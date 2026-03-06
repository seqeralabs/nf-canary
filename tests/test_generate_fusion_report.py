#!/usr/bin/env -S uv run --no-project --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest==9.0.2", "jinja2==3.1.6", "humanize==4.15.0"]
# ///

"""
Unit tests for generate_fusion_report.py
Tests load_json_report, merge_reports, render_html, and status aggregation logic.
"""

import json
import sys
from pathlib import Path

import pytest
from generate_fusion_report import (
    load_json_report,
    merge_reports,
    render_html,
    load_template,
    main,
    humanize_check,
    smart_title,
    detail_label,
    trim_sub_msg,
    truncate_error,
    inline_code,
    extract_actual,
    extract_reference,
    format_detail_value,
    _humanize_bytes,
    _format_number,
    prepare_template_context,
)


@pytest.fixture
def write_reports(tmp_path):
    """Helper fixture to write JSON report files and return their paths."""
    def _write(**reports):
        paths = {}
        for name, data in reports.items():
            p = tmp_path / f"{name}.json"
            p.write_text(json.dumps(data))
            paths[name] = str(p)
        return paths
    return _write


class TestLoadJsonReport:
    """Test cases for load_json_report function."""

    def test_load_valid_json(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text(json.dumps({"status": "pass", "message": "All checks passed"}))
        result = load_json_report(str(path))
        assert result == {"status": "pass", "message": "All checks passed"}

    def test_load_none_path(self):
        assert load_json_report(None) == {}

    def test_load_empty_string_path(self):
        assert load_json_report("") == {}

    def test_load_missing_file(self):
        result = load_json_report("/nonexistent/path/file.json")
        assert "error" in result
        assert "not found" in result["error"]

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{invalid json content")
        result = load_json_report(str(path))
        assert "error" in result
        assert "Malformed JSON" in result["error"]

    def test_load_empty_json_file(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("")
        result = load_json_report(str(path))
        assert "error" in result

    def test_load_complex_json(self, tmp_path):
        test_data = {
            "summary": {"status": "warn"},
            "checks": {
                "check1": {"status": "pass", "message": "OK"},
                "check2": {"status": "fail", "message": "Failed"},
            },
            "version": "v1.5.0",
        }
        path = tmp_path / "complex.json"
        path.write_text(json.dumps(test_data))
        result = load_json_report(str(path))
        assert result == test_data
        assert result["summary"]["status"] == "warn"


class TestMergeReports:
    """Test cases for merge_reports function."""

    def test_merge_all_pass(self, write_reports):
        paths = write_reports(
            doctor={"summary": {"status": "pass"}},
            bench={"summary": {"status": "pass"}},
            objbench={"summary": {"status": "pass"}},
        )
        result = merge_reports(paths["doctor"], paths["bench"], paths["objbench"])
        assert result["overall_status"] == "pass"

    def test_merge_with_warning(self, write_reports):
        paths = write_reports(
            doctor={"summary": {"status": "pass"}},
            bench={"summary": {"status": "warn"}},
            objbench={"summary": {"status": "pass"}},
        )
        result = merge_reports(paths["doctor"], paths["bench"], paths["objbench"])
        assert result["overall_status"] == "degraded"

    def test_merge_with_critical_failure(self, write_reports):
        paths = write_reports(
            doctor={
                "summary": {"status": "fail"},
                "checks": [{"check": "fuse_device", "status": "fail", "category": "critical"}],
            },
            bench={"summary": {"status": "pass"}},
            objbench={"summary": {"status": "pass"}},
        )
        result = merge_reports(paths["doctor"], paths["bench"], paths["objbench"])
        assert result["overall_status"] == "fail"

    def test_merge_with_warning_only_failure(self, write_reports):
        paths = write_reports(
            doctor={
                "summary": {"status": "fail"},
                "checks": [
                    {"check": "fuse_device", "status": "pass", "category": "critical"},
                    {"check": "cpu_cores", "status": "fail", "category": "warning"},
                ],
            },
            bench={"summary": {"status": "pass"}},
            objbench={"summary": {"status": "pass"}},
        )
        result = merge_reports(paths["doctor"], paths["bench"], paths["objbench"])
        assert result["overall_status"] == "degraded"

    def test_merge_with_no_reports(self):
        result = merge_reports(None, None, None)
        assert result["overall_status"] == "pass"
        assert result["reports"]["doctor"] == {}
        assert result["reports"]["bench"] == {}
        assert result["reports"]["objbench"] == {}

    def test_merge_partial_reports(self, write_reports):
        doctor = {"summary": {"status": "pass"}}
        paths = write_reports(doctor=doctor)
        result = merge_reports(paths["doctor"], None, None)
        assert result["overall_status"] == "pass"
        assert result["reports"]["doctor"] == doctor
        assert result["reports"]["bench"] == {}
        assert result["reports"]["objbench"] == {}

    def test_merge_with_invalid_report(self, write_reports):
        doctor = {"summary": {"status": "pass"}}
        paths = write_reports(doctor=doctor)
        result = merge_reports(paths["doctor"], "/nonexistent/bench.json", None)
        assert result["overall_status"] == "pass"
        assert result["reports"]["doctor"] == doctor
        assert "error" in result["reports"]["bench"]

    def test_merge_timestamp_present(self):
        result = merge_reports(None, None, None)
        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")

    def test_status_aggregation_priority(self, tmp_path):
        """Without check-level category data, 'fail' and 'warn' both resolve to 'degraded'."""
        test_cases = [
            (["pass", "pass", "pass"], "pass"),
            (["pass", "warn", "pass"], "degraded"),
            (["pass", "fail", "pass"], "degraded"),
            (["warn", "fail"], "degraded"),
            (["fail", "fail", "fail"], "degraded"),
            (["pass"], "pass"),
            (["warn"], "degraded"),
            (["fail"], "degraded"),
        ]

        for statuses, expected in test_cases:
            paths = []
            for i, status in enumerate(statuses):
                data = {"summary": {"status": status}}
                path = tmp_path / f"report_{'-'.join(statuses)}_{i}.json"
                path.write_text(json.dumps(data))
                paths.append(str(path))

            while len(paths) < 3:
                paths.append(None)

            result = merge_reports(*paths)
            assert result["overall_status"] == expected, \
                f"Failed for statuses {statuses}: got {result['overall_status']}, expected {expected}"


class TestRenderHtml:
    """Test cases for render_html function."""

    def test_render_basic_html(self):
        """Test basic HTML rendering."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "summary": {"status": "pass"},
                    "checks": {
                        "fuse_device": {"status": "pass", "message": "FUSE available"}
                    },
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert isinstance(html, str)
        assert "Fusion Filesystem Diagnostics" in html
        assert "2026-02-24T10:00:00Z" in html
        assert "pass" in html.lower()

    def test_render_with_status_badge(self):
        """Test that status badges are rendered correctly."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "warn",
            "reports": {
                "doctor": {
                    "summary": {"status": "warn"},
                    "checks": {},
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "warn" in html.lower() or "status-warn" in html

    def test_render_with_doctor_checks(self):
        """Test rendering with doctor report checks."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "summary": {"status": "pass"},
                    "version": "v1.5.0",
                    "checks": {
                        "memory": {
                            "status": "pass",
                            "message": "32GB available",
                        },
                        "fuse_device": {
                            "status": "warn",
                            "message": "FUSE check warning",
                        },
                    },
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "v1.5.0" in html
        assert "memory" in html.lower() or "Memory" in html
        assert "System Checks" in html

    def test_render_empty_reports(self):
        """Test rendering with empty reports."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {},
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_render_html_structure(self):
        """Test that rendered HTML contains basic HTML structure."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {"summary": {"status": "pass"}},
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "<html" in html.lower()
        assert "<body" in html.lower()
        assert "</body>" in html.lower()
        assert "</html>" in html.lower()

    def test_xss_in_remediation_is_escaped(self):
        """Test that HTML in report data is escaped to prevent XSS."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "fail",
            "reports": {
                "doctor": {
                    "check_summary": {"overall": "fail", "passed": 0, "failed": 1},
                    "checks": [
                        {
                            "check": "test_check",
                            "category": "critical",
                            "status": "fail",
                            "message": "<script>alert('xss')</script>",
                            "remediation": "<img src=x onerror=alert(1)>",
                        },
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "<script>alert" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html or "&#" in html

    def test_xss_in_check_message_is_escaped(self):
        """Test that HTML in check messages is escaped."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "check_summary": {"overall": "pass", "passed": 1, "failed": 0},
                    "checks": [
                        {
                            "check": "fuse_device",
                            "category": "critical",
                            "status": "pass",
                            "message": "<b>bold</b> text",
                            "details": {"path": "<script>alert(1)</script>"},
                        },
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "<script>alert(1)</script>" not in html

    def test_render_does_not_mutate_input(self):
        """Test that render_html does not modify the input dictionary."""
        combined_report = {
            "timestamp": "2026-02-24T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "storage": {
                        "filesystems": [
                            {
                                "device": "/dev/sda1",
                                "mount_point": "/",
                                "type": "ext4",
                                "total_bytes": 100000000000,
                                "available_bytes": 50000000000,
                            },
                        ],
                    },
                    "checks": [],
                    "check_summary": {"overall": "pass", "passed": 0, "failed": 0},
                },
                "bench": {},
                "objbench": {},
            },
        }

        import copy
        original = copy.deepcopy(combined_report)
        render_html(combined_report)
        assert "_used_pct" not in combined_report["reports"]["doctor"]["storage"]["filesystems"][0]
        assert combined_report == original


class TestLoadTemplate:
    """Test cases for load_template function."""

    def test_load_template_exists(self):
        """Test that template file is found and loaded."""
        template = load_template()
        assert isinstance(template, str)
        assert len(template) > 0

    def test_load_template_contains_variables(self):
        """Test that template contains Jinja2 template variables."""
        template = load_template()
        assert "{{" in template or "{%" in template

    def test_load_template_is_html(self):
        """Test that template is HTML content."""
        template = load_template()
        assert "<html" in template.lower()
        assert "<body" in template.lower()


class TestFilterFunctions:
    """Tests for module-level filter/helper functions."""

    def test_humanize_check_known_labels(self):
        assert humanize_check("fuse_device") == "FUSE Device"
        assert humanize_check("bucket_access_rw") == "Bucket Access (read/write)"
        assert humanize_check("nvme") == "NVMe"
        assert humanize_check("cpu_cores") == "CPU Cores"

    def test_humanize_check_unknown_with_acronyms(self):
        assert humanize_check("dns_lookup") == "DNS Lookup"
        assert humanize_check("http_check") == "HTTP Check"

    def test_humanize_check_simple(self):
        assert humanize_check("memory") == "Memory"
        assert humanize_check("disk_space") == "Disk Space"

    def test_smart_title(self):
        assert smart_title("cpu_cores") == "CPU Cores"
        assert smart_title("total_bytes") == "Total Bytes"

    def test_detail_label_critical(self):
        assert detail_label("required_min", "critical") == "Required (≥)"
        assert detail_label("required_bytes", "critical") == "Required (≥)"

    def test_detail_label_warning(self):
        assert detail_label("required_min", "warning") == "Recommended (≥)"
        assert detail_label("cores_required", "warning") == "Recommended (≥)"

    def test_detail_label_regular_key(self):
        assert detail_label("kernel_version") == "Kernel Version"

    def test_trim_sub_msg_strips_prefix(self):
        assert trim_sub_msg("check bucket exists: ok") == "ok"
        assert trim_sub_msg("list objects: ok") == "ok"

    def test_trim_sub_msg_no_colon(self):
        assert trim_sub_msg("simple message") == "simple message"

    def test_trim_sub_msg_empty(self):
        assert trim_sub_msg("") == ""
        assert trim_sub_msg(None) == ""

    def test_truncate_error_short_message(self):
        assert truncate_error("ok") == "ok"
        assert truncate_error("short error") == "short error"

    def test_truncate_error_api_error(self):
        long_msg = "operation error S3: PutObject, https response error StatusCode: 403, api error AccessDenied: Access Denied"
        result = truncate_error(long_msg)
        assert result == "AccessDenied: Access Denied"

    def test_truncate_error_status_code(self):
        long_msg = "x" * 81 + " StatusCode: 404 some extra text"
        result = truncate_error(long_msg)
        assert result == "HTTP 404"

    def test_truncate_error_generic(self):
        long_msg = "a" * 100
        result = truncate_error(long_msg)
        assert len(result) == 81  # 80 chars + ellipsis
        assert result.endswith("…")

    def test_truncate_error_empty(self):
        assert truncate_error("") == ""
        assert truncate_error(None) == ""

    def test_inline_code_converts_backticks(self):
        result = inline_code("Run `ulimit -n` to check")
        assert "<code>ulimit -n</code>" in str(result)

    def test_inline_code_escapes_html(self):
        result = inline_code("<script>alert(1)</script>")
        assert "<script>" not in str(result)
        assert "&lt;script&gt;" in str(result)

    def test_inline_code_empty(self):
        assert inline_code("") == ""
        assert inline_code(None) is None

    def test_extract_actual_kernel_version(self):
        assert extract_actual({"kernel_version": "5.15.0"}) == "5.15.0"

    def test_extract_actual_cores(self):
        assert extract_actual({"cores_available": 4}) == "4"

    def test_extract_actual_large_number(self):
        assert extract_actual({"soft_limit": 65535}) == "65,535"

    def test_extract_actual_bytes(self):
        result = extract_actual({"total_bytes": 8589934592})
        assert "GiB" in result

    def test_extract_actual_empty(self):
        assert extract_actual(None) == ""
        assert extract_actual({}) == ""

    def test_extract_reference(self):
        assert extract_reference({"required_min": "5.10"}) == "5.10"

    def test_extract_reference_bytes(self):
        result = extract_reference({"required_bytes": 4294967296})
        assert "GiB" in result

    def test_format_detail_value_bytes(self):
        result = format_detail_value(8589934592, "total_bytes")
        assert "GiB" in result
        assert "8,589,934,592" in result

    def test_format_detail_value_large_int(self):
        assert format_detail_value(65535) == "65,535"

    def test_format_detail_value_small(self):
        assert format_detail_value(42) == 42

    def test_humanize_bytes(self):
        assert _humanize_bytes(1073741824) == "1.0 GiB"
        assert _humanize_bytes(1048576) == "1 MiB"
        assert _humanize_bytes(524288) == "512 KiB"
        assert _humanize_bytes(1024) == "1 KiB"
        assert _humanize_bytes(500) == "500 Bytes"

    def test_format_number(self):
        assert _format_number(1000) == "1,000"
        assert _format_number(999) == "999"
        assert _format_number(65535) == "65,535"


class TestPrepareTemplateContext:
    """Tests for prepare_template_context function."""

    def test_does_not_mutate_input(self):
        """Verify the input dict is not modified."""
        import copy
        combined = {
            "timestamp": "2026-01-01T00:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "storage": {
                        "filesystems": [
                            {"total_bytes": 100, "available_bytes": 50, "mount_point": "/"},
                        ],
                    },
                    "checks": [],
                },
                "bench": {},
                "objbench": {},
            },
        }
        original = copy.deepcopy(combined)
        prepare_template_context(combined)
        assert combined == original

    def test_splits_checks_correctly(self):
        combined = {
            "timestamp": "2026-01-01T00:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "checks": [
                        {"check": "fuse_device", "status": "pass", "category": "critical"},
                        {"check": "disk_space", "status": "pass", "category": "warning"},
                        {"check": "bucket_access_rw", "status": "pass", "category": "critical"},
                        {"check": "bucket_access_ro", "status": "pass", "category": "critical"},
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }
        ctx = prepare_template_context(combined)
        assert len(ctx["system_checks"]) == 1
        assert ctx["system_checks"][0]["check"] == "fuse_device"
        assert len(ctx["disk_checks"]) == 1
        assert len(ctx["bucket_checks"]) == 2

    def test_collects_recommendations(self):
        combined = {
            "timestamp": "2026-01-01T00:00:00Z",
            "overall_status": "fail",
            "reports": {
                "doctor": {
                    "checks": [
                        {"check": "open_files", "status": "fail", "category": "warning", "remediation": "Increase ulimit"},
                        {"check": "fuse_device", "status": "fail", "category": "critical", "remediation": "Install FUSE"},
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }
        ctx = prepare_template_context(combined)
        assert len(ctx["recommendations"]) == 2
        # Critical should sort first
        assert ctx["recommendations"][0]["category"] == "critical"
        assert ctx["recommendations"][1]["category"] == "warning"

    def test_warnings_count(self):
        combined = {
            "timestamp": "2026-01-01T00:00:00Z",
            "overall_status": "degraded",
            "reports": {
                "doctor": {
                    "checks": [
                        {"check": "cpu_cores", "status": "fail", "category": "warning"},
                        {"check": "open_files", "status": "fail", "category": "warning"},
                        {"check": "fuse_device", "status": "pass", "category": "critical"},
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }
        ctx = prepare_template_context(combined)
        assert ctx["warnings_count"] == 2


class TestMain:
    """Tests for main() entrypoint."""

    def test_no_args_exits_one(self, monkeypatch):
        """main() with no report args should exit 1."""
        monkeypatch.setattr(sys, 'argv', ['generate_fusion_report.py'])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_successful_generation_exits_zero(self, write_reports, tmp_path, monkeypatch):
        """main() exits 0 on successful report generation regardless of check status."""
        paths = write_reports(doctor={
            "summary": {"status": "pass"},
            "checks": [{"check": "fuse_device", "status": "pass", "category": "critical"}],
        })
        html_out = str(tmp_path / "out.html")
        json_out = str(tmp_path / "out.json")
        monkeypatch.setattr(sys, 'argv', [
            'generate_fusion_report.py',
            '--doctor', paths["doctor"],
            '--output-html', html_out,
            '--output-json', json_out,
        ])
        main()
        assert Path(html_out).exists()
        assert Path(json_out).exists()

    def test_critical_failure_still_exits_zero(self, write_reports, tmp_path, monkeypatch):
        """main() exits 0 even with critical failures — report was generated successfully."""
        paths = write_reports(doctor={
            "summary": {"status": "fail"},
            "checks": [{"check": "fuse_device", "status": "fail", "category": "critical"}],
        })
        html_out = str(tmp_path / "out.html")
        json_out = str(tmp_path / "out.json")
        monkeypatch.setattr(sys, 'argv', [
            'generate_fusion_report.py',
            '--doctor', paths["doctor"],
            '--output-html', html_out,
            '--output-json', json_out,
        ])
        main()
        assert Path(html_out).exists()


class TestIntegration:
    """Integration tests for full report generation workflow."""

    def test_full_workflow_with_doctor_data(self, write_reports):
        paths = write_reports(doctor={
            "timestamp": "2026-02-24T10:00:00Z",
            "version": "v1.5.0",
            "summary": {"status": "pass", "message": "All checks passed"},
            "checks": {
                "fuse_device": {"status": "pass", "message": "/dev/fuse is available"},
                "kernel": {"status": "pass", "message": "Kernel version 5.15.0 >= 5.10"},
            },
        })
        combined = merge_reports(paths["doctor"], None, None)
        assert combined["overall_status"] == "pass"
        html = render_html(combined)
        assert "v1.5.0" in html
        assert "fuse" in html.lower()

    def test_full_workflow_with_multiple_reports(self, write_reports):
        paths = write_reports(
            doctor={"summary": {"status": "pass"}, "checks": {}},
            bench={"summary": {"status": "warn"}, "results": {"throughput": "5 GiB/s"}},
            objbench={"summary": {"status": "pass"}, "results": {}},
        )
        combined = merge_reports(paths["doctor"], paths["bench"], paths["objbench"])
        assert combined["overall_status"] == "degraded"
        html = render_html(combined)
        assert isinstance(html, str)
        assert len(html) > 1000


class TestRealFusionDoctorFormat:
    """Tests for the real fusion doctor output format (list-based checks, check_summary)."""

    def test_render_with_list_checks(self):
        """Test rendering when checks is a list (real fusion doctor format)."""
        combined_report = {
            "timestamp": "2026-03-04T10:00:00Z",
            "overall_status": "pass",
            "reports": {
                "doctor": {
                    "fusion_version": "2.6-develop-1f517df",
                    "check_summary": {
                        "overall": "pass",
                        "passed": 2,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "checks": [
                        {
                            "check": "fuse_device",
                            "category": "critical",
                            "status": "pass",
                            "message": "/dev/fuse is available",
                            "details": {"path": "/dev/fuse"},
                            "duration_ms": 0,
                        },
                        {
                            "check": "disk_space",
                            "category": "warning",
                            "status": "warn",
                            "message": "Low disk space on /tmp",
                            "duration_ms": 5,
                        },
                    ],
                },
                "bench": {},
                "objbench": {},
            },
        }

        html = render_html(combined_report)
        assert "2.6-develop-1f517df" in html
        assert "FUSE Device" in html
        assert "Storage Checks" in html  # disk_space goes to its own section
        assert "/dev/fuse" in html
        assert "System Checks" in html
        assert ">2<" in html  # "2" in metric-value for Passed
        assert "Passed" in html

    def test_merge_with_check_summary(self, write_reports):
        paths = write_reports(doctor={
            "check_summary": {"overall": "warn", "passed": 3, "failed": 0},
            "checks": [],
        })
        result = merge_reports(paths["doctor"], None, None)
        assert result["overall_status"] == "degraded"

    def test_full_workflow_real_format(self, write_reports):
        paths = write_reports(doctor={
            "schema_version": "1.1",
            "fusion_version": "2.6.0",
            "timestamp": "2026-03-04T10:00:00Z",
            "checks": [
                {
                    "check": "fuse_device",
                    "category": "critical",
                    "status": "pass",
                    "message": "/dev/fuse is available and accessible",
                    "details": {"path": "/dev/fuse", "permissions": "Dcrw-rw-rw-"},
                    "duration_ms": 0,
                },
            ],
            "check_summary": {"overall": "pass", "passed": 1, "failed": 0, "skipped": 0},
        })
        combined = merge_reports(paths["doctor"], None, None)
        assert combined["overall_status"] == "pass"
        html = render_html(combined)
        assert "2.6.0" in html
        assert "FUSE Device" in html
        assert "Dcrw-rw-rw-" in html


class TestNewSections:
    """Tests for the new System Environment, Storage, Resource Limits sections."""

    FULL_DOCTOR_DATA = {
        "schema_version": "1.1",
        "fusion_version": "2.6-develop-1f517df",
        "timestamp": "2026-03-04T15:35:35Z",
        "system": {
            "os": {
                "name": "ubuntu",
                "version": "24.04",
                "kernel": "6.14.0-27-generic",
                "architecture": "x86_64",
            },
            "cpu": {
                "model": "13th Gen Intel(R) Core(TM) i7-1355U",
                "cores": 10,
                "threads": 12,
            },
            "memory": {
                "total_bytes": 33301454848,
                "available_bytes": 3561734144,
                "swap_total_bytes": 2046816256,
                "swap_free_bytes": 417792,
            },
        },
        "storage": {
            "filesystems": [
                {
                    "device": "/dev/dm-1",
                    "mount_point": "/",
                    "type": "ext4",
                    "total_bytes": 981132795904,
                    "available_bytes": 152799973376,
                },
            ],
            "nvme_devices": [
                {
                    "name": "nvme0",
                    "model": "WD PC SN810",
                    "size_bytes": 1024209543168,
                    "block_devices": ["nvme0n1"],
                },
            ],
        },
        "resources": {
            "open_files": {"soft": 1048576, "hard": 1048576},
            "max_procs": {"soft": 125971, "hard": 125971},
            "mem_lock": {"soft": 4162678784, "hard": 4162678784},
            "stack_size": {"soft": 12800000, "hard": 18446744073709551615},
        },
        "checks": [
            {
                "check": "fuse_device",
                "category": "critical",
                "status": "pass",
                "message": "/dev/fuse is available and accessible",
                "details": {"path": "/dev/fuse", "permissions": "Dcrw-rw-rw-"},
                "duration_ms": 0,
            },
        ],
        "check_summary": {
            "overall": "pass",
            "passed": 1,
            "failed": 0,
            "skipped": 0,
        },
    }

    def _render(self, doctor_data=None):
        combined = {
            "timestamp": "2026-03-04T15:35:35Z",
            "overall_status": "pass",
            "reports": {
                "doctor": doctor_data or self.FULL_DOCTOR_DATA,
                "bench": {},
                "objbench": {},
            },
        }
        return render_html(combined)

    def test_system_section_present(self):
        """Test that System card is rendered."""
        html = self._render()
        assert "System" in html

    def test_os_info_rendered(self):
        """Test OS name, version, kernel, architecture appear."""
        html = self._render()
        assert "Ubuntu" in html
        assert "24.04" in html
        assert "6.14.0-27-generic" in html
        assert "x86_64" in html

    def test_cpu_info_rendered(self):
        """Test CPU model, cores, threads appear."""
        html = self._render()
        assert "10 / 12" in html  # cores / threads
        assert "i7-1355U" in html

    def test_memory_info_rendered(self):
        """Test memory total capacity appears in kv-grid layout."""
        html = self._render()
        assert "31.0 GiB" in html  # total capacity

    def test_storage_section_present(self):
        """Test that Storage section is rendered."""
        html = self._render()
        assert "Storage" in html

    def test_nvme_devices_rendered(self):
        """Test NVMe device info appears."""
        html = self._render()
        assert "nvme0" in html
        assert "WD PC SN810" in html

    def test_filesystem_table_rendered(self):
        """Test filesystem table with mount point and device."""
        html = self._render()
        assert "/dev/dm-1" in html
        assert "ext4" in html

    def test_resource_limits_section_present(self):
        """Test that Resource Limits section is rendered."""
        html = self._render()
        assert "Resource Limits" in html

    def test_resource_limits_values_rendered(self):
        """Test key resource limit values appear (with thousands separators)."""
        html = self._render()
        assert "1,048,576" in html  # open files
        assert "125,971" in html  # max procs

    def test_resource_limits_unlimited_rendered(self):
        """Test unlimited values displayed correctly."""
        html = self._render()
        assert "unlimited" in html  # stack_size hard limit

    def test_check_details_structured(self):
        """Test that check details use structured key-value instead of raw JSON."""
        html = self._render()
        assert "dk-key" in html  # structured detail key class
        assert "dk-val" in html  # structured detail value class
        assert "Dcrw-rw-rw-" in html

    def test_no_system_section_when_missing(self):
        """Test System card is absent when no system data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert "kv-label" not in html or "OS" not in html

    def test_no_storage_section_when_missing(self):
        """Test Storage section is absent when no storage data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert "NVMe" not in html

    def test_no_resource_section_when_missing(self):
        """Test Resource Limits section is absent when no resource data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert 'id="resource-limits"' not in html

    def test_section_renamed_to_system_checks(self):
        """Test that checks section is now 'System Checks'."""
        html = self._render()
        assert "System Checks" in html
        assert "System &amp; Validation" not in html


class TestP2Improvements:
    """Tests for P2 improvements: context-dependent collapse, copy buttons, filesystem filtering, timestamps."""

    FULL_DOCTOR_DATA = TestNewSections.FULL_DOCTOR_DATA

    def _render(self, doctor_data=None, overall_status="pass"):
        combined = {
            "timestamp": "2026-03-04T15:35:35Z",
            "overall_status": overall_status,
            "reports": {
                "doctor": doctor_data or self.FULL_DOCTOR_DATA,
                "bench": {},
                "objbench": {},
            },
        }
        return render_html(combined)

    def test_storage_collapsed_on_pass(self):
        """Storage sections should NOT have 'open' when overall status is pass."""
        html = self._render(overall_status="pass")
        import re
        for section_id in ("storage-devices", "mounted-filesystems"):
            match = re.search(rf'<details id="{section_id}"[^>]*>', html)
            if match:
                assert "open" not in match.group(0), f"{section_id} should not be open"

    def test_storage_not_open_on_fail(self):
        """Storage sections should NOT auto-open when overall status is fail."""
        doctor = dict(self.FULL_DOCTOR_DATA)
        doctor["check_summary"] = {"overall": "fail", "passed": 0, "failed": 1}
        html = self._render(doctor_data=doctor, overall_status="fail")
        import re
        for section_id in ("storage-devices", "mounted-filesystems"):
            match = re.search(rf'<details id="{section_id}"[^>]*>', html)
            if match:
                assert "open" not in match.group(0), f"{section_id} should not be open"

    def test_timestamps_use_time_element(self):
        """Timestamps should use <time> elements with local-time class."""
        html = self._render()
        assert '<time datetime="2026-03-04T15:35:35Z" class="local-time">' in html

    def test_timestamp_localization_js(self):
        """JS for localizing timestamps should be present."""
        html = self._render()
        assert "toLocaleString" in html
        assert "local-time" in html



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
