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
import copy
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import humanize


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

    # Compute overall status (fail > degraded > warn > pass)
    # "degraded" = all critical checks pass, but some warning-category checks fail
    # Supports both legacy "summary.status" and real fusion "check_summary.overall"
    statuses = []
    for report in combined["reports"].values():
        if report and "error" not in report:
            if "check_summary" in report:
                statuses.append(report["check_summary"].get("overall", "unknown"))
            elif "summary" in report:
                statuses.append(report["summary"].get("status", "unknown"))

    if "fail" in statuses:
        # Check if failures are only in warning-category checks
        has_critical_failure = False
        for report in combined["reports"].values():
            if not report or "error" in report:
                continue
            checks = report.get("checks", [])
            if isinstance(checks, list):
                for c in checks:
                    if c.get("status") == "fail" and c.get("category") == "critical":
                        has_critical_failure = True
                        break
            elif isinstance(checks, dict):
                for c in checks.values():
                    if c.get("status") == "fail" and c.get("category") == "critical":
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


# --- Jinja2 filter/helper functions (module-level for testability) ---

_CHECK_LABELS = {
    "fuse_device": "FUSE Device",
    "bucket_access_rw": "Bucket Access (read/write)",
    "bucket_access_ro": "Bucket Access (read-only)",
    "nvme": "NVMe",
    "cpu_cores": "CPU Cores",
    "open_files": "Open Files",
    "kernel_version": "Kernel Version",
}
_ACRONYMS = {"uri", "id", "cpu", "gpu", "io", "os", "ip", "dns", "http", "https", "ssh", "ssl", "tls", "nfs", "api", "nvme"}


def humanize_check(name):
    """Convert snake_case check names to readable labels."""
    if name in _CHECK_LABELS:
        return _CHECK_LABELS[name]
    words = name.replace('_', ' ').split()
    return ' '.join(w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words)


def smart_title(text):
    """Title-case that respects acronyms."""
    words = text.replace('_', ' ').split()
    return ' '.join(w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words)


_REQUIREMENT_KEYS = {'required_min', 'required_bytes', 'cores_required'}


def detail_label(key, category=''):
    """Label for detail keys, context-dependent on severity."""
    if key in _REQUIREMENT_KEYS:
        if category == 'critical':
            return 'Required (≥)'
        return 'Recommended (≥)'
    return smart_title(key)


def trim_sub_msg(msg):
    """Strip redundant prefixes from sub-check messages."""
    if not msg or ':' not in msg:
        return msg or ''
    _, _, after = msg.partition(':')
    return after.strip()


def truncate_error(msg, limit=80):
    """Truncate long error messages to the actionable portion."""
    if not msg or len(msg) <= limit:
        return msg or ''
    lower = msg.lower()
    idx = lower.find('api error')
    if idx != -1:
        after = msg[idx + len('api error'):].lstrip(' :')
        return after if after else msg[:limit] + '…'
    sc_match = re.search(r'StatusCode:\s*(\d+)', msg)
    if sc_match:
        return f"HTTP {sc_match.group(1)}"
    return msg[:limit] + '…'


def inline_code(text):
    """Convert `backtick` text to <code> elements, escaping HTML first."""
    from markupsafe import Markup, escape
    if not text:
        return text
    escaped = str(escape(str(text)))
    result = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    return Markup(result)


def _humanize_bytes(b):
    """Format byte counts as human-readable GiB/MiB/KiB."""
    fmt = '%.1f' if b >= 1073741824 else '%.0f'
    return humanize.naturalsize(b, binary=True, format=fmt)


def _format_number(val):
    """Format integers with comma separators."""
    if isinstance(val, (int, float)):
        return humanize.intcomma(val)
    return str(val)


_ACTUAL_KEYS = ['kernel_version', 'cores_available', 'soft_limit', 'devices_found']
_REFERENCE_KEYS = ['required_min', 'required_bytes', 'cores_required']


def extract_actual(details):
    """Extract the actual/measured value from check details."""
    if not details or not isinstance(details, dict):
        return ''
    for key in _ACTUAL_KEYS:
        if key in details:
            return _format_number(details[key])
    if 'total_bytes' in details:
        return _humanize_bytes(details['total_bytes'])
    return ''


def extract_reference(details):
    """Extract the reference/required value from check details."""
    if not details or not isinstance(details, dict):
        return ''
    for key in _REFERENCE_KEYS:
        if key in details:
            val = details[key]
            if 'bytes' in key:
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
    env.filters['humanize_check'] = humanize_check
    env.filters['smart_title'] = smart_title
    env.filters['trim_sub_msg'] = trim_sub_msg
    env.filters['truncate_error'] = truncate_error
    env.filters['extract_actual'] = extract_actual
    env.filters['extract_reference'] = extract_reference
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
    doctor_report = copy.deepcopy(combined_report.get("reports", {}).get("doctor", {}))

    # Compute usage% for each filesystem (for usage bar rendering)
    storage = doctor_report.get("storage", {})
    if storage.get("filesystems"):
        for fs in storage["filesystems"]:
            total = fs.get("total_bytes", 0)
            if total > 0:
                fs["_used_pct"] = ((total - fs.get("available_bytes", 0)) / total) * 100
            else:
                fs["_used_pct"] = 0

    # Split checks into groups: system, disk, bucket
    _BUCKET_CHECKS = {'bucket_access_rw', 'bucket_access_ro'}
    _DISK_CHECKS = {'disk_space'}
    system_checks = []
    disk_checks = []
    bucket_checks = []

    checks = doctor_report.get("checks", [])
    if isinstance(checks, list):
        for c in checks:
            check_name = c.get("check", c.get("name", ""))
            if check_name in _BUCKET_CHECKS:
                bucket_checks.append(c)
            elif check_name in _DISK_CHECKS:
                disk_checks.append(c)
            else:
                system_checks.append(c)
    elif isinstance(checks, dict):
        system_checks = checks

    # Count warning-category failures and collect recommendations
    warnings_count = 0
    recommendations = []
    all_checks = []
    if isinstance(checks, list):
        all_checks = checks
    elif isinstance(checks, dict):
        all_checks = checks.values()
    seen_remediations = set()
    for c in all_checks:
        if c.get("status") == "fail" and c.get("category") == "warning":
            warnings_count += 1
        if c.get("status") != "pass" and c.get("remediation"):
            rem = c["remediation"]
            if rem not in seen_remediations:
                seen_remediations.add(rem)
                check_name = c.get("check", c.get("name", "Unknown"))
                recommendations.append({
                    "check": check_name,
                    "category": c.get("category", ""),
                    "status": c.get("status", ""),
                    "remediation": rem,
                })

    # Sort recommendations: critical first, then warnings
    _CATEGORY_ORDER = {"critical": 0, "warning": 1}
    recommendations.sort(key=lambda r: _CATEGORY_ORDER.get(r["category"], 2))

    return {
        "timestamp": combined_report.get("timestamp", ""),
        "overall_status": combined_report.get("overall_status", "unknown"),
        "doctor_report": doctor_report,
        "system_checks": system_checks,
        "disk_checks": disk_checks,
        "bucket_checks": bucket_checks,
        "warnings_count": warnings_count,
        "recommendations": recommendations,
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

    overall_status = combined.get("overall_status", "unknown")
    print(f"Reports generated:")
    print(f"  HTML: {args.output_html}")
    print(f"  JSON: {args.output_json}")
    print(f"  Status: {overall_status.upper()}")


if __name__ == "__main__":
    main()
