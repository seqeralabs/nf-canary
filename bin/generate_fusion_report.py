#!/usr/bin/env -S uv run --no-project --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["jinja2==3.1.6", "humanize==4.15.0"]
# ///

"""
Generate a consolidated Fusion diagnostic report from doctor/bench/objbench outputs.
Produces both JSON and self-contained HTML reports.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import humanize
from markupsafe import Markup, escape


def load_json_report(path: str) -> Dict[str, Any]:
    """Load a JSON report file.

    Args:
        path: Path to JSON report file

    Returns:
        Parsed JSON dictionary

    Raises:
        FileNotFoundError: If the report file does not exist
        json.JSONDecodeError: If the file contains malformed JSON
        IOError: If the file cannot be read
    """
    with open(path, 'r') as f:
        return json.load(f)


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
            "doctor": load_json_report(doctor_report) if doctor_report else {},
            "bench": load_json_report(bench_report) if bench_report else {},
            "objbench": load_json_report(objbench_report) if objbench_report else {},
        },
    }

    # Compute overall status using check_summary from schema v2.0
    # "degraded" = all critical checks pass, but some warning-severity checks fail
    statuses = []
    for report in combined["reports"].values():
        if report:
            if "check_summary" in report:
                statuses.append(report["check_summary"].get("overall", "unknown"))
            elif "summary" in report:
                statuses.append(report["summary"].get("status", "unknown"))

    if "fail" in statuses:
        # Use check_summary.criticals when available (v2.0), fall back to check inspection
        has_critical_failure = False
        for report in combined["reports"].values():
            if not report:
                continue
            summary = report.get("check_summary", {})
            if "criticals" in summary:
                has_critical_failure = has_critical_failure or summary.get("criticals", 0) > 0
            else:
                checks = report.get("checks", [])
                if isinstance(checks, list):
                    for c in checks:
                        if c.get("status") == "fail" and c.get("severity", c.get("category")) == "critical":
                            has_critical_failure = True
                            break
                elif isinstance(checks, dict):
                    for c in checks.values():
                        if c.get("status") == "fail" and c.get("severity", c.get("category")) == "critical":
                            has_critical_failure = True
                            break
            if has_critical_failure:
                break

        combined["overall_status"] = "fail" if has_critical_failure else "degraded"
    elif "warn" in statuses:
        combined["overall_status"] = "degraded"
    else:
        combined["overall_status"] = "pass"

    return combined


# --- Constants ---

_SEVERITY_ORDER = {"critical": 0, "warning": 1}

# --- Jinja2 filter/helper functions (module-level for testability) ---


def humanize_check(name, catalog=None):
    """Convert snake_case check names to readable labels using catalog when available."""
    if catalog and name in catalog:
        return catalog[name].get("label", name.replace('_', ' ').title())
    return name.replace('_', ' ').title()


def check_description(name, catalog=None):
    """Look up the description for a check from the catalog."""
    if catalog and name in catalog:
        return catalog[name].get("description", "")
    return ""


def detail_label(key, severity='', requirement_key=None):
    """Label for detail keys, context-dependent on severity."""
    if requirement_key and key == requirement_key:
        if severity == 'critical':
            return 'Required (≥)'
        return 'Recommended (≥)'
    return key.replace('_', ' ').title()


def trim_sub_msg(msg):
    """Strip redundant prefixes from sub-check messages."""
    if not msg or ':' not in msg:
        return msg or ''
    _, _, after = msg.partition(':')
    return after.strip()


def truncate_error(msg, limit=80):
    """Truncate long error messages, keeping the start for context."""
    if not msg or len(msg) <= limit:
        return msg or ''
    return msg[:limit] + '…'


def inline_code(text):
    """Convert `backtick` text to <code> elements, escaping HTML first."""
    if not text:
        return text
    escaped = str(escape(str(text)))
    result = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    return Markup(result)


def _humanize_bytes(b):
    """Format byte counts as human-readable GiB/MiB/KiB."""
    fmt = '%.1f' if b >= 1073741824 else '%.0f'
    return humanize.naturalsize(b, binary=True, format=fmt)


def _format_value(val):
    """Format a value for display: comma separators for numbers, str() for others."""
    if isinstance(val, (int, float)):
        return humanize.intcomma(val)
    return str(val)


def extract_actual(details, value_key=None):
    """Extract the actual/measured value from check details."""
    if not details or not isinstance(details, dict):
        return ''
    if value_key and value_key in details:
        val = details[value_key]
        if 'bytes' in value_key:
            return _humanize_bytes(val)
        return _format_value(val)
    return ''


def extract_reference(details, requirement_key=None):
    """Extract the reference/required value from check details."""
    if not details or not isinstance(details, dict):
        return ''
    if requirement_key and requirement_key in details:
        val = details[requirement_key]
        if 'bytes' in requirement_key:
            return _humanize_bytes(val)
        return str(val)
    return ''


def format_detail_value(val, key=''):
    """Format detail values: humanize bytes, add commas to large numbers."""
    if isinstance(val, (int, float)) and 'bytes' in key.lower():
        return f"{_humanize_bytes(int(val))} ({humanize.intcomma(int(val))})"
    if isinstance(val, int) and val >= 1000:
        return humanize.intcomma(val)
    return val


def _create_jinja_env():
    """Create and configure the Jinja2 environment with all filters and globals."""
    from jinja2 import Environment

    env = Environment(trim_blocks=True, lstrip_blocks=True, autoescape=True)
    env.filters['intcomma'] = lambda v: humanize.intcomma(int(v)) if isinstance(v, (int, float)) else str(v)
    env.filters['inline_code'] = inline_code
    env.filters['trim_sub_msg'] = trim_sub_msg
    env.filters['truncate_error'] = truncate_error
    env.globals['humanize_check'] = humanize_check
    env.globals['check_description'] = check_description
    env.globals['extract_actual'] = extract_actual
    env.globals['extract_reference'] = extract_reference
    env.globals['detail_label'] = detail_label
    env.globals['format_detail_value'] = format_detail_value

    return env


def prepare_template_context(combined_report: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare template context from the combined report without mutating the input.

    Args:
        combined_report: Merged diagnostic report dictionary

    Returns:
        Dictionary of template variables
    """
    doctor_report = combined_report.get("reports", {}).get("doctor", {})

    # Split checks into groups: system, disk, bucket
    _BUCKET_CHECKS = {'bucket_access_rw', 'bucket_access_ro'}
    _DISK_CHECKS = {'disk_space'}
    system_checks = []
    disk_checks = []
    bucket_checks = []

    checks = doctor_report.get("checks", [])
    if isinstance(checks, list):
        for c in checks:
            if c.get("status") == "skip":
                continue
            check_name = c.get("check", c.get("name", ""))
            if check_name in _BUCKET_CHECKS:
                bucket_checks.append(c)
            elif check_name in _DISK_CHECKS:
                disk_checks.append(c)
            else:
                system_checks.append(c)
    elif isinstance(checks, dict):
        system_checks = checks

    # Build flat list of all checks once
    all_checks = list(checks) if isinstance(checks, list) else list(checks.values()) if isinstance(checks, dict) else []

    # Use check_summary.warnings when available; fall back to counting
    check_summary = doctor_report.get("check_summary", {})
    if "warnings" in check_summary:
        warnings_count = check_summary["warnings"]
    else:
        warnings_count = sum(
            1 for c in all_checks
            if c.get("status") == "fail" and c.get("severity", c.get("category")) == "warning"
        )

    # Collect recommendations
    recommendations = []
    seen_remediations = set()
    for c in all_checks:
        if c.get("status") != "pass" and c.get("remediation"):
            rem = c["remediation"]
            if rem not in seen_remediations:
                seen_remediations.add(rem)
                check_name = c.get("check", c.get("name", "Unknown"))
                recommendations.append({
                    "check": check_name,
                    "severity": c.get("severity", c.get("category", "")),
                    "status": c.get("status", ""),
                    "remediation": rem,
                })

    # Sort recommendations: critical first, then warnings
    recommendations.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 2))

    # Extract check_catalog from doctor report
    check_catalog = doctor_report.get("check_catalog", {})

    return {
        "timestamp": combined_report.get("timestamp", ""),
        "overall_status": combined_report.get("overall_status", "unknown"),
        "doctor_report": doctor_report,
        "system_checks": system_checks,
        "disk_checks": disk_checks,
        "bucket_checks": bucket_checks,
        "warnings_count": warnings_count,
        "recommendations": recommendations,
        "check_catalog": check_catalog,
        "bench_report": combined_report.get("reports", {}).get("bench", {}),
        "objbench_report": combined_report.get("reports", {}).get("objbench", {}),
    }


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
    if template_str is None:
        template_str = load_template(template_path)

    env = _create_jinja_env()
    template = env.from_string(template_str)
    context = prepare_template_context(combined_report)

    return template.render(**context)


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
        "--output-json", type=str, default="fusion-report.json",
        help="Output path for combined JSON report (default: fusion-report.json)"
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
    try:
        combined = merge_reports(
            doctor_report=args.doctor,
            bench_report=args.bench,
            objbench_report=args.objbench,
        )
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

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

    overall_status = combined.get("overall_status", "unknown")
    print(f"Reports generated:")
    print(f"  HTML: {args.output_html}")
    print(f"  JSON: {args.output_json}")
    print(f"  Status: {overall_status.upper()}")


if __name__ == "__main__":
    main()
