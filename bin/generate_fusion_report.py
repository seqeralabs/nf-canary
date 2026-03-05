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
    # Supports both legacy "summary.status" and real fusion "check_summary.overall"
    statuses = []
    for report in combined["reports"].values():
        if report and "error" not in report:
            if "check_summary" in report:
                statuses.append(report["check_summary"].get("overall", "unknown"))
            elif "summary" in report:
                statuses.append(report["summary"].get("status", "unknown"))

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
    from jinja2 import Environment

    # Load template if not provided (for backward compatibility with tests)
    if template_str is None:
        template_str = load_template(template_path)

    env = Environment(trim_blocks=True, lstrip_blocks=True)
    env.filters['intcomma'] = lambda v: f"{int(v):,}" if isinstance(v, (int, float)) else str(v)

    # Humanize check names: snake_case identifiers → readable labels
    _CHECK_LABELS = {
        "fuse_device": "FUSE Device",
        "bucket_access_rw": "Bucket Access (read/write)",
        "bucket_access_ro": "Bucket Access (read-only)",
    }
    _ACRONYMS = {"uri", "id", "cpu", "gpu", "io", "os", "ip", "dns", "http", "https", "ssh", "ssl", "tls", "nfs", "api"}

    def humanize_check(name):
        if name in _CHECK_LABELS:
            return _CHECK_LABELS[name]
        words = name.replace('_', ' ').split()
        return ' '.join(w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words)

    env.filters['humanize_check'] = humanize_check

    # Title-case that respects acronyms
    def smart_title(text):
        words = text.replace('_', ' ').split()
        return ' '.join(w.upper() if w.lower() in _ACRONYMS else w.capitalize() for w in words)

    env.filters['smart_title'] = smart_title

    # Strip redundant prefixes from sub-check messages
    # e.g. "check bucket exists: ok" → "ok", "list objects: ok" → "ok"
    # but keep meaningful parts: "access denied (HTTP 403)" stays
    def trim_sub_msg(msg):
        if not msg or ':' not in msg:
            return msg or ''
        _, _, after = msg.partition(':')
        return after.strip()

    env.filters['trim_sub_msg'] = trim_sub_msg

    template = env.from_string(template_str)

    doctor_report = combined_report.get("reports", {}).get("doctor", {})

    # Sort filesystems by usage% descending and filter out zero-size / noise mounts
    storage = doctor_report.get("storage", {})
    if storage.get("filesystems"):
        noise_prefixes = ("/var/snap/", "/snap/")
        noise_types = ("squashfs", "tmpfs")
        filtered = []
        for fs in storage["filesystems"]:
            total = fs.get("total_bytes", 0)
            if total <= 0:
                continue
            mount = fs.get("mount_point", "")
            fs_type = fs.get("type", "")
            if any(mount.startswith(p) for p in noise_prefixes):
                continue
            if fs_type in noise_types and mount != "/tmp":
                continue
            # Attach computed usage% for sorting
            fs["_used_pct"] = ((total - fs.get("available_bytes", 0)) / total) * 100
            filtered.append(fs)
        storage["filesystems"] = sorted(filtered, key=lambda f: f["_used_pct"], reverse=True)

    html = template.render(
        timestamp=combined_report.get("timestamp", ""),
        overall_status=combined_report.get("overall_status", "unknown"),
        doctor_report=doctor_report,
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
