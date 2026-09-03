"""peers-model 的 prepare → plan → apply 编排。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from workbench.config import Config
from workbench.manifest import Manifest
from workbench.result import Result

from . import excel_model, pdf_source
from .contracts import ContractError, load, workbook
from .periods import Period

DOMAIN = "peers-model"
STEPS = ["extract", "facts", "verify", "plan", "apply", "readback", "charts"]


def _context(paths, company: str, period_text: str):
    contract = load(company)
    period = Period.parse(period_text)
    if period is None:
        raise ValueError("期间格式应为 26Q3、26H1 或 FY2026")
    model = workbook(contract, Config(paths))
    run_key = f"{contract.company}-{period.key}"
    manifest = Manifest(paths, DOMAIN, run_key)
    manifest.ensure_steps(STEPS)
    output = paths.outputs(DOMAIN, run_key)
    output.mkdir(parents=True, exist_ok=True)
    return contract, period, model, run_key, manifest, output


def inspect(paths, company: str) -> Result:
    try:
        contract = load(company)
        model = workbook(contract, Config(paths))
        payload = excel_model.inspect_workbook(model, contract)
    except (ContractError, ValueError, excel_model.ModelError) as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)
    missing = payload["missing"]
    return Result(
        status="blocked" if missing else "success",
        summary="模型合同检查通过。" if not missing else "模型合同缺少工作表。",
        domain=DOMAIN, missing=missing,
        checks=[{"name": "工作簿", "level": "ok" if not missing else "fail", "detail": model.name}],
        data=payload,
    )


def prepare(paths, company: str, period_text: str, pdf_paths: list[str]) -> Result:
    try:
        contract, period, model, run_key, manifest, output = _context(paths, company, period_text)
        pdfs = [Path(p).resolve() for p in pdf_paths]
        extracts = []
        for index, pdf in enumerate(pdfs, 1):
            payload = pdf_source.extract_first_pass(pdf)
            destination = output / f"source-{index}.extract.json"
            pdf_source.write_extract(payload, destination)
            extracts.append(destination)
            manifest.record_input(f"pdf_{index}", pdf)
        template = excel_model.build_template(model, contract, period, pdfs)
        facts_path = output / "facts.template.json"
        facts_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.record_input("model", model)
        manifest.record_output("facts_template", facts_path)
        manifest.set_step("extract", "done", result_data={"pdfs": len(pdfs), "extracts": len(extracts)})
        manifest.set_step("facts", "running", note="等待 Agent 按 PDF 填写 facts 模板")
        return Result(
            status="partial", summary="PDF 第一遍抽取完成，已生成逐行 facts 模板。",
            domain=DOMAIN, period=run_key,
            checks=[
                {"name": "PDF", "level": "ok", "detail": f"{len(pdfs)} 份"},
                {"name": "facts 模板", "level": "ok", "detail": str(facts_path)},
            ],
            next_steps=[
                "Agent 按原始 PDF 填写 facts；每个 disclosed 数必须带页码、原话和数值文本。",
                "填写后运行 plan，系统会独立重新打开 PDF 做第二遍验证。",
            ],
            data={"facts": str(facts_path), "extracts": [str(p) for p in extracts]},
        )
    except (ContractError, ValueError, pdf_source.EvidenceError, excel_model.ModelError) as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)


def _verified_plan(paths, company: str, period_text: str, facts_file: str, *, skip_pdf: bool = False):
    contract, period, model, run_key, manifest, output = _context(paths, company, period_text)
    facts_path = Path(facts_file).resolve()
    facts = pdf_source.load_facts(facts_path)
    if facts.get("company") != contract.company or facts.get("period") != period.key:
        raise ValueError("facts 的 company/period 与命令不一致")
    if skip_pdf:
        findings = [{"ok": True, "skipped": "replay"}]
    else:
        findings = pdf_source.verify_facts(facts, variant="layout")
        failures = [item for item in findings if not item["ok"]]
        if failures:
            report = output / "pdf-verification.json"
            report.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest.set_step("verify", "blocked", note=f"{len(failures)} 条证据未通过")
            raise pdf_source.EvidenceError(f"PDF 第二遍复核有 {len(failures)} 条未通过；见 {report}")
    plan_payload = excel_model.build_plan(model, contract, period, facts)
    plan_payload["facts_file"] = str(facts_path)
    plan_payload["pdf_verification"] = findings
    plan_path = output / "plan.json"
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.record_input("facts", facts_path)
    manifest.record_output("plan", plan_path)
    manifest.set_step("facts", "done")
    manifest.set_step("verify", "done", result_data={"facts": len(findings)})
    manifest.set_step("plan", "done", result_data={"operations": len(plan_payload["operations"])})
    return contract, period, model, run_key, manifest, output, facts, plan_payload, plan_path


def plan(paths, company: str, period_text: str, facts_file: str) -> Result:
    try:
        _, _, _, run_key, _, _, _, payload, plan_path = _verified_plan(
            paths, company, period_text, facts_file)
        writes = sum(len(item["writes"]) for item in payload["operations"])
        return Result(
            status="partial", summary=f"零写入计划已生成：{writes} 个硬编码单元格。",
            domain=DOMAIN, period=run_key,
            checks=[
                {"name": "PDF 第二遍复核", "level": "ok", "detail": f"{writes} 条写入证据通过"},
                {"name": "计划", "level": "ok", "detail": str(plan_path)},
            ],
            next_steps=["核对计划后明确同意写入模型副本；原始 Model 不会被覆盖。说「确认写入模型副本」。"],
            data=payload,
        )
    except (ContractError, ValueError, pdf_source.EvidenceError, excel_model.ModelError) as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)


def apply(paths, company: str, period_text: str, facts_file: str, *, confirmed: bool) -> Result:
    if not confirmed:
        return Result(
            status="blocked", summary="尚未获得模型副本写入确认。", domain=DOMAIN,
            next_steps=["在已明确说明目标和影响后，说「确认写入模型副本」。原始 Model 不会被覆盖。"],
        )
    try:
        contract, period, model, run_key, manifest, output, facts, payload, _ = _verified_plan(
            paths, company, period_text, facts_file)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = output / f"{model.stem}_{period.key}_updated_{stamp}{model.suffix}"
        audit = excel_model.apply_plan(model, destination, contract, period, payload)

        post_pdf = pdf_source.verify_facts(facts, variant="plain")
        post_failures = [item for item in post_pdf if not item["ok"]]
        audit["post_write_pdf_verification"] = post_pdf
        if post_failures:
            audit["errors"].append(f"写后独立 PDF 复核有 {len(post_failures)} 条失败")
            audit["passed"] = False

        audit_path = output / f"audit-{stamp}.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        if not audit["passed"]:
            manifest.set_step("apply", "failed", note="写后审计失败；原始 Model 未改")
            return Result(
                status="failed", summary="副本已生成，但写后审计未通过；原始 Model 未改。",
                domain=DOMAIN, period=run_key, warnings=audit["errors"],
                data={"output": str(destination), "audit": str(audit_path)},
            )
        manifest.record_output("model_copy", destination)
        manifest.record_output("audit", audit_path)
        manifest.set_step("apply", "done")
        manifest.set_step("readback", "done", result_data={"cells": len(audit["checks"])})
        manifest.set_step("charts", "done", result_data={
            "series": audit["charts"]["readback"]["series_checked"]})
        return Result(
            status="success",
            summary="Model 副本更新并通过关闭重开、PDF 与 Charts 审计；原始 Model 未改。",
            domain=DOMAIN, period=run_key,
            checks=[
                {"name": "输出副本", "level": "ok", "detail": str(destination)},
                {"name": "写后审计", "level": "ok", "detail": str(audit_path)},
            ],
            data={"output": str(destination), "audit": audit},
        )
    except (ContractError, ValueError, pdf_source.EvidenceError, excel_model.ModelError) as error:
        return Result(status="blocked", summary=str(error), domain=DOMAIN)
