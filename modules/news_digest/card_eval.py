"""飞书周报卡片的质量评估与迭代门禁。

只覆盖 `references/feishu-im-card.md` 与 `feishu-im-card.template.json`。
不发飞书，不合并。信息量与隐喻率由外部裁判模型计数；
本模块切句、套排除名单，并与同一期次的第一次打分比较。
没有 `IR_CARD_JUDGE_API_KEY` 时不编造分数。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from workbench.fileio import write_text, write_text_atomic
from workbench.paths import Paths
from workbench.result import Result

from . import calendar_
from .steps import DOMAIN

#: 将要发送的卡片正文。目录用期次键，文件名用 ASCII（ADR 0007）。
DRAFT_FILENAME = "feishu-card-draft.txt"
#: 人粘回的修改稿。本次没传入就不存在。
FINAL_FILENAME = "feishu-card-final.txt"
RECORD_FILENAME = "feishu-card-eval.json"

SCOPE = "feishu-im-card"
SCOPE_PATHS = (
    "modules/news_digest/references/feishu-im-card.md",
    "modules/news_digest/references/feishu-im-card.template.json",
)

#: 日常说法或术语，不是隐喻。裁判标了也要丢掉。顺序固定，提示词不随哈希变。
EXCLUDED_METAPHORS = ("字段", "运行", "面对挑战", "神经网络")
_EXCLUDED_METAPHOR_SET = frozenset(EXCLUDED_METAPHORS)

JUDGE_API_KEY_ENV = "IR_CARD_JUDGE_API_KEY"
JUDGE_MODEL_ENV = "IR_CARD_JUDGE_MODEL"
JUDGE_BASE_URL_ENV = "IR_CARD_JUDGE_BASE_URL"
DEFAULT_JUDGE_MODEL = "gpt-4.1"
DEFAULT_JUDGE_BASE_URL = "https://api.openai.com/v1"

_SENTENCE_END = "。？！"
_PEERS_MARKERS = ("peers-model", "peers_model", "peers-appendix", "/peers/")


class CardEvalBlocked(Exception):
    def __init__(self, summary: str, *, missing: list[str] | None = None) -> None:
        super().__init__(summary)
        self.summary = summary
        self.missing = missing or []


class CardEvalFailed(Exception):
    def __init__(self, summary: str) -> None:
        super().__init__(summary)
        self.summary = summary


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def draft_path(base: Paths, period: str) -> Path:
    return base.outputs(DOMAIN, period) / DRAFT_FILENAME


def final_path(base: Paths, period: str) -> Path:
    return base.outputs(DOMAIN, period) / FINAL_FILENAME


def record_path(base: Paths, period: str) -> Path:
    return base.runs(DOMAIN, period) / RECORD_FILENAME


def path_is_peers(path: Path) -> bool:
    text = "/" + path.as_posix().lower()
    return any(marker in text for marker in _PEERS_MARKERS)


def is_heading_line(line: str) -> bool:
    """Markdown 标题行。1 到 6 个 `#`，后面还有文字。单独的井号不是标题。"""
    stripped = line.strip()
    marks = 0
    while marks < len(stripped) and stripped[marks] == "#":
        marks += 1
    if marks < 1 or marks > 6 or marks == len(stripped):
        return False
    return bool(stripped[marks:].strip())


def is_table_row(line: str) -> bool:
    """Markdown 表行。以 `|` 起止，或一行里至少两个 `|`。"""
    stripped = line.strip()
    if "|" not in stripped:
        return False
    if stripped.startswith("|") or stripped.endswith("|"):
        return True
    return stripped.count("|") >= 2


def is_link_only_line(line: str) -> bool:
    """整行只有一个 URL，或只有一个 Markdown 链接。

    去掉强调符号后再判断，所以 `**[标题](https://…)**` 也算纯链接行。
    行里还有别的字，就不算。
    """
    core = line.strip().strip("*_`").strip()
    if core.startswith("<") and core.endswith(">"):
        core = core[1:-1].strip()
    return _is_bare_url(core) or _is_markdown_link(core)


def _is_bare_url(text: str) -> bool:
    if any(ch.isspace() for ch in text):
        return False
    return text.startswith("https://") or text.startswith("http://")


def _is_markdown_link(text: str) -> bool:
    if not (text.startswith("[") and text.endswith(")")):
        return False
    label, sep, target = text[1:-1].rpartition("](")
    if not sep or not label.strip():
        return False
    return _is_bare_url(target.strip())


def countable_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if is_heading_line(line) or is_table_row(line) or is_link_only_line(line):
            continue
        lines.append(line)
    return lines


def split_sentences(text: str) -> list[str]:
    """按 `。？！` 切句。半角 `.` `!` `?` 不切。

    标题行、表行、纯链接行整行不计入，行内的句号也不产生句子。
    没有句末标点的一行算一句。
    """
    sentences: list[str] = []
    for line in countable_lines(text):
        parts = _split_on_terminators(line)
        sentences.extend(part.strip() for part in parts if part.strip())
    return sentences


def _split_on_terminators(line: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for char in line:
        if char in _SENTENCE_END:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(char)
    parts.append("".join(buf))
    return parts


def normalize_metaphor(phrase: str) -> str:
    return phrase.strip().strip("「」\"'“”『』")


def metaphor_rejection(phrase: str, plainer: str, sentences: list[str]) -> str | None:
    """返回丢掉这条隐喻的原因。留下时返回 None。"""
    needle = normalize_metaphor(phrase)
    if not needle:
        return "empty"
    if not plainer.strip():
        return "no-plainer"
    if needle in _EXCLUDED_METAPHOR_SET:
        return "excluded"
    if needle not in "\n".join(sentences):
        return "not-in-text"
    return None


def accepted_metaphors(items: list[dict], sentences: list[str]) -> list[dict]:
    kept: list[dict] = []
    for item in items:
        phrase = str(item.get("phrase") or "")
        plainer = str(item.get("plainer") or "")
        if metaphor_rejection(phrase, plainer, sentences) is not None:
            continue
        kept.append({"phrase": normalize_metaphor(phrase), "plainer": plainer.strip()})
    return kept


def metaphor_rate_percent(metaphor_count: int, sentence_count: int) -> float:
    """隐喻率 = 隐喻数 / 句子数 × 100。展示值保留两位小数，四舍五入。"""
    if sentence_count <= 0:
        raise ValueError("sentence_count 必须大于 0")
    value = (Decimal(metaphor_count) * Decimal(100) / Decimal(sentence_count)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(value)


def rate_not_higher(current: dict, baseline: dict) -> bool:
    """用件数交叉相乘，避免两位小数把门禁判反。"""
    return (
        current["metaphor_count"] * baseline["sentence_count"]
        <= baseline["metaphor_count"] * current["sentence_count"]
    )


def decide_recommendation(baseline: dict | None, current: dict) -> dict:
    """第一次打分是基线。之后仅当信息量不降且隐喻率不升，才记 pending-confirm。

    返回值里的 merged 恒为 False。本函数不表示已经合并。
    """
    if baseline is None:
        return {
            "recommendation": "baseline",
            "pending_confirm": False,
            "merged": False,
            "reasons": ["该期次第一次打分，记为基线"],
        }
    info_ok = current["信息量"] >= baseline["信息量"]
    metaphor_ok = rate_not_higher(current, baseline)
    reasons: list[str] = []
    if not info_ok:
        reasons.append("信息量下降")
    if not metaphor_ok:
        reasons.append("隐喻率上升")
    if info_ok and metaphor_ok:
        return {
            "recommendation": "pending-confirm",
            "pending_confirm": True,
            "merged": False,
            "reasons": ["信息量未下降", "隐喻率未上升"],
        }
    return {
        "recommendation": "reject",
        "pending_confirm": False,
        "merged": False,
        "reasons": reasons,
    }


def fact_points_from_payload(payload: dict) -> list[str]:
    raw = payload.get("fact_points")
    if not isinstance(raw, list):
        raise CardEvalFailed("裁判返回的 fact_points 不是数组。未记分。")
    points: list[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("claim") or "").strip()
        else:
            raise CardEvalFailed("裁判返回的事实点不是字符串。未记分。")
        if text:
            points.append(text)
    return points


def metaphors_from_payload(payload: dict) -> list[dict]:
    raw = payload.get("metaphors", [])
    if not isinstance(raw, list):
        raise CardEvalFailed("裁判返回的 metaphors 不是数组。未记分。")
    items: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            items.append({"phrase": item.strip(), "plainer": ""})
        elif isinstance(item, dict):
            items.append(
                {
                    "phrase": str(item.get("phrase") or item.get("text") or "").strip(),
                    "plainer": str(item.get("plainer") or item.get("plain") or "").strip(),
                }
            )
        else:
            raise CardEvalFailed("裁判返回的隐喻不是对象。未记分。")
    return items


def metrics_for(sentences: list[str], payload: dict) -> dict:
    if not sentences:
        raise CardEvalBlocked("草稿没有可计的句子，不能计算隐喻率。")
    fact_points = fact_points_from_payload(payload)
    metaphors = accepted_metaphors(metaphors_from_payload(payload), sentences)
    count = len(metaphors)
    return {
        "信息量": len(fact_points),
        "隐喻率": metaphor_rate_percent(count, len(sentences)),
        "sentence_count": len(sentences),
        "metaphor_count": count,
        "fact_points": fact_points,
        "metaphors": metaphors,
    }


def judge_model_name() -> str:
    return os.environ.get(JUDGE_MODEL_ENV, "").strip() or DEFAULT_JUDGE_MODEL


def judge_base_url() -> str:
    return os.environ.get(JUDGE_BASE_URL_ENV, "").strip().rstrip("/") or DEFAULT_JUDGE_BASE_URL


def _judge_instructions() -> str:
    excluded = "、".join(EXCLUDED_METAPHORS)
    return (
        "你是飞书周报卡片的裁判。你没有写这张卡。"
        "只计数。不要改写卡片。不要判断陈述是否属实。\n"
        "信息量等于事实点个数。一个事实点是一条具体陈述："
        "一个数字、一个日期、一个名称、一个产品，或一个事件。"
        "评价句不是事实点。例如「这很重要」不是事实点。\n"
        "隐喻是可以换成更直白说法的词或短语。"
        "给不出更直白的说法，就不是隐喻，不要放入 metaphors。"
        f"不要把这些词或短语算作隐喻：{excluded}。\n"
        "用户消息里一行是一句，已经去掉标题行、表格行和纯链接行。\n"
        "只返回一个 JSON 对象，不要写别的文字。"
        '{"fact_points":["..."],"metaphors":[{"phrase":"...","plainer":"..."}]}'
        "没有隐喻时 metaphors 为空数组。"
    )


def parse_judge_content(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if text.endswith("```"):
            text = text[: -3].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise CardEvalFailed(f"裁判返回的不是 JSON。未记分。（{error.msg}）") from error
    if not isinstance(data, dict):
        raise CardEvalFailed("裁判返回的 JSON 不是对象。未记分。")
    return data


def post_chat(api_key: str, model: str, card_sentences: str) -> dict:
    """调用 OpenAI 兼容的 chat completions。密钥只放在请求头里。"""
    url = judge_base_url() + "/chat/completions"
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _judge_instructions()},
            {"role": "user", "content": "句子如下，一行一句：\n" + card_sentences},
        ],
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise CardEvalFailed(f"裁判接口返回 HTTP {error.code}。未记分。") from error
    except urllib.error.URLError as error:
        raise CardEvalFailed(f"裁判接口连不上（{error.reason}）。未记分。") from error
    except TimeoutError as error:
        raise CardEvalFailed("裁判接口超时。未记分。") from error
    except json.JSONDecodeError as error:
        raise CardEvalFailed("裁判接口返回的不是 JSON。未记分。") from error
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise CardEvalFailed("裁判接口没有返回消息正文。未记分。") from error
    if not isinstance(content, str) or not content.strip():
        raise CardEvalFailed("裁判消息正文是空的。未记分。")
    return parse_judge_content(content)


def request_judge(card_sentences: str, writer_model: str) -> dict:
    api_key = os.environ.get(JUDGE_API_KEY_ENV, "").strip()
    if not api_key:
        raise CardEvalBlocked(
            "裁判未打分：缺少环境变量 IR_CARD_JUDGE_API_KEY。"
            "没有密钥，不编造信息量或隐喻率。",
            missing=[JUDGE_API_KEY_ENV],
        )
    model = judge_model_name()
    writer = writer_model.strip()
    if not writer:
        raise CardEvalBlocked(
            f"裁判模型是 {model}。需要 --writer-model 写明写卡模型，"
            "以便确认两者不是同一个模型。未打分。",
            missing=["--writer-model"],
        )
    if writer.lower() == model.lower():
        raise CardEvalBlocked(
            f"写卡模型与裁判模型都是 {model}。裁判必须是另一个模型。未打分。",
            missing=["--writer-model"],
        )
    payload = post_chat(api_key, model, card_sentences)
    return {"payload": payload, "judge_model": model, "writer_model": writer}


def _empty_record(period: str) -> dict:
    return {
        "version": 1,
        "scope": SCOPE,
        "scope_paths": list(SCOPE_PATHS),
        "period": period,
        "merged": False,
        "program_action": "record-only",
        "note": "本程序不合并。人确认前不得合并飞书卡片模板改动。",
        "baseline": None,
        "latest_recommendation": None,
        "runs": [],
    }


def load_record(base: Paths, period: str) -> dict:
    path = record_path(base, period)
    if not path.is_file():
        return _empty_record(period)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CardEvalBlocked(f"打分记录读不了，未覆盖：{path}（{error}）") from error
    if not isinstance(data, dict) or data.get("period") != period:
        raise CardEvalBlocked(f"打分记录的期次与 {period} 不一致，未覆盖：{path}")
    if data.get("scope") != SCOPE:
        raise CardEvalBlocked(f"打分记录的范围不是 {SCOPE}，未覆盖：{path}")
    return data


def _checked_baseline(baseline: dict | None) -> dict | None:
    if baseline is None:
        return None
    for key in ("信息量", "metaphor_count", "sentence_count"):
        value = baseline.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise CardEvalBlocked(f"基线记录的{key}不是整数，未覆盖。")
    if baseline["sentence_count"] <= 0:
        raise CardEvalBlocked("基线句子数是 0，未覆盖。")
    return baseline


def persist_score(
    base: Paths,
    period: str,
    metrics: dict,
    *,
    judge_model: str,
    writer_model: str,
    draft: Path,
    final: Path | None,
) -> dict:
    record = load_record(base, period)
    baseline = _checked_baseline(record.get("baseline"))
    decision = decide_recommendation(baseline, metrics)
    run = {
        "scored_at": _now(),
        "source": "draft",
        "draft": DRAFT_FILENAME,
        "final": FINAL_FILENAME if final is not None else None,
        "final_scored": False,
        "信息量": metrics["信息量"],
        "隐喻率": metrics["隐喻率"],
        "sentence_count": metrics["sentence_count"],
        "metaphor_count": metrics["metaphor_count"],
        "fact_points": metrics["fact_points"],
        "metaphors": metrics["metaphors"],
        "judge_model": judge_model,
        "writer_model": writer_model,
        "recommendation": decision["recommendation"],
        "reasons": decision["reasons"],
        "merged": False,
    }
    if baseline is None:
        record["baseline"] = {
            "信息量": metrics["信息量"],
            "隐喻率": metrics["隐喻率"],
            "sentence_count": metrics["sentence_count"],
            "metaphor_count": metrics["metaphor_count"],
            "scored_at": run["scored_at"],
            "judge_model": judge_model,
            "writer_model": writer_model,
            "draft": str(draft),
        }
    record["merged"] = False
    record["program_action"] = "record-only"
    record["latest_recommendation"] = decision["recommendation"]
    record["runs"] = list(record.get("runs") or [])
    record["runs"].append(run)
    write_text_atomic(
        record_path(base, period),
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
    )
    return {"decision": decision, "run": run, "baseline": record["baseline"], "record": record}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CardEvalBlocked(f"读不到文件：{path}（{error}）") from error
    except UnicodeError as error:
        raise CardEvalBlocked(f"文件不是 UTF-8：{path}（{error}）") from error


def _normalize_saved(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text


def save_texts(base: Paths, period: str, draft_text: str, final_text: str | None) -> tuple[Path, Path | None]:
    """写入草稿。只有本次传入终稿才写终稿；否则删掉已有终稿。"""
    saved_draft = draft_path(base, period)
    saved_final = final_path(base, period)
    write_text(saved_draft, _normalize_saved(draft_text))
    if final_text is None:
        if saved_final.is_file():
            saved_final.unlink()
        return saved_draft, None
    write_text(saved_final, _normalize_saved(final_text))
    return saved_draft, saved_final


def _resolve_period(args) -> str:
    period = (getattr(args, "period", None) or "").strip() or calendar_.latest_completed_key()
    calendar_.parse_key(period)
    return period


def _blocked(summary: str, period: str | None, **kwargs) -> Result:
    return Result(status="blocked", summary=summary, domain=DOMAIN, period=period, **kwargs)


def cmd_card_eval(args, base: Paths) -> Result:
    try:
        period = _resolve_period(args)
    except calendar_.PeriodError as error:
        return _blocked(str(error), getattr(args, "period", None) or None)

    label = calendar_.label_from_key(period)
    draft_src = getattr(args, "draft_file", None) or None
    final_src = getattr(args, "final_file", None) or None
    for label_zh, src in (("草稿", draft_src), ("终稿", final_src)):
        if src and path_is_peers(Path(src)):
            return _blocked(
                f"本命令只评估飞书卡片材料（{SCOPE}），不评估 Peers。已拒绝这份{label_zh}。",
                period,
            )

    try:
        if draft_src:
            draft_text = _read_text(Path(draft_src))
        elif draft_path(base, period).is_file():
            draft_text = _read_text(draft_path(base, period))
        else:
            return _blocked(
                "没有将要发送的卡片正文。",
                period,
                missing=[str(draft_path(base, period))],
                next_steps=[
                    "用 --draft-file 传入卡片正文。命令会把它写成 "
                    f"outputs/news-digest/{period}/{DRAFT_FILENAME}。",
                ],
            )
        if not draft_text.strip():
            return _blocked("卡片正文是空的。未打分。", period)
        final_text = None
        if final_src:
            final_text = _read_text(Path(final_src))
            if not final_text.strip():
                return _blocked("粘回的终稿是空的。未写入终稿，也未打分。", period)
        saved_draft, saved_final = save_texts(base, period, draft_text, final_text)
    except CardEvalBlocked as error:
        return _blocked(error.summary, period, missing=error.missing)

    sentences = split_sentences(draft_text)
    local = {
        "judge": "blocked",
        "required_env": JUDGE_API_KEY_ENV,
        "scores": None,
        "sentence_count": len(sentences),
        "draft": str(saved_draft),
        "final": str(saved_final) if saved_final else None,
        "scope": SCOPE,
        "merged": False,
    }
    if not sentences:
        local["required_env"] = None
        return _blocked(
            "草稿没有可计的句子。标题行、表格行和纯链接行不计入。未打分。",
            period,
            data=local,
        )

    writer = (getattr(args, "writer_model", None) or "").strip()
    if not writer:
        writer = os.environ.get("IR_CARD_WRITER_MODEL", "").strip()
    try:
        judged = request_judge("\n".join(sentences), writer)
        metrics = metrics_for(sentences, judged["payload"])
        stored = persist_score(
            base,
            period,
            metrics,
            judge_model=judged["judge_model"],
            writer_model=judged["writer_model"],
            draft=saved_draft,
            final=saved_final,
        )
    except CardEvalBlocked as error:
        data = dict(local)
        if JUDGE_API_KEY_ENV not in error.missing:
            data["required_env"] = None
            data["judge"] = "blocked"
        return _blocked(
            error.summary,
            period,
            missing=error.missing,
            data=data,
            next_steps=_blocked_next_steps(error),
        )
    except CardEvalFailed as error:
        return Result(
            status="failed",
            summary=error.summary,
            domain=DOMAIN,
            period=period,
            data={
                "judge": "failed",
                "scores": None,
                "draft": str(saved_draft),
                "final": str(saved_final) if saved_final else None,
                "merged": False,
                "scope": SCOPE,
            },
            next_steps=["分数没有写入。排除接口故障后，用同一期次重跑。"],
        )

    decision = stored["decision"]
    baseline = stored["baseline"]
    recommendation = decision["recommendation"]
    summary = _summary(label, metrics, baseline, recommendation)
    level = "fail" if recommendation == "reject" else "ok"
    status = "partial" if recommendation == "reject" else "success"
    if recommendation == "pending-confirm":
        status = "partial"
    return Result(
        status=status,
        summary=summary,
        domain=DOMAIN,
        period=period,
        checks=[
            {"name": "范围", "level": "ok", "detail": SCOPE},
            {"name": "信息量", "level": level, "detail": str(metrics["信息量"])},
            {
                "name": "隐喻率",
                "level": level,
                "detail": (
                    f"{metrics['隐喻率']}（{metrics['metaphor_count']}/"
                    f"{metrics['sentence_count']}×100）"
                ),
            },
            {"name": "建议", "level": level, "detail": recommendation},
            {"name": "合并", "level": "ok", "detail": "未合并"},
            {
                "name": "终稿",
                "level": "ok",
                "detail": FINAL_FILENAME if saved_final else "无",
            },
        ],
        next_steps=_scored_next_steps(recommendation),
        data={
            "judge": "scored",
            "judge_model": stored["run"]["judge_model"],
            "writer_model": stored["run"]["writer_model"],
            "scores": {
                "信息量": metrics["信息量"],
                "隐喻率": metrics["隐喻率"],
                "sentence_count": metrics["sentence_count"],
                "metaphor_count": metrics["metaphor_count"],
            },
            "baseline": {
                "信息量": baseline["信息量"],
                "隐喻率": baseline["隐喻率"],
            },
            "recommendation": recommendation,
            "reasons": decision["reasons"],
            "merged": False,
            "scope": SCOPE,
            "draft": str(saved_draft),
            "final": str(saved_final) if saved_final else None,
            "record": str(record_path(base, period)),
        },
    )


def _blocked_next_steps(error: CardEvalBlocked) -> list[str]:
    if JUDGE_API_KEY_ENV in error.missing:
        return [
            f"设置环境变量 {JUDGE_API_KEY_ENV} 后，用同一期次重跑。",
            "同时用 --writer-model 写明写卡模型。它必须和裁判模型不同。",
            "草稿已保存。终稿仅在本次传入 --final-file 时存在。",
        ]
    return ["换一个与裁判不同的 --writer-model 后，用同一期次重跑。草稿已保存。"]


def _summary(label: str, metrics: dict, baseline: dict, recommendation: str) -> str:
    if recommendation == "baseline":
        return (
            f"{label}：信息量 {metrics['信息量']}，隐喻率 {metrics['隐喻率']}。"
            "这是该期次的基线。未合并。"
        )
    return (
        f"{label}：信息量 {metrics['信息量']}（基线 {baseline['信息量']}），"
        f"隐喻率 {metrics['隐喻率']}（基线 {baseline['隐喻率']}）。"
        f"建议 {recommendation}。未合并。"
    )


def _scored_next_steps(recommendation: str) -> list[str]:
    if recommendation == "baseline":
        return [
            "后续评估使用同一期次。本命令不改基线，也不合并。",
            "模板改动要人确认后才合并。确认措辞由人在仓库流程里给出，本命令不执行合并。",
        ]
    if recommendation == "pending-confirm":
        return [
            "建议记为 pending-confirm。本命令不合并。",
            "需要人确认后，才由人合并飞书卡片模板改动。",
        ]
    return [
        "未达到 pending-confirm：信息量不得下降，隐喻率不得上升。",
        "本命令不合并。",
    ]
