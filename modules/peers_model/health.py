"""peers-model 健康检查。"""
from __future__ import annotations

import importlib.util

from workbench.config import Config

from .contracts import load, workbook
from .excel_model import inspect_workbook


def checks(paths) -> list[dict]:
    rows = []
    for company in ("BKNG", "EXPE", "ABNB", "MEITUAN", "TCEL"):
        try:
            contract = load(company)
            path = workbook(contract, Config(paths))
            inspection = inspect_workbook(path, contract)
            missing = inspection["missing"]
            level = "fail" if missing else "ok"
            detail = "缺少：" + "、".join(missing) if missing else path.name
            rows.append({"name": f"{company} Model", "level": level, "detail": detail})
        except Exception as error:  # noqa: BLE001
            rows.append({"name": f"{company} Model", "level": "fail", "detail": str(error)})
    for package, label in (("pdfplumber", "PDF 抽取"), ("win32com", "Excel COM")):
        ok = importlib.util.find_spec(package) is not None
        rows.append({"name": label, "level": "ok" if ok else "fail",
                     "detail": "可用" if ok else f"缺少 {package}"})
    rows.append({"name": "写入边界", "level": "ok", "detail": "只生成 outputs 副本，不覆盖权威 Model"})
    return rows
