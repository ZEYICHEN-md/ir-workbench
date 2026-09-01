"""Code-enforced expert-call extraction, rendering, and Lark publishing."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime
from html import escape, unescape
from pathlib import Path
from typing import Any, Callable

from workbench.fileio import write_text
from workbench.paths import Paths
from workbench.result import Result

DOMAIN = "expert-calls"
WIKI_URL = "https://trip.larkenterprise.com/wiki/JobqwazW9ivX2ykm4Jqc8dXwnBd"
DOC_TOKEN = "ADJHdO2CWo0TMNxTZ2ecfHJAnlh"
HEADING = "Expert Call"
TEMPLATE = Path(__file__).with_name("templates") / "expert_call_callout.xml"
EVIDENCE_KEYS = (
    "quantified_content",
    "causal_mechanism",
    "relevant_information_gain",
)
RELEVANCE_AREAS = {
    "tcom_operations": "携程经营与财务判断",
    "china_cross_border": "中国及跨境旅行需求",
    "global_ota_competition": "全球 OTA 竞争格局",
    "ai_travel_distribution": "AI 对旅行搜索、流量与交易转化的影响",
}
SCORE_WEIGHTS = {
    "ir_relevance": 30,
    "information_gain": 20,
    "expert_authority": 20,
    "evidence_quality": 15,
    "causal_depth": 10,
    "freshness": 5,
}
ORGANIZATION_SCOPES = {
    "global_leader": "大型跨国平台/集团",
    "scaled_multimarket": "有规模的多市场公司",
    "regional_or_niche": "区域性或细分公司",
    "single_property_or_local": "单体酒店或本地小型公司",
}
ORGANIZATION_TIER_CAPS = {
    "global_leader": "A",
    "scaled_multimarket": "B",
    "regional_or_niche": "C",
    "single_property_or_local": "C",
}
STRATEGIC_MARKET_SCOPES = {
    "china_or_apac_priority": "中国或亚太重点市场",
    "global_peer_readthrough": "全球竞对映射",
    "other_region": "其他区域市场",
    "local_only": "单一本地市场",
}
ROLE_LEVELS = {
    "c_suite_or_business_head",
    "vp_or_head",
    "director",
    "manager_or_operator",
    "advisor_or_external",
}
FUNCTIONAL_PROXIMITIES = {
    "direct_owner",
    "direct_team",
    "adjacent_function",
    "external_observer",
}
TIER_LABELS = {
    "A": "优先考虑进入飞书",
    "B": "可考虑，需人工权衡",
    "C": "建议不收录",
}


class ManifestValidationError(ValueError):
    """A callout manifest is unsafe or incomplete."""


class EmptyOrScannedPDFError(ValueError):
    """The PDF has no extractable text and requires OCR or another source."""


ScannedOrEmptyPDFError = EmptyOrScannedPDFError


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_payload(source: Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, Path):
        return json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ManifestValidationError("manifest 必须是 JSON object")
    return deepcopy(source)


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("interviews", payload.get("records"))
    if not isinstance(rows, list) or not rows:
        raise ManifestValidationError("manifest.interviews 必须是非空数组")
    return rows
def _present(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    return value is not None and value != "" and value != []


def _located(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.search(
        r"(?:第?\s*\d+\s*页|page\s*\d+|p\.?\s*\d+|第?\s*\d+\s*(?:段|行|节)|"
        r"location|section|question\s*\d+|\d{1,2}:\d{2})",
        value,
        re.I,
    ))


def _relevance_details(
    evidence: dict[str, Any],
    index: int,
    *,
    required: bool,
) -> tuple[list[str], str]:
    value = evidence.get("relevant_information_gain")
    if value in (None, False, "", []):
        if required:
            raise ManifestValidationError(
                f"第 {index} 条没有直接 IR 信息增量；B2B 不能单独作为收录理由"
            )
        return [], ""
    if not isinstance(value, dict):
        raise ManifestValidationError(
            f"第 {index} 条 relevant_information_gain 必须包含 areas 与 reason"
        )
    areas = value.get("areas")
    reason = value.get("reason")
    if not isinstance(areas, list) or not areas or not all(isinstance(area, str) for area in areas):
        raise ManifestValidationError(f"第 {index} 条相关性 areas 必须是非空数组")
    unknown = set(areas) - set(RELEVANCE_AREAS)
    if unknown:
        raise ManifestValidationError(
            f"第 {index} 条有未知相关性分类：{', '.join(sorted(unknown))}"
        )
    if not isinstance(reason, str) or not reason.strip():
        raise ManifestValidationError(f"第 {index} 条相关性 reason 不能为空")
    return list(dict.fromkeys(areas)), reason.strip()


def _validate_expert_profile(row: dict[str, Any], index: int) -> dict[str, Any]:
    profile = row.get("expert_profile")
    if not isinstance(profile, dict):
        raise ManifestValidationError(f"第 {index} 条缺 expert_profile")
    for key in (
        "organization", "organization_scope", "strategic_market_scope",
        "role_level", "functional_proximity", "assessment",
    ):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ManifestValidationError(f"第 {index} 条 expert_profile.{key} 不能为空")
    if profile["organization_scope"] not in ORGANIZATION_SCOPES:
        raise ManifestValidationError(
            f"第 {index} 条 organization_scope 只能是：{', '.join(ORGANIZATION_SCOPES)}"
        )
    if profile["strategic_market_scope"] not in STRATEGIC_MARKET_SCOPES:
        raise ManifestValidationError(
            f"第 {index} 条 strategic_market_scope 只能是：{', '.join(STRATEGIC_MARKET_SCOPES)}"
        )
    if profile["role_level"] not in ROLE_LEVELS:
        raise ManifestValidationError(f"第 {index} 条 role_level 不在受控分类中")
    if profile["functional_proximity"] not in FUNCTIONAL_PROXIMITIES:
        raise ManifestValidationError(f"第 {index} 条 functional_proximity 不在受控分类中")
    return profile


def _validate_selection_review(row: dict[str, Any], index: int) -> dict[str, Any]:
    review = row.get("selection_review")
    if not isinstance(review, dict):
        raise ManifestValidationError(f"第 {index} 条缺 selection_review")
    summary = review.get("one_line_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ManifestValidationError(f"第 {index} 条 one_line_summary 不能为空")
    caveats = review.get("caveats")
    if not isinstance(caveats, list) or not all(isinstance(item, str) and item.strip() for item in caveats):
        raise ManifestValidationError(f"第 {index} 条 caveats 必须是字符串数组")
    insights = review.get("key_insights")
    if not isinstance(insights, list):
        raise ManifestValidationError(f"第 {index} 条 key_insights 必须是数组")
    for insight_number, insight in enumerate(insights, 1):
        if not isinstance(insight, dict):
            raise ManifestValidationError(f"第 {index} 条第 {insight_number} 个 insight 必须是 object")
        for key in ("insight", "why_it_matters", "anchor_refs"):
            if key not in insight:
                raise ManifestValidationError(
                    f"第 {index} 条第 {insight_number} 个 insight 缺 {key}"
                )
        if not all(
            isinstance(insight[key], str) and insight[key].strip()
            for key in ("insight", "why_it_matters")
        ):
            raise ManifestValidationError(
                f"第 {index} 条第 {insight_number} 个 insight 文本不能为空"
            )
        refs = insight["anchor_refs"]
        if not isinstance(refs, list) or not all(isinstance(ref, int) and ref > 0 for ref in refs):
            raise ManifestValidationError(
                f"第 {index} 条第 {insight_number} 个 anchor_refs 必须是正整数数组"
            )
        if any(ref > len(row.get("anchor_numbers", [])) for ref in refs):
            raise ManifestValidationError(
                f"第 {index} 条第 {insight_number} 个 insight 引用了不存在的 anchor"
            )
    scores = review.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_WEIGHTS):
        raise ManifestValidationError(
            f"第 {index} 条 scores 必须且只能包含：{', '.join(SCORE_WEIGHTS)}"
        )
    for key in SCORE_WEIGHTS:
        item = scores[key]
        if not isinstance(item, dict):
            raise ManifestValidationError(f"第 {index} 条 {key} 评分必须是 object")
        score = item.get("score")
        reason = item.get("reason")
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 5:
            raise ManifestValidationError(f"第 {index} 条 {key}.score 必须是 0–5 整数")
        if not isinstance(reason, str) or not reason.strip():
            raise ManifestValidationError(f"第 {index} 条 {key}.reason 不能为空")
    return review


def _validate_included(row: dict[str, Any], index: int) -> None:
    required = (
        "include", "title", "expert_background", "interview_time", "anchor_numbers",
        "paragraphs", "pdf_name", "pdf_href", "value_reason",
        "inclusion_evidence", "expert_profile", "selection_review", "intel_entries",
    )
    missing = [key for key in required if not _present(row, key)]
    if "left_out" not in row:
        missing.append("left_out")
    if missing:
        raise ManifestValidationError(f"第 {index} 条收录记录缺字段：{', '.join(missing)}")
    text_fields = (
        "title", "expert_background", "interview_time", "pdf_name", "pdf_href", "value_reason",
    )
    invalid_text = [key for key in text_fields if not isinstance(row.get(key), str) or not row[key].strip()]
    if invalid_text:
        raise ManifestValidationError(f"第 {index} 条字段必须是非空字符串：{', '.join(invalid_text)}")
    paragraphs = row["paragraphs"]
    if not isinstance(paragraphs, list) or not 2 <= len(paragraphs) <= 3:
        raise ManifestValidationError(f"第 {index} 条 paragraphs 必须恰为 2–3 段")
    if not all(isinstance(p, str) and p.strip() for p in paragraphs):
        raise ManifestValidationError(f"第 {index} 条 paragraphs 不能含空段")
    for paragraph_number, paragraph in enumerate(paragraphs, 1):
        if not re.search(r"\d|%|％|百分点|倍|一半|三分", paragraph):
            raise ManifestValidationError(
                f"第 {index} 条第 {paragraph_number} 段没有锚定数字；每段至少一个"
            )
    if not isinstance(row["left_out"], list):
        raise ManifestValidationError(f"第 {index} 条 left_out 必须是数组")

    anchors = row["anchor_numbers"]
    if not isinstance(anchors, list) or len(anchors) < 4:
        raise ManifestValidationError(f"第 {index} 条少于 4 个 anchor_numbers，不得收录")
    for number, anchor in enumerate(anchors, 1):
        if not isinstance(anchor, dict):
            raise ManifestValidationError(f"第 {index} 条第 {number} 个 anchor number 必须是 object")
        anchor_fields = ("value", "so_what", "source_quote", "quote_where")
        missing_anchor = [key for key in anchor_fields if not _present(anchor, key)]
        if missing_anchor:
            raise ManifestValidationError(
                f"第 {index} 条第 {number} 个 anchor number 缺：{', '.join(missing_anchor)}"
            )
        invalid_anchor = [
            key for key in anchor_fields
            if not isinstance(anchor.get(key), str) or not anchor[key].strip()
        ]
        if invalid_anchor:
            raise ManifestValidationError(
                f"第 {index} 条第 {number} 个 anchor number 字段必须是非空字符串："
                + ", ".join(invalid_anchor)
            )
        if not _located(anchor["quote_where"]):
            raise ManifestValidationError(
                f"第 {index} 条第 {number} 个 anchor number 的 quote_where 必须含页码/位置"
            )

    evidence = row["inclusion_evidence"]
    if not isinstance(evidence, dict):
        raise ManifestValidationError(f"第 {index} 条 inclusion_evidence 必须是 object")
    unknown = set(evidence) - set(EVIDENCE_KEYS)
    if unknown:
        raise ManifestValidationError(f"第 {index} 条 inclusion_evidence 有未知键：{', '.join(sorted(unknown))}")
    if not bool(evidence.get("quantified_content")):
        raise ManifestValidationError(f"第 {index} 条缺少量化内容证据")
    _relevance_details(evidence, index, required=True)
    _validate_expert_profile(row, index)
    _validate_selection_review(row, index)


def validate_manifest(source: Path | dict[str, Any]) -> dict[str, Any]:
    """Validate every record and return a detached payload."""
    payload = _load_payload(source)
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(
        r"20\d{6}-(?:[01]\d|2[0-3])[0-5]\d[0-5]\d", run_id
    ):
        raise ManifestValidationError("manifest.run_id 必须是 YYYYMMDD-HHMMSS")
    rows = _records(payload)
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("include"), bool):
            raise ManifestValidationError(f"第 {index} 条必须明确给出 boolean include")
        if row["include"]:
            _validate_included(row, index)
        elif not isinstance(row.get("skip_reason"), str) or not row["skip_reason"].strip():
            raise ManifestValidationError(f"第 {index} 条未收录记录必须给非空字符串 skip_reason")
        if "intel_entries" in row and not isinstance(row["intel_entries"], list):
            raise ManifestValidationError(f"第 {index} 条 intel_entries 必须是数组")
    if "intel_entries" in payload and not isinstance(payload["intel_entries"], list):
        raise ManifestValidationError("manifest.intel_entries 必须是数组")
    prepare_intelligence_entries(payload)
    return payload


def _validate_shortlist_candidate(row: dict[str, Any], index: int) -> None:
    required = (
        "title", "expert_background", "interview_time", "pdf_name",
        "anchor_numbers", "inclusion_evidence", "expert_profile", "selection_review",
    )
    missing = [key for key in required if not _present(row, key)]
    if missing:
        raise ManifestValidationError(f"第 {index} 个候选缺字段：{', '.join(missing)}")
    if row.get("include") not in (None, True, False):
        raise ManifestValidationError(f"第 {index} 个候选 include 必须是 true/false/null")
    anchors = row["anchor_numbers"]
    if not isinstance(anchors, list):
        raise ManifestValidationError(f"第 {index} 个候选 anchor_numbers 必须是数组")
    for number, anchor in enumerate(anchors, 1):
        if not isinstance(anchor, dict):
            raise ManifestValidationError(f"第 {index} 个候选第 {number} 个 anchor 必须是 object")
        for key in ("value", "so_what", "source_quote", "quote_where"):
            if not isinstance(anchor.get(key), str) or not anchor[key].strip():
                raise ManifestValidationError(
                    f"第 {index} 个候选第 {number} 个 anchor 的 {key} 不能为空"
                )
        if not _located(anchor["quote_where"]):
            raise ManifestValidationError(
                f"第 {index} 个候选第 {number} 个 anchor 的 quote_where 必须含页码/位置"
            )
    evidence = row["inclusion_evidence"]
    if not isinstance(evidence, dict):
        raise ManifestValidationError(f"第 {index} 个候选 inclusion_evidence 必须是 object")
    unknown = set(evidence) - set(EVIDENCE_KEYS)
    if unknown:
        raise ManifestValidationError(
            f"第 {index} 个候选 inclusion_evidence 有未知键：{', '.join(sorted(unknown))}"
        )
    areas, _reason = _relevance_details(evidence, index, required=False)
    _validate_expert_profile(row, index)
    review = _validate_selection_review(row, index)
    if not areas and review["scores"]["ir_relevance"]["score"] != 0:
        raise ManifestValidationError(
            f"第 {index} 个候选无直接 IR 相关性时，ir_relevance.score 必须为 0"
        )


def validate_shortlist(source: Path | dict[str, Any]) -> dict[str, Any]:
    """Validate a pre-decision candidate manifest where include may be null."""
    payload = _load_payload(source)
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(
        r"20\d{6}-(?:[01]\d|2[0-3])[0-5]\d[0-5]\d", run_id
    ):
        raise ManifestValidationError("manifest.run_id 必须是 YYYYMMDD-HHMMSS")
    for index, row in enumerate(_records(payload), 1):
        if not isinstance(row, dict):
            raise ManifestValidationError(f"第 {index} 个候选必须是 object")
        _validate_shortlist_candidate(row, index)
    return payload


def rank_candidates(source: Path | dict[str, Any]) -> list[dict[str, Any]]:
    """Return a transparent, evidence-backed ranking for human selection."""
    payload = validate_shortlist(source)
    ranked: list[dict[str, Any]] = []
    for row in _records(payload):
        evidence = row["inclusion_evidence"]
        areas, relevance_reason = _relevance_details(evidence, 1, required=False)
        scores = row["selection_review"]["scores"]
        profile = row["expert_profile"]
        total = round(sum(
            scores[key]["score"] * weight / 5
            for key, weight in SCORE_WEIGHTS.items()
        ), 1)
        eligibility_reasons: list[str] = []
        if not areas:
            eligibility_reasons.append("没有直接 IR 信息增量")
        if len(row["anchor_numbers"]) < 4:
            eligibility_reasons.append(f"只有 {len(row['anchor_numbers'])} 个锚定数字，少于 4 个")
        eligible = not eligibility_reasons
        if eligible and total >= 80:
            base_tier = "A"
        elif eligible and total >= 65:
            base_tier = "B"
        else:
            base_tier = "C"
        scope = profile["organization_scope"]
        market_scope = profile["strategic_market_scope"]
        tier_cap = ORGANIZATION_TIER_CAPS[scope]
        if scope == "regional_or_niche" and market_scope == "china_or_apac_priority":
            tier_cap = "B"
        tier_order = {"A": 0, "B": 1, "C": 2}
        tier = base_tier if tier_order[base_tier] >= tier_order[tier_cap] else tier_cap
        tier_cap_reason = ""
        if tier != base_tier:
            if scope == "regional_or_niche" and market_scope == "china_or_apac_priority":
                tier_cap_reason = (
                    "专家来自区域性/细分公司，但直接覆盖 Trip.com 国际扩张重点的"
                    "中国或亚太市场；来源背书较弱，最高为 B 档"
                )
            else:
                tier_cap_reason = (
                    f"专家来自{ORGANIZATION_SCOPES[scope]}，按来源偏好最高为 {tier_cap} 档"
                )
        ranked.append({
            "title": row["title"],
            "pdf_name": row["pdf_name"],
            "expert_background": row["expert_background"],
            "interview_time": row["interview_time"],
            "summary": row["selection_review"]["one_line_summary"],
            "score": total,
            "tier": tier,
            "raw_tier": base_tier,
            "tier_cap": tier_cap,
            "tier_cap_reason": tier_cap_reason,
            "recommendation": TIER_LABELS[tier],
            "expert_profile": {
                **deepcopy(profile),
                "organization_scope_label": ORGANIZATION_SCOPES[scope],
                "strategic_market_scope_label": STRATEGIC_MARKET_SCOPES[market_scope],
            },
            "eligible": eligible,
            "eligibility_reasons": eligibility_reasons,
            "relevance_areas": [RELEVANCE_AREAS[area] for area in areas],
            "relevance_reason": relevance_reason,
            "valuable_data": [deepcopy(anchor) for anchor in row["anchor_numbers"][:5]],
            "key_insights": deepcopy(row["selection_review"]["key_insights"]),
            "caveats": list(row["selection_review"]["caveats"]),
            "score_details": deepcopy(scores),
            "human_decision": (
                "待决定" if row.get("include") is None
                else "选择进入飞书" if row["include"] else "不进入飞书"
            ),
        })
    ranked.sort(key=lambda item: ({"A": 0, "B": 1, "C": 2}[item["tier"]], -item["score"], item["title"]))
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
    return ranked


def _one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def render_shortlist(source: Path | dict[str, Any], target: Path) -> list[dict[str, Any]]:
    """Write the human review report; this stage never renders or publishes callouts."""
    ranked = rank_candidates(source)
    lines = [
        "# Expert Call 精选候选排序",
        "",
        "> 这是辅助人工选择的透明排序，不代表自动发布。只有人工决定 include 后，才进入 callout 草稿。",
        "",
    ]
    for item in ranked:
        lines.extend([
            f"## {item['rank']}. [{item['tier']} · {item['score']:.1f}/100] {_one_line(item['title'])}",
            "",
            f"- **建议**：{item['recommendation']}；**人工决定**：{item['human_decision']}",
            f"- **专家背景**：{_one_line(item['expert_background'])}",
            (
                f"- **专家来源偏好**：{_one_line(item['expert_profile']['organization'])} · "
                f"{item['expert_profile']['organization_scope_label']} · "
                f"{item['expert_profile']['strategic_market_scope_label']} · "
                f"{item['expert_profile']['role_level']} · "
                f"{item['expert_profile']['functional_proximity']}"
            ),
            f"- **身份判断**：{_one_line(item['expert_profile']['assessment'])}",
            f"- **访谈时间**：{_one_line(item['interview_time'])}",
            f"- **大致讲什么**：{_one_line(item['summary'])}",
            f"- **IR 相关范围**：{'、'.join(item['relevance_areas']) or '无直接相关性'}",
            f"- **为什么重要**：{_one_line(item['relevance_reason']) or '未建立直接 IR 信息增量'}",
        ])
        if item["eligibility_reasons"]:
            lines.append(f"- **硬门槛**：未通过（{'；'.join(item['eligibility_reasons'])}）")
        if item["tier_cap_reason"]:
            lines.append(f"- **来源档位上限**：{item['tier_cap_reason']}")
        lines.extend(["", "**关键数据**"])
        if item["valuable_data"]:
            for anchor in item["valuable_data"]:
                lines.append(
                    f"- **{_one_line(anchor['value'])}**：{_one_line(anchor['so_what'])}；"
                    f"原话：{_one_line(anchor['source_quote'])}（{_one_line(anchor['quote_where'])}）"
                )
        else:
            lines.append("- 无足够可核对数字")
        lines.extend(["", "**高参考意义的事实与洞察**"])
        if item["key_insights"]:
            for insight in item["key_insights"]:
                refs = "、".join(str(ref) for ref in insight["anchor_refs"]) or "无数字锚点"
                lines.append(
                    f"- {_one_line(insight['insight'])} —— {_one_line(insight['why_it_matters'])}"
                    f"（锚点 {refs}）"
                )
        else:
            lines.append("- 未识别出足以改变判断的洞察")
        lines.extend(["", "**局限与风险**"])
        if item["caveats"]:
            lines.extend(f"- {_one_line(caveat)}" for caveat in item["caveats"])
        else:
            lines.append("- 未记录；人工选择前应补充核对")
        lines.extend(["", "**评分依据**"])
        for key in SCORE_WEIGHTS:
            detail = item["score_details"][key]
            lines.append(
                f"- `{key}` {detail['score']}/5（权重 {SCORE_WEIGHTS[key]}%）："
                f"{_one_line(detail['reason'])}"
            )
        lines.extend(["", "---", ""])
    write_text(target, "\n".join(lines).rstrip() + "\n")
    return ranked


def extract_pdf(pdf_path: Path, out: Path | None = None) -> Path:
    """Extract page-marked text with pdfplumber; reject image-only/empty PDFs."""
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError("缺少 pdfplumber，无法抽取 PDF") from error

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = (page.extract_text() or "").strip()
            pages.append(f"=== Page {page_number} ===\n{text}")
    if not pages or not any(part.split("\n", 1)[-1].strip() for part in pages):
        raise EmptyOrScannedPDFError(
            f"{pdf_path.name} 没有可提取文本，可能是扫描件或空 PDF；请先 OCR，不能静默继续"
        )
    target = out or pdf_path.with_suffix(".txt")
    write_text(target, "\n\n".join(pages) + "\n")
    return target


def _xml(value: Any) -> str:
    return escape(str(value), quote=True)


def render_callout(record: dict[str, Any], template: Path = TEMPLATE) -> str:
    """Render only the revision-1680 structure, escaping all dynamic XML text."""
    _validate_included(record, 1)
    paragraphs = "".join(f"<p>{_xml(text)}</p>" for text in record["paragraphs"])
    rendered = (
        template.read_text(encoding="utf-8").strip()
        .replace("{{TITLE}}", _xml(record["title"]))
        .replace("{{EXPERT_BACKGROUND}}", _xml(record["expert_background"]))
        .replace("{{INTERVIEW_TIME}}", _xml(record["interview_time"]))
        .replace("{{PARAGRAPH_BLOCKS}}", paragraphs)
        .replace("{{PDF_HREF}}", _xml(record["pdf_href"]))
    )
    if "background-color" in rendered or "<bookmark" in rendered:
        raise RuntimeError("callout 模板偏离 revision 1680：禁止 background-color/bookmark")
    return rendered


def render_manifest(source: Path | dict[str, Any], out_dir: Path) -> list[Path]:
    payload = validate_manifest(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, record in enumerate(_records(payload), 1):
        if not record["include"]:
            continue
        path = out_dir / f"{index:02d}_callout.xml"
        write_text(path, render_callout(record) + "\n")
        written.append(path)
    return written
LarkRunner = Callable[..., dict[str, Any]]


def run_lark(*args: str, executable: str = "lark-cli") -> dict[str, Any]:
    """Run lark-cli as the user with argv and shell disabled."""
    resolved = shutil.which(executable)
    if resolved is None and executable.lower() == "lark-cli":
        resolved = shutil.which("lark-cli.cmd")
    if resolved is None:
        raise RuntimeError(f"找不到 {executable}；请检查 lark-cli 是否已安装并在 PATH 中")

    cli_argv = [resolved, *args]
    if "--as" not in cli_argv:
        cli_argv.extend(["--as", "user"])
    if Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        argv = ["cmd.exe", "/d", "/s", "/c", *cli_argv]
    else:
        argv = cli_argv
    process = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        cwd=Path(__file__).resolve().parents[2],
    )
    if process.returncode:
        raise RuntimeError((process.stderr or process.stdout or "lark-cli failed").strip())
    if not process.stdout.strip():
        raise RuntimeError("lark-cli returned empty output")
    data = json.loads(process.stdout)
    if not data.get("ok", True):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def _content(response: dict[str, Any]) -> str:
    data = response.get("data", response)
    document = data.get("document", data)
    content = document.get("content")
    if not isinstance(content, str):
        raise RuntimeError("lark-cli fetch response 缺 document.content")
    return content


def fetch_document(lark: LarkRunner = run_lark, *, keyword: str | None = None) -> str:
    args = ["docs", "+fetch", "--doc", DOC_TOKEN, "--detail", "full"]
    if keyword:
        args.extend(["--scope", "keyword", "--keyword", keyword])
    return _content(lark(*args))


def _is_red(fragment: str) -> bool:
    if re.search(r'text-color=["\']red["\']', fragment, re.I):
        return True
    for red, green, blue in re.findall(
        r"text-color=[\"']rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)[\"']",
        fragment,
    ):
        if int(red) > int(green) + 30 and int(red) > int(blue) + 30:
            return True
    return False


def resolve_anchor(content: str, heading: str = HEADING) -> str:
    """Resolve the whole grid containing the red, centered h2 heading."""
    containers = [
        (attrs, body, r'\bid=["\']([^"\']+)')
        for attrs, body in re.findall(r'<grid\b([^>]*)>(.*?)</grid>', content, re.I | re.S)
    ]
    containers.extend(
        (attrs, body, r'\btop-block-id=["\']([^"\']+)')
        for attrs, body in re.findall(r'<excerpt\b([^>]*)>(.*?)</excerpt>', content, re.I | re.S)
    )
    for attrs, body, id_pattern in containers:
        container_id = re.search(id_pattern, attrs)
        for h2 in re.finditer(r'<h2\b([^>]*)>(.*?)</h2>', body, re.I | re.S):
            h2_attrs, h2_body = h2.groups()
            centered = re.search(r'(align|text-align)=["\']center["\']', h2_attrs + h2_body, re.I)
            if container_id and centered and heading in unescape(h2_body) and _is_red(h2_attrs + h2_body):
                return container_id.group(1)
    raise RuntimeError("找不到包含红色居中 Expert Call h2 的 grid；未执行写入")
def duplicate_reason(content: str, title: str, pdf_href: str) -> str | None:
    """Detect exact rendered title or exact raw-file link."""
    readable = unescape(content)
    title_pattern = r"<b>\s*" + re.escape(title) + r"\s*</b>"
    if re.search(title_pattern, readable, re.S):
        return "title"
    links = re.findall(r"https?://[^\s<>\"']+", readable)
    if pdf_href and pdf_href in links:
        return "pdf_href"
    return None


def is_duplicate(content: str, title: str, pdf_href: str) -> bool:
    return duplicate_reason(content, title, pdf_href) is not None


def plan_insertions(records: list[dict[str, Any]], content: str) -> list[dict[str, Any]]:
    """Preserve manifest order while removing exact duplicates."""
    planned: list[dict[str, Any]] = []
    seen_content = content
    for record in records:
        if not record.get("include") or is_duplicate(seen_content, record["title"], record["pdf_href"]):
            continue
        planned.append(record)
        seen_content += render_callout(record)
    return planned


def remote_duplicate_reason(record: dict[str, Any], lark: LarkRunner) -> str | None:
    """Use focused Lark reads to find an exact title or exact PDF link."""
    title_content = fetch_document(lark, keyword=record["title"])
    reason = duplicate_reason(title_content, record["title"], record["pdf_href"])
    if reason:
        return reason
    file_token = record["pdf_href"].rstrip("/").rsplit("/", 1)[-1]
    if file_token:
        link_content = fetch_document(lark, keyword=file_token)
        return duplicate_reason(link_content, record["title"], record["pdf_href"])
    return None


def find_callout_block_id(content: str, title: str) -> str | None:
    readable = unescape(content)
    for match in re.finditer(r'<callout\b([^>]*)>(.*?)</callout>', readable, re.I | re.S):
        attrs, body = match.groups()
        if re.search(r"<b>\s*" + re.escape(title) + r"\s*</b>", body, re.S):
            block_id = re.search(r'\b(?:block-id|id)=["\']([^"\']+)', attrs)
            return block_id.group(1) if block_id else None
    return None


def _save_publish_state(
    manifest_path: Path,
    *,
    status: str,
    block_ids: list[str],
    error: str | None = None,
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["publish_result"] = {
        "status": status,
        "written_block_ids": block_ids,
        **({"error": error} if error else {}),
    }
    write_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _collect_intel_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = list(payload.get("intel_entries", []))
    for record in _records(payload):
        if record.get("include"):
            entries.extend(record.get("intel_entries", []))
    return entries
def prepare_intelligence_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the complete intelligence projection before any Lark write."""
    from modules.competitor_intel.entry import Entry, normalize

    raw_entries = _collect_intel_entries(payload)
    if any(record.get("include") for record in _records(payload)) and not raw_entries:
        raise ManifestValidationError(
            "发布前必须提供 intel_entries；statement 必须含原话 quote 与位置 quote_where"
        )
    prepared: list[dict[str, Any]] = []
    for raw in raw_entries:
        row = deepcopy(raw)
        row["channel"] = "expert-call"
        row["sensitivity"] = "internal"
        entry, _unregistered = normalize(Entry.from_dict(row))
        prepared.append(entry.to_dict())
    return prepared


