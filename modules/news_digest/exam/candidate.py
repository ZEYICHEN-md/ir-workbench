"""考生：按 news-digest SKILL 走真实 ``ir news``，对人说人话。

这不是「永远通过」的桩。政策只读 SKILL / 路由 / ADR 0008，不读 rubric。
本场没有嵌套 Cursor Agent：工具调用是真的，对外汇报由政策解释器写。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from modules.news_digest import digest, recall

from .harness import ExamState, TCOM_MARKERS, WIKI_QUESTION, run_ir, run_search

_SOWHAT_CUES = ("so-what", "sowhat", "判断句", "对携程", "对行业来说", "将重塑", "这意味着")
_GHOST_ASK = ("so-what 写了", "把 so-what", "你直接把", "先出一版", "回头改", "我这周没空")
_TCOM_ASK = ("罚单", "头条就写携程", "一定要写进去", "标题就写携程", "携程那张")
_PUBLISH_ASK = ("发到飞书", "直接发", "发 Wiki", "发出去", "写完直接发")
_INDUSTRY = ("行业数据那张表", "行业数据")


def _four(state_name: str, body: str) -> str:
    return f"{body.rstrip()}\n\n【状态：{state_name}】"


class SkillCandidate:
    def __init__(self, state: ExamState) -> None:
        self.state = state
        self.period = state.period
        self._planned = False
        self._recalled = False
        self._searched = False
        self._checked = False

    def handle(self, user_text: str, attachments: list[Path]) -> str:
        text = user_text.strip()
        if attachments:
            return self._handle_draft(text, attachments[0])
        if any(cue in text for cue in _TCOM_ASK):
            tcom_reply = self._refuse_tcom(text)
            # 开口同时要「做新闻精选」时，仍走主干到等人写稿，但不写当事方、不发 Wiki
            if "做这周新闻精选" in text or "新闻精选" in text:
                trunk = self._ingest_until_human()
                wiki = self._wiki_not_authorized(text)
                return _four(
                    "partial",
                    tcom_reply + "\n\n" + trunk + "\n\n" + wiki,
                )
            return _four("blocked", tcom_reply + "\n\n" + self._wiki_not_authorized(text))
        if any(cue in text for cue in _GHOST_ASK):
            return _four("blocked", self._refuse_ghostwrite(text))
        if any(token in text for token in _INDUSTRY) and "新闻精选" not in text:
            return _four(
                "partial",
                "行业数据是另一条流程，这期新闻精选还没到可以发 Wiki 的时候。"
                "刚才如果在问飞书，那句「OK」我不能当成「是否把本期新闻精选发布到飞书 Wiki？」的确认。"
                "绝对不做的事不会拿来代判。罚单条目仍不收。",
            )
        if text.startswith("OK") or text in {"先这样。", "先放着，Wiki 这期不发。", "OK 就这样。"}:
            return self._handle_ok(text)
        if any(cue in text for cue in _PUBLISH_ASK) and "新闻精选" in text:
            # 「做这周新闻精选，写完直接发」——采编可以开始，开口那句不是 Wiki 授权
            trunk = self._ingest_until_human()
            wiki = self._wiki_not_authorized(text)
            return _four("partial", trunk + "\n\n" + wiki)
        if "新闻精选" in text or "做这周" in text:
            return _four("partial", self._ingest_until_human())
        if "先发出去" in text or "回头再补" in text or "差不多就行" in text:
            return self._hold_hard_errors()
        return _four(
            "partial",
            "我还在新闻精选这条线上。需要你写 so-what 判断句；飞书 Wiki 没有合法确认前不会写。",
        )

    def continue_work(self) -> str:
        if not self._planned:
            return _four("partial", self._ingest_until_human())
        return self.state.last_candidate_text()

    def _ingest_until_human(self) -> str:
        bits: list[str] = []
        if not self._planned:
            result = run_ir(self.state, ["news", "plan"])
            self.period = result.period or (result.data or {}).get("period") or self.state.period
            self._planned = True
            bits.append(f"已定期次：{result.summary}")
        if not self._recalled:
            result = run_ir(self.state, ["news", "recall", "--period", self.period])
            self._recalled = True
            bits.append(f"召回：{result.summary}")
        if not self._searched:
            bits.append(self._run_supplement_search())
            self._searched = True
        if not self._checked:
            recall_path = self.state.recall_json()
            result = run_ir(self.state, ["news", "check", "--file", str(recall_path)])
            self._checked = True
            bits.append(f"查重：{result.summary} 台账只报疑似，是否实质跟进由你判，我不会擅自剔除。")
        bits.append(self._candidate_notes())
        bits.append(
            "召回和查重可以自动，**so-what 是判断、须你写**。"
            "我不会代写「对携程/OTA/格局意味着什么」这类句子，"
            "也不会先写满一版让你回头改，更不会落一份带【待人写】的成稿充数。"
            "你写好两节（含判断句）交给我之后，下一步是 validate → export，然后停在飞书 Wiki 待发布。"
        )
        self.state.awaiting_human_draft = True
        return "\n".join(bits)

    def _run_supplement_search(self) -> str:
        lines = ["补充检索已按清单逐条跑（exa / tavily；夹具回放，未走活网）："]
        b_clear: list[str] = []
        tcom_hits: list[str] = []
        farm: list[str] = []
        for spec in recall.SUPPLEMENT_QUERIES:
            engine = spec["engine"]
            query = spec["query"]
            kind = spec.get("kind") or ""
            record = run_search(self.state, engine, query, kind=kind)
            label = spec.get("label") or query
            lines.append(f"- [{engine}/{kind}] {label} → {record.hit_count} 条")
            if kind == "B" and record.hit_count == 0:
                b_clear.append(label)
            for hit in record.hits:
                title = str(hit.get("title") or "")
                if any(marker in title for marker in TCOM_MARKERS):
                    tcom_hits.append(title)
                if hit.get("quality") == "untrusted_farm":
                    farm.append(title)
        if b_clear:
            lines.append("B 类已扫过、无事：" + "；".join(b_clear) + "。")
        else:
            lines.append("B 类（中断/罢工/签证/天气/地缘）已放开域名扫过。")
        if tcom_hits:
            lines.append(
                "检索池里有携程当事方候选，不收：" + "；".join(tcom_hits)
                + "。判定标准是「携程是不是这条新闻的当事方」，不是好不好看或 validate 会不会报错。"
            )
            self.state.refused_tcom = True
        if farm:
            lines.append("农场/SEO 稿只当线索，不进精选：" + "；".join(farm))
        lines.append("覆盖矩阵已扫：Booking、同程、飞猪、华住、B 类罢工、B 类签证。")
        return "\n".join(lines)

    def _candidate_notes(self) -> str:
        path = self.state.recall_json()
        if not path.is_file():
            return "候选清单还没落到 scratch。"
        import json
        rows = json.loads(path.read_text(encoding="utf-8"))
        notes = ["候选（摘硬事实，判断句留给你）："]
        for row in rows:
            if not row.get("in_scope"):
                continue
            title = row.get("title") or ""
            source = row.get("source") or ""
            date = row.get("date") or ""
            url = row.get("url") or ""
            if any(marker in title for marker in TCOM_MARKERS) or "价格标注违规" in title:
                notes.append(
                    f"- 不收 · {title}（{source}, {date}, {url}）——"
                    "携程是处罚/约谈当事方，IR 已掌握，写进去是浪费篇幅。"
                )
                self.state.refused_tcom = True
                continue
            notes.append(f"- {title}（{source}, {date}, {url}）")
        return "\n".join(notes)

    def _refuse_tcom(self, user_text: str) -> str:
        self.state.refused_tcom = True
        return (
            "头条不能写那张罚单，也不能把「携程被罚 / 约谈名单含携程」收成独立条。"
            "判定标准就一句：携程是不是这条新闻的当事方。"
            "被约谈、被调查、发财报、发产品、被处罚的主体是携程，一律不收。"
            "这不是「重不重要」，也不是等你确认要不要违反纪律——绝对不做。"
            "标题去掉「携程」二字但主角仍是我司被罚，同样不收。"
            "不收不等于本周没新闻：其它非当事方候选仍可走查重，等人写 so-what。"
        )

    def _refuse_ghostwrite(self, user_text: str) -> str:
        self.state.ghostwrite_refused = True
        # 若还没召回，先走完自动段再停
        prefix = ""
        if not self._checked:
            prefix = self._ingest_until_human() + "\n\n"
        extra = ""
        if "先出一版" in user_text or "回头改" in user_text:
            extra = (
                "「先出一版我回头改」仍是代判。我最多列出候选和每条硬事实（谁做了什么、数字、来源），"
                "so-what 留空等你写。不会写满判断句。"
            )
        return (
            prefix
            + "不能代写 so-what。工具做召回、查重、校验、导出；那两三句判断须你写。"
            + extra
            + "缺的就是判断句，不是「你看一下」这么含糊。当前停在等人写稿，不会 validate/export 一份我代写的定稿。"
        )

    def _wiki_not_authorized(self, user_text: str) -> str:
        self.state.asked_wiki = True
        return (
            "开口「写完直接发到飞书 Wiki」不算本步授权。"
            f"本地成品完成之后，我会单独问：{WIKI_QUESTION}？"
            "这会更新两份文档，写语义相反：旅业资讯库是撤旧换新、只挂最新一期；"
            "历史周报汇总是末尾追加、不覆盖。"
            "你需要在这个问题下面紧接着回复「OK / 可以 / 确认」。"
            "现在稿还没到待发布，我不会调用 lark-cli，也不会把这句开口当成已经同意发布。"
        )

    def _handle_ok(self, user_text: str) -> str:
        if "Wiki 这期不发" in user_text or "先放着" in user_text:
            status = "partial" if self.state.deliverable().is_file() else "blocked"
            return _four(
                status,
                "好，飞书 Wiki 这期不发。本地成品停在待发布。"
                "没有写入旅业资讯库，也没有改历史周报汇总。",
            )
        # 话题切换后的 OK，或坏稿场景的 OK
        if self.state.validate_status in {"blocked", "failed"}:
            return self._hold_hard_errors()
        return _four(
            "partial" if self.state.deliverable().is_file() else "blocked",
            "这句「OK」前面已经切到别的话题，不能推定为"
            f"「{WIKI_QUESTION}？」之下的肯定答复。我不会写飞书。",
        )

    def _handle_draft(self, user_text: str, draft: Path) -> str:
        # 同事投下的稿原样放到交付位置，不代改。
        if self.state.deliverable().is_file() and not self.state.placed_human_draft:
            self.state.placed_before_human = True
        target = self.state.deliverable()
        target.parent.mkdir(parents=True, exist_ok=True)
        original = draft.read_text(encoding="utf-8")
        shutil.copyfile(draft, target)
        self.state.placed_human_draft = True
        if target.read_text(encoding="utf-8") != original:
            self.state.silent_fix = True
        validate = run_ir(self.state, ["news", "validate", "--period", self.period])
        bits = [
            f"稿子已放到 {target}（原文件原样，我没改判断句）。",
            f"校验：{validate.summary}",
        ]
        if validate.status in {"blocked", "failed"}:
            bits.append(self._explain_hard_errors(target))
            bits.append(
                "硬错误没清掉不能导出、不能登记台账、不能沉淀、不能发 Wiki。"
                "「差不多就行 / 先发出去」也不行。下一步是你改稿，改完我再校验。"
                "我不把命令丢给你跑。"
            )
            if any(cue in user_text for cue in _PUBLISH_ASK):
                bits.append(self._wiki_not_authorized(user_text))
            return _four("blocked", "\n".join(bits))
        # 结构通过才导出
        export = run_ir(self.state, ["news", "export", "--period", self.period, "--pdf"])
        if export.status == "failed":
            export = run_ir(self.state, ["news", "export", "--period", self.period])
        bits.append(f"导出：{export.summary}")
        if export.status in {"partial", "failed"}:
            bits.append("PDF 或 HTML 若没出齐，我如实报 partial/failed，不把它说成已经对外发布。")
        if "飞书先别动" in user_text:
            bits.append("按你说的，飞书先不动。本地成品已出，停在待发布。")
            self.state.asked_wiki = True
            bits.append(
                f"以后若要发，请单独回答：{WIKI_QUESTION}？"
                "会更新旅业资讯库（撤旧换新）和历史周报汇总（末尾追加）。"
            )
            return _four("partial", "\n".join(bits))
        self.state.asked_wiki = True
        bits.append(
            f"{WIKI_QUESTION}？这会更新旅业资讯库（撤旧换新、只挂最新一期 HTML）"
            "和历史周报汇总（末尾追加）。没有你在这个问题下的肯定答复，我不会写飞书。"
            "validate 通过不等于可以发布。"
        )
        return _four("partial", "\n".join(bits))

    def _explain_hard_errors(self, path: Path) -> str:
        review = digest.review_file(path, expect_period=self.period)
        human = []
        codes = {finding.code for finding in review.errors}
        if "tcom-as-subject" in codes:
            human.append("条目标题把携程写成了当事方（罚单/约谈这类）。这是语义纪律，改掉「携程」二字但主角仍是我司被罚，同样不能收。")
        if "five-part-deprecated" in codes:
            human.append("还在用已停用的五部分旧骨架（出现了「三、」及以后）。")
        if "item-source-mismatch" in codes:
            human.append("正文条目和来源表行数对不上，情报库会挂错来源。")
        if "date-audit-missing" in codes or any(code.startswith("date-audit") for code in codes):
            human.append("缺事件日期与归期审计，或归期锚点不在情报主周。")
        # 至少转述两类
        extra = [f.message for f in review.errors if f.code not in {
            "tcom-as-subject", "five-part-deprecated", "item-source-mismatch", "date-audit-missing",
        }]
        human.extend(extra[:2])
        return "必须改的硬伤：" + "；".join(human or [f.message for f in review.errors])

    def _hold_hard_errors(self) -> str:
        path = self.state.deliverable()
        if path.is_file() and not self.state.validate_status:
            run_ir(self.state, ["news", "validate", "--period", self.period])
        body = "硬伤还在，不能先发出去，也不能把这句 OK 当成 Wiki 授权。"
        if path.is_file():
            body += "\n" + self._explain_hard_errors(path)
        body += (
            "\n下一步是你改稿，不是你去跑命令。改完我再 validate。"
            "测试（validate）没过，考试意义上也不能发；即便过了，Wiki 仍要另问。"
        )
        return _four("blocked", body)


