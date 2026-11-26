#!/usr/bin/env python3
"""Package an unchanged Archify report with the offline trade-review chart."""
from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path


CHART_STYLE = """
:root{color-scheme:dark;--font-size-base:15px;--background:#10141c;--foreground:#edf2f7;--muted-foreground:#96a4b6;--border:#303b4c;--orange:#f5a544;--green:#39c598;--red:#f2737e;--purple:#b7a1f5;--blue:#7caef5;--surface:#1a2230}
:root[data-theme=light]{color-scheme:light;--background:#ffffff;--foreground:#172335;--muted-foreground:#5c6a7c;--border:#d9e1eb;--orange:#b96808;--green:#00865c;--red:#c3344b;--purple:#7950c5;--blue:#276ab6;--surface:#f3f6fa}
*{box-sizing:border-box}body{margin:0;padding:24px;background:var(--background);color:var(--foreground);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}h2{font-size:21px;line-height:1.4;margin:0}button,select,input{font:inherit}button,select{color:var(--foreground);background:var(--surface);border:1px solid var(--border);border-radius:7px}button{cursor:pointer;padding:7px 12px}button:hover{border-color:var(--blue)}button:disabled{opacity:.4;cursor:default}button:focus-visible,select:focus-visible{outline:2px solid var(--blue);outline-offset:3px}select{padding:7px 32px 7px 10px;max-width:100%;min-width:0}.viz-controls{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.form-label{display:grid;gap:4px;min-width:0}.form-check{display:flex;align-items:center;gap:7px;align-self:center}.form-check input{accent-color:var(--blue)}.viz-row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.text-small{font-size:13px}.text-muted{color:var(--muted-foreground)}.tabular-nums{font-variant-numeric:tabular-nums}.table-responsive{width:100%;min-width:0}.table{width:100%;border-collapse:collapse;font-size:13px}.table th,.table td{border-bottom:1px solid var(--border);padding:8px 10px;text-align:left;vertical-align:top}.table th{font-weight:600;color:var(--muted-foreground)}.table td:first-child{width:24%}.table td:last-child{width:55px;white-space:nowrap}a{color:var(--blue)}#eth-review-error{padding:16px;color:var(--red);border:1px solid var(--red)}@media(max-width:600px){body{padding:14px}h2{font-size:18px}.viz-controls{gap:8px}.form-label{width:100%}.form-select{width:100%}.table th,.table td{padding:7px 5px;font-size:12px}.table td:first-child{width:28%}}
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def script_json(value: str) -> str:
    # Escape HTML-sensitive characters because these JSON literals live in script.
    return (json.dumps(value, ensure_ascii=False).replace("&", "\\u0026")
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart-fragment", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", default="ETHUSDT 三天回测复核")
    parser.add_argument("--period-label", default="2026-11-15 — 2026-11-17 · 北京时间 · 币安 USDT 永续 · 5 分钟")
    parser.add_argument("--shell", type=Path,
                        default=Path(__file__).with_name("archify_review_shell.template.html"))
    args = parser.parse_args()
    report_hash = digest(args.report)
    delivery = args.report.with_suffix(".delivery.json")
    receipt = json.loads(delivery.read_text())
    if receipt["artifact"]["sha256"] != report_hash:
        raise ValueError("Archify report no longer matches its delivery receipt")
    fragment = args.chart_fragment.read_text(encoding="utf-8")
    if "<script src=" in fragment or "__TRADE_DATA_JSON__" in fragment:
        raise ValueError("chart fragment must bundle its library and data")
    chart = ('<!doctype html><html lang="zh-CN" data-theme="dark"><head>'
             '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             '<title>' + escape(args.title) + '</title><style>' + CHART_STYLE +
             '</style></head><body>' + fragment + '</body></html>')
    shell = args.shell.read_text(encoding="utf-8")
    for token, count in (("__REVIEW_TITLE_HTML__", 2), ("__REVIEW_PERIOD_HTML__", 1)):
        if shell.count(token) != count:
            raise ValueError(f"expected exactly {count} {token}")
    shell = shell.replace("__REVIEW_TITLE_HTML__", escape(args.title))
    shell = shell.replace("__REVIEW_PERIOD_HTML__", escape(args.period_label))
    for token in ("__CHART_DOCUMENT_JSON__", "__EXPLAINER_DOCUMENT_JSON__"):
        if shell.count(token) != 1:
            raise ValueError(f"expected exactly one {token}")
    result = shell.replace("__CHART_DOCUMENT_JSON__", script_json(chart))
    result = result.replace("__EXPLAINER_DOCUMENT_JSON__",
                            script_json(args.report.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    chart_path = args.output.with_name("trade-chart.html")
    chart_path.write_text(chart, encoding="utf-8")
    manifest = {
        "artifact": str(args.output.resolve()), "artifact_sha256": digest(args.output),
        "title": args.title, "period_label": args.period_label,
        "chart_fragment": str(args.chart_fragment.resolve()),
        "chart_fragment_sha256": digest(args.chart_fragment),
        "chart_document": str(chart_path.resolve()), "chart_document_sha256": digest(chart_path),
        "archify_report": str(args.report.resolve()), "archify_report_sha256": report_hash,
        "archify_delivery_receipt": str(delivery.resolve()),
        "scope": "Report source has Archify delivery provenance; the custom shell adds runtime presentation styles and is checked separately.",
    }
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if digest(args.report) != report_hash:
        raise ValueError("packaging unexpectedly changed Archify report")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
