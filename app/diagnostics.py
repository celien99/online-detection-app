"""Command line entry point for production diagnostics."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.infrastructure.config_store import ConfigStore
from app.services.diagnostics import DiagnosticReport, ProductionDiagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run production readiness diagnostics.")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    config = ConfigStore(str(config_path))
    report = ProductionDiagnostics(config, config_path).run()
    if args.json:
        print(report.to_json())
    else:
        print(_format_report(report))
    return 1 if report.status == "FAIL" else 0


def _format_report(report: DiagnosticReport) -> str:
    lines = [f"Production diagnostics: {report.status}", ""]
    for item in report.items:
        lines.append(f"[{item.status}] {item.name}: {item.message}")
        if item.suggestion:
            lines.append(f"  建议: {item.suggestion}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
