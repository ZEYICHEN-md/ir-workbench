"""Ticker/quarter path resolution for peers-appendix.

The frozen repository used ``companies/`` and ``derived/drafts/``.  In the
workbench, raw materials are inputs, generated work is outputs, and execution
evidence is kept under runs:

``inputs/peers-appendix/<TICKER>/<YYQn>/``
``outputs/peers-appendix/<TICKER>/<YYQn>/``
``runs/peers-appendix/<YYQn>/``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workbench import domains
from workbench.paths import Paths

DOMAIN = "peers-appendix"
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")


def normalize_ticker(value: str) -> str:
    ticker = (value or "").strip().upper()
    if not _TICKER_RE.fullmatch(ticker):
        raise ValueError(
            f"ticker 格式不对：{value!r}；只接受 1–12 位大写字母、数字、点或连字符。"
        )
    return ticker


def validate_period(period: str) -> str:
    if not domains.get(DOMAIN).validate_period(period):
        raise ValueError(f"季度键格式不对：{period!r}；应形如 26Q2。")
    return period


def full_quarter(period: str) -> str:
    validate_period(period)
    return f"20{period}"


@dataclass(frozen=True)
class CompanyQuarterView:
    """All durable paths for one company and fiscal quarter."""

    base: Paths
    ticker: str
    period: str

    @property
    def quarter(self) -> str:
        return full_quarter(self.period)

    @property
    def materials_dir(self) -> Path:
        return self.base.inputs(DOMAIN) / self.ticker / self.period

    @property
    def output_dir(self) -> Path:
        return self.base.outputs(DOMAIN) / self.ticker / self.period

    @property
    def run_dir(self) -> Path:
        return self.base.runs(DOMAIN, self.period) / self.ticker

    @property
    def snapshot(self) -> Path:
        return self.materials_dir / "ir_snapshot.json"

    @property
    def snapshot_markdown(self) -> Path:
        return self.output_dir / "ir_snapshot.md"

    @property
    def fill(self) -> Path:
        return self.materials_dir / "fill_inputs.json"

    @property
    def strategy_decision(self) -> Path:
        return self.materials_dir / "strategy_decision.json"

    @property
    def source_model(self) -> Path:
        return self.materials_dir / "source_model.xlsx"

    @property
    def template(self) -> Path:
        return self.materials_dir / "template.docx"

    @property
    def texts(self) -> Path:
        return self.materials_dir / "texts.json"

    @property
    def input_chart_map(self) -> Path:
        return self.materials_dir / "chart_map.json"

    @property
    def model(self) -> Path:
        return self.output_dir / "model" / (
            f"peers_data_comparison_{self.ticker}_{self.period}_work.xlsx"
        )

    @property
    def audit_report(self) -> Path:
        return self.run_dir / "model_audit.json"

    @property
    def charts_gate_report(self) -> Path:
        return self.run_dir / "charts_gate.json"

    @property
    def chart_dir(self) -> Path:
        return self.output_dir / "charts"

    @property
    def generated_chart_map(self) -> Path:
        return self.output_dir / "chart_map.json"

    @property
    def chart_map(self) -> Path:
        """Prefer a human-supplied map; EXPE may generate the known map."""
        if self.input_chart_map.is_file():
            return self.input_chart_map
        return self.generated_chart_map

    @property
    def brief(self) -> Path:
        return self.output_dir / "writing_brief.json"

    @property
    def writing_gate_report(self) -> Path:
        return self.run_dir / "writing_gate.json"

    @property
    def applied_docx(self) -> Path:
        return self.output_dir / f"{self.ticker} {self.period} 业绩总结_applied.docx"

    @property
    def docx(self) -> Path:
        return self.output_dir / f"{self.ticker} {self.period} 业绩总结.docx"

    @property
    def docx_gate_report(self) -> Path:
        return self.run_dir / "docx_gate.json"

    def ensure_directories(self) -> None:
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "period": self.period,
            "quarter": self.quarter,
            "materials_dir": str(self.materials_dir),
            "outputs_dir": str(self.output_dir),
            "run_dir": str(self.run_dir),
            "required_human_inputs": {
                "ir_snapshot": str(self.snapshot),
                "fill_inputs": str(self.fill),
                "strategy_decision": str(self.strategy_decision),
                "texts": str(self.texts),
            },
            "mechanical_inputs": {
                "source_model": str(self.source_model),
                "template": str(self.template),
                "chart_map_if_needed": str(self.input_chart_map),
            },
            "outputs": {
                "model": str(self.model),
                "charts": str(self.chart_dir),
                "brief": str(self.brief),
                "docx": str(self.docx),
            },
        }


def resolve_view(base: Paths, ticker: str, period: str) -> CompanyQuarterView:
    return CompanyQuarterView(base, normalize_ticker(ticker), validate_period(period))
