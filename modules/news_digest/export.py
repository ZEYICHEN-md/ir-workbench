"""新闻精选 Markdown → 研报风格 HTML，可选一键导出 PDF。

## 这份文件是**照搬**过来的，刻意没有重写

它在旧仓已经出过 4 期成品（含 PDF），排版细节（字体内嵌、页眉页脚、章节锚点、
显著变化高亮）都是一期一期调出来的。重写的收益是代码更整齐，代价是排版可能悄悄变样
而没人立刻发现——对唯一的对外交付物不值得冒这个险。和 `aviation-monthly` 的管道
同一个判断（见 docs/MIGRATION.md 第 2 步）。

改动只有三处：模板路径指向模块内、去掉 import 时改 stdout 编码（由 `workbench.cli` 统一做）、
以及补上这段说明。

## 里面有为五部分周报写的死代码

`_SECTION_CN`、`SUBSECTION_MARKERS` 里的「港股/暑运/Q2 回顾」、`FOOTER_FULL` 都只对
五章格式有意义。五部分周报已停用（见 `digest.py`），这些分支现在走不到。
**没有顺手删**：它们无副作用，而在同一次迁移里既搬又改是把两类风险混在一起。
真要清就单独做一轮，对着导出结果比对。
"""
from __future__ import annotations

import base64
import html as html_module
import re
from pathlib import Path

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent
TEMPLATE_CSS = ROOT / "templates" / "report.css"
FONTS_DIR = ROOT / "templates" / "fonts"

FONT_FILES = [
    ("Noto Sans SC", "noto-sans-sc-400.woff2", 400),
    ("Noto Sans SC", "noto-sans-sc-600.woff2", 600),
    ("Noto Sans SC", "noto-sans-sc-700.woff2", 700),
]

HTML_SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
{css}
  </style>
</head>
<body>
  <div class="page">
    <header class="masthead {masthead_class}">
      <div class="masthead-kicker">Trip.com Group · Investor Relations</div>
      <h1>{title}</h1>
      <div class="masthead-accent" aria-hidden="true"></div>
      <div class="masthead-meta">{meta_html}</div>
    </header>
    <div class="toolbar no-print">
      <button type="button" onclick="window.print()">导出 PDF（浏览器打印）</button>
    </div>
    {toc}
    <main class="content">
{body}
    </main>
    <footer class="disclaimer">
      {footer}
    </footer>
  </div>
