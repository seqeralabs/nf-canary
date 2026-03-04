#!/usr/bin/env -S uv run --no-project --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["jinja2"]
# ///

"""
Generate a consolidated Fusion diagnostic report from doctor/bench/objbench outputs.
Produces both JSON and self-contained HTML reports.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional


def load_json_report(path: Optional[str]) -> Dict[str, Any]:
    """Load a JSON report file, return empty dict if path is None.

    Args:
        path: Path to JSON report file, or None

    Returns:
        Parsed JSON dictionary, or dict with "error" key if loading fails
    """
    if not path:
        return {}

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"Report file not found: {path}"}
    except json.JSONDecodeError as e:
        return {"error": f"Malformed JSON in {path}: {str(e)}"}
    except IOError as e:
        return {"error": f"Cannot read {path}: {str(e)}"}


def merge_reports(
    doctor_report: Optional[str] = None,
    bench_report: Optional[str] = None,
    objbench_report: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge individual diagnostic reports into a single combined report.

    Args:
        doctor_report: Path to fusion doctor JSON output
        bench_report: Path to fusion bench JSON output
        objbench_report: Path to fusion objbench JSON output

    Returns:
        Merged report dictionary
    """
    combined = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "reports": {
            "doctor": load_json_report(doctor_report),
            "bench": load_json_report(bench_report),
            "objbench": load_json_report(objbench_report),
        },
    }

    # Compute overall status (fail > warn > pass)
    statuses = []
    for report in combined["reports"].values():
        if report and "error" not in report:
            if "summary" in report:
                statuses.append(report["summary"].get("status", "unknown"))
            # Note: Reports without "summary" are silently ignored in status aggregation

    if "fail" in statuses:
        combined["overall_status"] = "fail"
    elif "warn" in statuses:
        combined["overall_status"] = "warn"
    else:
        combined["overall_status"] = "pass"

    return combined


def render_html(combined_report: Dict[str, Any], template_str: Optional[str] = None, template_path: Optional[str] = None) -> str:
    """
    Render self-contained HTML report from combined data.

    Args:
        combined_report: Merged diagnostic report dictionary
        template_str: The HTML template string (pre-loaded for robustness).
                     If None, will be loaded from template_path or default location.
        template_path: Path to template file (optional, overrides default location)

    Returns:
        HTML string with inline CSS/JS
    """
    from jinja2 import Template

    # Load template if not provided (for backward compatibility with tests)
    if template_str is None:
        template_str = load_template(template_path)

    template = Template(template_str)

    html = template.render(
        timestamp=combined_report.get("timestamp", ""),
        overall_status=combined_report.get("overall_status", "unknown"),
        doctor_report=combined_report.get("reports", {}).get("doctor", {}),
        bench_report=combined_report.get("reports", {}).get("bench", {}),
        objbench_report=combined_report.get("reports", {}).get("objbench", {}),
    )

    return html


def load_template(template_path: Optional[str] = None) -> str:
    """Load the HTML template from assets/templates directory or specified path.

    Args:
        template_path: Optional path to template file. If None, uses default location.

    Returns:
        HTML template string

    Raises:
        FileNotFoundError: If template file is not found
        IOError: If template file cannot be read
    """
    # Use provided path or default location
    if template_path:
        path = Path(template_path)
    else:
        # Go up from bin/ to project root, then into assets/templates
        path = Path(__file__).parent.parent / "assets" / "templates" / "fusion_report_template.html"
    
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"HTML template not found at {path}. "
            "Ensure fusion_report_template.html is in 'assets/templates/' directory."
        )
    except IOError as e:
        raise IOError(f"Cannot read template file {path}: {str(e)}")


def main():
    """Main entry point for report generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate consolidated Fusion diagnostic HTML report"
    )
    parser.add_argument(
        "--doctor", type=str, required=False,
        help="Path to fusion doctor JSON report"
    )
    parser.add_argument(
        "--bench", type=str, required=False,
        help="Path to fusion bench JSON report"
    )
    parser.add_argument(
        "--objbench", type=str, required=False,
        help="Path to fusion objbench JSON report"
    )
    parser.add_argument(
        "--output-html", type=str, default="fusion-report.html",
        help="Output path for HTML report (default: fusion-report.html)"
    )
    parser.add_argument(
        "--output-json", type=str, default="fusion_report.json",
        help="Output path for combined JSON report (default: fusion_report.json)"
    )
    parser.add_argument(
        "--template", type=str, required=False,
        help="Path to HTML template file (optional, uses default if not provided)"
    )

    args = parser.parse_args()

    # Validate that at least one report was provided
    if not any([args.doctor, args.bench, args.objbench]):
        print(
            "ERROR: At least one report must be provided. Use '--doctor', '--bench', or '--objbench'.",
            file=sys.stderr
        )
        sys.exit(1)

    # Load template at startup for early failure detection
    try:
        template_str = load_template(args.template)
    except (FileNotFoundError, IOError) as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Merge all reports
    combined = merge_reports(
        doctor_report=args.doctor,
        bench_report=args.bench,
        objbench_report=args.objbench,
    )

    # Write combined JSON
    try:
        with open(args.output_json, 'w') as f:
            json.dump(combined, f, indent=2)
    except IOError as e:
        print(f"ERROR: Failed to write JSON report to {args.output_json}: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Render and write HTML
    try:
        html = render_html(combined, template_str)
        with open(args.output_html, 'w') as f:
            f.write(html)
    except IOError as e:
        print(f"ERROR: Failed to write HTML report to {args.output_html}: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to render HTML report: {str(e)}", file=sys.stderr)
        sys.exit(1)

    print(f"Reports generated:")
    print(f"  HTML: {args.output_html}")
    print(f"  JSON: {args.output_json}")
    overall_status = combined.get("overall_status", "unknown")
    print(f"  Status: {overall_status.upper()}")

    # Exit with appropriate code based on status
    exit_codes = {"pass": 0, "warn": 0, "fail": 1, "unknown": 1}
    sys.exit(exit_codes.get(overall_status, 1))


if __name__ == "__main__":
    main()