def write_intelligence_draft(
    payload: dict[str, Any],
    target: Path,
    *,
    prepared: list[dict[str, Any]] | None = None,
) -> Path:
    """Write an internal expert-call draft without committing it to the store."""
    entries = prepared if prepared is not None else prepare_intelligence_entries(payload)
    write_text(
        target,
        json.dumps(
            {
                "channel": "expert-call",
                "sensitivity": "internal",
                "committed": False,
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
    )
    return target


def publish_manifest(
    manifest_path: Path,
    base: Paths,
    run_id: str,
    *,
    confirm: bool = False,
    lark: LarkRunner = run_lark,
) -> Result:
    """Plan or sequentially publish records, re-fetching after every write."""
    try:
        payload = validate_manifest(manifest_path)
        prepared_intel = prepare_intelligence_entries(payload)
        anchor_content = fetch_document(lark, keyword=HEADING)
        anchor = resolve_anchor(anchor_content)
        included = [row for row in _records(payload) if row["include"]]
        planned: list[dict[str, Any]] = []
        duplicates: list[str] = []
        batch_content = ""
        for record in included:
            reason = duplicate_reason(
                batch_content, record["title"], record["pdf_href"]
            ) or remote_duplicate_reason(record, lark)
            if reason:
                duplicates.append(record["title"])
                continue
            planned.append(record)
            batch_content += render_callout(record)
    except Exception as error:  # validation/read failures are explicit and side-effect free
        return Result(
            status="blocked",
            summary="发布前检查未通过，未写飞书。",
            domain=DOMAIN,
            period=run_id,
            missing=[str(error)],
        )

    if not confirm:
        return Result(
            status="partial",
            summary=f"发布预演：计划写入 {len(planned)} 条，**未写飞书**。",
            domain=DOMAIN,
            period=run_id,
            checks=[
                {"name": "目标文档", "level": "ok", "detail": DOC_TOKEN},
                {"name": "插入锚点", "level": "ok", "detail": anchor},
                {"name": "精确重复", "level": "warn" if duplicates else "ok", "detail": "、".join(duplicates) or "无"},
            ],
            next_steps=["只有用户明确确认后才可使用发布确认参数。"],
            data={"planned_titles": [row["title"] for row in planned], "written_block_ids": []},
        )

    written_ids: list[str] = []
    written_titles: list[str] = []
    scratch = base.scratch / "expert-calls" / run_id / "callouts"
    scratch.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(planned, 1):
        xml_path = scratch / f"{index:02d}_callout.xml"
        write_text(xml_path, render_callout(record) + "\n")
        try:
            relative_xml = xml_path.resolve().relative_to(base.root.resolve()).as_posix()
            response = lark(
                "docs", "+update", "--doc", DOC_TOKEN,
                "--command", "block_insert_after", "--block-id", anchor,
                "--content", f"@{relative_xml}",
            )
            operation = response.get("data", {}).get("result", "success")
            if operation != "success":
                raise RuntimeError(f"lark-cli update result={operation}")
            verified = fetch_document(lark, keyword=record["title"])
            block_id = find_callout_block_id(verified, record["title"])
            if not block_id or not is_duplicate(verified, record["title"], record["pdf_href"]):
                raise RuntimeError(f"写后回读未找到 callout：{record['title']}")
            written_ids.append(block_id)
            written_titles.append(record["title"])
            anchor = block_id
        except Exception as error:  # preserve every already verified block id
            _save_publish_state(
                manifest_path,
                status="partial" if written_ids else "failed",
                block_ids=written_ids,
                error=str(error),
            )
            return Result(
                status="partial" if written_ids else "failed",
                summary=f"发布在第 {index} 条中断；已验证写入 {len(written_ids)} 条。",
                domain=DOMAIN,
                period=run_id,
                warnings=[str(error)],
                next_steps=["保留 manifest 中的 block id；处理失败项后重跑，精确判重会跳过已写条目。"],
                data={"written_block_ids": written_ids, "written_titles": written_titles},
            )

    try:
        draft = write_intelligence_draft(
            payload,
            base.scratch / "expert-calls" / f"intel-draft-{run_id}.json",
            prepared=prepared_intel,
        )
    except Exception as error:
        _save_publish_state(manifest_path, status="partial", block_ids=written_ids, error=str(error))
        return Result(
            status="partial",
            summary=f"飞书发布完成 {len(written_ids)} 条，但情报草稿校验失败。",
            domain=DOMAIN,
            period=run_id,
            warnings=[str(error)],
            data={"written_block_ids": written_ids},
        )

    _save_publish_state(manifest_path, status="success", block_ids=written_ids)
    return Result(
        status="success",
        summary=f"飞书发布完成 {len(written_ids)} 条；情报仅生成草稿，未入库。",
        domain=DOMAIN,
        period=run_id,
        checks=[
            {"name": "逐条回读", "level": "ok", "detail": f"{len(written_ids)} 个 block id"},
            {"name": "情报库", "level": "ok", "detail": "只生成 draft，committed=false"},
        ],
        data={
            "written_block_ids": written_ids,
            "written_titles": written_titles,
            "duplicates": duplicates,
            "intel_draft": str(draft),
        },
    )


publish = publish_manifest