</body>
</html>
"""

OVERVIEW_MARKERS = ("本周概览", "本期数据概览", "数据来源")
SUBSECTION_MARKERS = ("Q2 回顾", "暑运", "本周市场态势", "估值与成交占比")
FOOTER_FULL = (
    "本报告仅供 Trip.com Group 内部 IR 参考。数据来源见正文第五节；不构成投资建议。"
)
FOOTER_NEWS = (
    "本精选仅供 Trip.com Group 内部 IR 参考。新闻来源见文末表格；不构成投资建议。"
)
META_NOTE_MARKERS = ("数据边界",)
_SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
SECTION_MARKERS = "一二三四五"
_SECTION_CN = {
    "一": "「一、OTA/旅游行业新闻精选」",
    "二": "「二、行业数据更新」",
    "三": "「三、卖方行业跟踪」",
    "四": "「四、港股市场动态」",
    "五": "「五、新闻来源与数据说明」",
}
_SECTION_PHRASE_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"新闻与\s*§四\s*行情叙事周"), "新闻与港股行情叙事周"),
    (re.compile(r"卖方见\s*§三\s*脚注"), "卖方见「三、卖方行业跟踪」脚注"),
]
_SECTION_COMPOUND_RE = re.compile(r"§([一二三四五])/§([一二三四五])")
_SECTION_SINGLE_RE = re.compile(r"§([一二三四五])")
SIGNIFICANT_CHANGE_PCT = 5.0
SIGNIFICANT_CHANGE_PP = 0.5
PERCENT_TOKEN = re.compile(r"([+-]?\d+(?:\.\d+)?%)")
PP_TOKEN = re.compile(r"([+-]?\d+(?:\.\d+)?pp)")
TREND_PHRASE_PATTERN = re.compile(
    r"("
    r"由正转负|由负转正|转负|转正"
    r"|降幅扩大|降幅收窄|增幅扩大|增幅收窄"
    r"|升至年内[^，。；]{0,16}|降至年内[^，。；]{0,16}"
    r"|走弱|回暖|回升|承压"
    r"|集中入市"
    r"|旅行中断|大面积取消|短时冲击"
    r"|交投降温|活跃度回升|环比缩量|环比放量|放量|缩量"
    r"|跟涨|跑输|跑赢"
    r"|回落至|回升至"
    r")"
)


def _split_front_matter(text: str) -> tuple[str, list[str], str]:
    lines = text.splitlines()
    title = ""
    meta_parts: list[str] = []
    body_start = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
            i += 1
            continue
        if stripped.startswith(">") and not meta_parts:
            while i < len(lines) and lines[i].strip().startswith(">"):
                meta_parts.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body_start = i
            break
        if stripped:
            break
        i += 1
    if not title:
        raise ValueError("未找到报告标题（首行应为 # 标题）")
    body = "\n".join(lines[body_start:]).strip()
    return title, meta_parts, body


def _format_masthead_meta(meta_lines: list[str]) -> str:
    if not meta_lines:
        return ""
    return "".join(
        f'<span class="masthead-meta-line">{html_module.escape(line)}</span>'
        for line in meta_lines
    )


def _masthead_class(title: str) -> str:
    if "新闻精选" in title:
        return "masthead--news"
    return "masthead--full"


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.strip()).strip("-").lower()
    return slug or "section"


def _annotate_tables(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        classes = ["report-table"]
        if any(k in block for k in ("酒店 OCC", "公司", "周期", "L12M")):
            classes.append("data-table")
        if "相对" in block and "55%" in block:
            classes.append("ratio-status-table")
        if "英文原标题" in block:
            classes.append("sources-table")
        class_attr = " ".join(classes)
        return block.replace("<table>", f'<table class="{class_attr}">', 1)

    return re.sub(r"<table>.*?</table>", repl, html, flags=re.DOTALL)


def _overview_label_and_body(text: str) -> tuple[str, str]:
    m = re.match(r"^\s*(.+?[：:])\s*(.*)$", text, flags=re.DOTALL)
    if not m:
        return "概览", text.strip()
    return m.group(1).rstrip("：:") + "：", m.group(2).strip()


def _split_overview_items(body: str) -> list[str]:
    if not body:
        return []
    parts = re.split(r"(?<=[。；])\s*|\n+", body)
    items = [p.strip(" ；。.\n") for p in parts if p.strip(" ；。.\n")]
    return items


def _extract_markdown_list_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        elif stripped.startswith("• "):
            items.append(stripped[2:].strip())
    return items


def _convert_overview_blockquotes(soup: BeautifulSoup) -> None:
    for blockquote in soup.find_all("blockquote"):
        if blockquote.find("ul"):
            ul = blockquote.find("ul")
            ul["class"] = ul.get("class", []) + ["overview-bullets"]
            label_p = blockquote.find("p")
            if label_p and label_p.find("strong"):
                label_p["class"] = label_p.get("class", []) + ["overview-label"]
            continue

        p = blockquote.find("p")
        if not p:
            continue

        full_text = p.get_text("\n", strip=True)
        if not any(m in full_text for m in OVERVIEW_MARKERS):
            continue

        strong = p.find("strong")
        label_text = strong.get_text(strip=True) if strong else ""
        remainder = full_text
        if label_text and remainder.startswith(label_text):
            remainder = remainder[len(label_text) :].strip()

        items = _extract_markdown_list_items(remainder)
        if not items:
            if label_text:
                items = _split_overview_items(remainder)
            else:
                label, body = _overview_label_and_body(full_text)
                label_text = label.rstrip("：:")
                items = _split_overview_items(body)

        items = [re.sub(r"^-\s+", "", item) for item in items if item.strip()]
        if not items:
            continue
        if not label_text:
            label_text = "概览"

        blockquote.clear()
        label_p = soup.new_tag("p", attrs={"class": "overview-label"})
        strong_tag = soup.new_tag("strong")
        strong_tag.string = label_text
        label_p.append(strong_tag)
        blockquote.append(label_p)

        ul = soup.new_tag("ul", attrs={"class": "overview-bullets"})
        for item in items:
            li = soup.new_tag("li")
            li.string = item
            ul.append(li)
        blockquote.append(ul)


def _build_toc(soup: BeautifulSoup) -> str:
    items: list[str] = []
    for index, h2 in enumerate(soup.find_all("h2"), start=1):
        title = h2.get_text(strip=True)
        anchor = _slugify(title)
        h2["id"] = anchor
        classes = list(h2.get("class", []))
        if title.startswith("五、") or "新闻来源与数据说明" in title:
            if "section-appendix" not in classes:
                classes.append("section-appendix")
        elif index > 1 and "section-break" not in classes:
            classes.append("section-break")
        if classes:
            h2["class"] = classes
        items.append(f'<li><a href="#{anchor}">{title}</a></li>')
    if not items:
        return ""
    lis = "\n".join(items)
    return f'<nav class="report-toc" aria-label="目录">\n<p class="toc-title">目录</p>\n<ul>\n{lis}\n</ul>\n</nav>'


def _normalize_headings(soup: BeautifulSoup) -> None:
    for h3 in soup.find_all("h3"):
        text = h3.get_text(strip=True)
        if "新闻来源" in text:
            h3.string = "新闻来源"


def _remove_empty_paragraphs_after_headings(soup: BeautifulSoup) -> None:
    for heading in soup.find_all(["h2", "h3"]):
        sibling = heading.find_next_sibling()
        while sibling is not None and sibling.name == "p":
            classes = sibling.get("class", [])
            if sibling.get_text(strip=True) or "subsection-title" in classes:
                break
            next_sibling = sibling.find_next_sibling()
            sibling.decompose()
            sibling = next_sibling


def _parse_signed_number(token: str) -> float | None:
    cleaned = token.replace("%", "").replace("pp", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _emphasis_markup(text: str) -> str:
    return f'<strong class="text-emphasis">{text}</strong>'


def _apply_trend_emphasis(text: str) -> str:
    return TREND_PHRASE_PATTERN.sub(lambda match: _emphasis_markup(match.group(1)), text)


def _apply_significant_metric_emphasis(text: str) -> str:
    def pct_repl(match: re.Match[str]) -> str:
        value = _parse_signed_number(match.group(1))
        if value is not None and abs(value) >= SIGNIFICANT_CHANGE_PCT:
            return _emphasis_markup(match.group(1))
        return match.group(0)

    text = PERCENT_TOKEN.sub(pct_repl, text)

    def pp_repl(match: re.Match[str]) -> str:
        value = _parse_signed_number(match.group(1))
        if value is not None and abs(value) >= SIGNIFICANT_CHANGE_PP:
            return _emphasis_markup(match.group(1))
        return match.group(0)

    return PP_TOKEN.sub(pp_repl, text)


def _transform_text(text: str, *, include_metrics: bool) -> str:
    updated = _apply_significant_metric_emphasis(text) if include_metrics else text
    return _apply_trend_emphasis(updated)


def _is_skippable_tag(tag: Tag) -> bool:
    if tag.name == "strong":
        return True
    classes = tag.get("class", [])
    return "news-title" in classes or "overview-label" in classes


def _emphasize_in_node(node: Tag, *, include_metrics: bool) -> None:
    for child in list(node.children):
        if isinstance(child, NavigableString):
            raw = str(child)
            if not raw.strip():
                continue
            transformed = _transform_text(raw, include_metrics=include_metrics)
            if transformed != raw:
                child.replace_with(BeautifulSoup(transformed, "html.parser"))
        elif isinstance(child, Tag):
            if _is_skippable_tag(child):
                continue
            _emphasize_in_node(child, include_metrics=include_metrics)


def _emphasize_in_element(element: Tag, *, include_metrics: bool) -> None:
    if element.name == "li":
        if "meta-note" in element.get("class", []):
            return
        if element.find_parent("blockquote", class_="callout-footnote"):
            return
    if element.find_parent("table", class_=lambda classes: classes and "sources-table" in classes):
        return
    _emphasize_in_node(element, include_metrics=include_metrics)


def _collect_emphasis_targets(root: Tag) -> list[Tag]:
    candidates: list[Tag] = []
    if root.name in ("li", "p"):
        candidates.append(root)
    candidates.extend(root.find_all(["li", "p"]))

    targets: list[Tag] = []
    seen: set[int] = set()
    for tag in candidates:
        tag_id = id(tag)
        if tag_id in seen:
            continue
        seen.add(tag_id)
        if tag.name == "p" and "subsection-title" in tag.get("class", []):
            continue
        if tag.find_parent("blockquote", class_="callout-footnote"):
            continue
        if tag.find_parent("table"):
            continue
        targets.append(tag)

    return targets


def _section_number(h2: Tag) -> int | None:
    text = h2.get_text(strip=True)
    if not text or text[0] not in SECTION_MARKERS:
        return None
    return SECTION_MARKERS.index(text[0]) + 1


def _apply_section_emphasis(soup: BeautifulSoup) -> None:
    headings = soup.find_all("h2")
    for index, heading in enumerate(headings):
        section = _section_number(heading)
        if section is None or section >= 5:
            continue
        next_heading = headings[index + 1] if index + 1 < len(headings) else None
        include_metrics = section in (2, 4)
        sibling = heading.find_next_sibling()
        while sibling is not None and sibling is not next_heading:
            if isinstance(sibling, Tag):
                if sibling.name == "blockquote" and "callout-footnote" in sibling.get("class", []):
                    sibling = sibling.find_next_sibling()
                    continue
                for target in _collect_emphasis_targets(sibling):
                    _emphasize_in_element(target, include_metrics=include_metrics)
            sibling = sibling.find_next_sibling()


def _enhance_semantic_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    _convert_overview_blockquotes(soup)
    _normalize_headings(soup)
    _remove_empty_paragraphs_after_headings(soup)
    toc = _build_toc(soup)

    for blockquote in soup.find_all("blockquote"):
        text = blockquote.get_text()
        if any(m in text for m in OVERVIEW_MARKERS):
            classes = blockquote.get("class", [])
            if "callout-overview" not in classes:
                blockquote["class"] = classes + ["callout-overview"]
        else:
            blockquote["class"] = blockquote.get("class", []) + ["callout-footnote"]

    for p in soup.find_all("p"):
        if p.find_parent("blockquote"):
            continue
        strong = p.find("strong", recursive=False)
        if not strong:
            continue
        p_text = p.get_text(strip=True)
        s_text = strong.get_text(strip=True)
        if p_text == s_text:
            if any(s_text.startswith(m) or m in s_text for m in SUBSECTION_MARKERS):
                p["class"] = p.get("class", []) + ["subsection-title"]
            continue
        p["class"] = p.get("class", []) + ["news-item"]
        classes = strong.get("class", [])
        if "news-title" not in classes:
            strong["class"] = classes + ["news-title"]

    for li in soup.find_all("li"):
        if any(m in li.get_text() for m in META_NOTE_MARKERS):
            li["class"] = li.get("class", []) + ["meta-note"]

    _apply_section_emphasis(soup)

    return str(soup), toc


def sanitize_section_symbols(text: str) -> str:
    """Replace internal §-prefixed section refs with reader-facing Chinese chapter names."""
    for pattern, replacement in _SECTION_PHRASE_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    def compound_repl(match: re.Match[str]) -> str:
        left = _SECTION_CN.get(match.group(1), match.group(1))
        right = _SECTION_CN.get(match.group(2), match.group(2))
        return f"{left}与{right}"

    text = _SECTION_COMPOUND_RE.sub(compound_repl, text)
    return _SECTION_SINGLE_RE.sub(
        lambda match: _SECTION_CN.get(match.group(1), match.group(0)),
        text,
    )


def md_to_html_fragment(md_body: str) -> tuple[str, str]:
    md_body = sanitize_section_symbols(md_body)
    html = markdown.markdown(
        md_body,
        extensions=["tables", "sane_lists"],
        output_format="html5",
    )
    html = _annotate_tables(html)
    return _enhance_semantic_html(html)


def _build_font_face_css() -> str:
    rules = []
    for family, filename, weight in FONT_FILES:
        path = FONTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少字体文件: {path}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  src: url(data:font/woff2;base64,{encoded}) format('woff2');\n"
            f"  font-weight: {weight};\n"
            f"  font-style: normal;\n"
            f"  font-display: swap;\n"
            f"}}"
        )
    return "\n\n".join(rules)


def _build_css(*, embed_fonts: bool = True) -> str:
    template_css = TEMPLATE_CSS.read_text(encoding="utf-8")
    if embed_fonts:
        return _build_font_face_css() + "\n\n" + template_css
    return template_css


def _footer_for_title(title: str) -> str:
    if "新闻精选" in title:
        return FOOTER_NEWS
    return FOOTER_FULL


def build_html(md_path: Path, *, embed_fonts: bool = True) -> str:
    text = sanitize_section_symbols(md_path.read_text(encoding="utf-8"))
    title, meta_lines, body = _split_front_matter(text)
    css = _build_css(embed_fonts=embed_fonts)
    body_html, toc = md_to_html_fragment(body)
    return HTML_SHELL.format(
        title=title,
        meta_html=_format_masthead_meta(meta_lines),
        masthead_class=_masthead_class(title),
        css=css,
        toc=toc,
        body=body_html,
        footer=_footer_for_title(title),
    )


def export_html(md_path: Path, html_path: Path | None = None, *, embed_fonts: bool = True) -> Path:
    html_path = html_path or md_path.with_suffix(".html")
    html_path.write_text(build_html(md_path, embed_fonts=embed_fonts), encoding="utf-8")
    return html_path


def export_pdf(html_path: Path, pdf_path: Path | None = None, *, header_label: str | None = None) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "导出 PDF 需要 playwright：pip install playwright && playwright install chromium"
        ) from exc

    pdf_path = pdf_path or html_path.with_suffix(".pdf")
    file_url = html_path.resolve().as_uri()
    label = header_label or "旅行行业周报"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(file_url, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "right": "16mm", "bottom": "20mm", "left": "16mm"},
            display_header_footer=True,
            header_template=(
                '<div style="width:100%;font-size:8px;color:#888;text-align:center;'
                'font-family:Arial,sans-serif;padding:0 16mm;">'
                "Trip.com IR · " + label + "</div>"
            ),
            footer_template=(
                '<div style="width:100%;font-size:8px;color:#888;text-align:center;'
                'font-family:Arial,sans-serif;padding:0 16mm;">'
                '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'
            ),
        )
        browser.close()
    return pdf_path


# 原来的独立命令行入口（`parser()` / `main()`）已删除。工作台里每个域只有一个入口：
# `ir news export`。留着第二个入口的后果在 `aviation-monthly` 上见过——管道被人从
# 命令行直接调，绕过配置锁定的工作簿，写了一份没人看的旧表半年没被发现。
