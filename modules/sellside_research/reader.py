"""按页抽取卖方研报，供 Agent 摘读并保留页码溯源。"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


class ResearchError(ValueError):
    pass


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract(path: Path) -> dict:
    if not path.is_file():
        raise ResearchError(f"找不到研报：{path}")
    if path.suffix.lower() != ".pdf":
        raise ResearchError("卖方研报摘读目前只接受 PDF")
    pages = []
    try:
        with pdfplumber.open(path) as document:
            for number, page in enumerate(document.pages, 1):
                text = clean_text(page.extract_text() or "")
                pages.append({"page": number, "text": text, "chars": len(text)})
    except Exception as error:  # noqa: BLE001 - PDF 库异常需转成人话
        raise ResearchError(f"PDF 无法读取：{error}") from error
    if not pages:
        raise ResearchError("PDF 没有页面")
    nonempty = [page for page in pages if page["text"]]
    if not nonempty:
        raise ResearchError("PDF 没有可提取文字，可能是扫描件；需要 OCR 后再摘读")
    return {
        "source": str(path.resolve()),
        "filename": path.name,
        "page_count": len(pages),
        "text_pages": len(nonempty),
        "chars": sum(page["chars"] for page in pages),
        "pages": pages,
    }


def markdown(payload: dict) -> str:
    lines = [
        f"# 研报按页抽取：{payload['filename']}",
        "",
        f"- 原件：`{payload['source']}`",
        f"- 页数：{payload['page_count']}",
        f"- 有文字页：{payload['text_pages']}",
        "",
        "> 这是摘读底稿，不是可转发成品。每条结论必须回到对应页核对。",
        "",
    ]
    for page in payload["pages"]:
        lines.extend([f"## 第 {page['page']} 页", "", page["text"] or "（本页无可提取文字）", ""])
    return "\n".join(lines)
