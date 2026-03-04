#!/usr/bin/env -S uv run --no-project --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest", "jinja2"]
# ///

"""
Unit tests for generate_fusion_report.py
Tests load_json_report, merge_reports, render_html, and status aggregation logic.
"""

import json
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path to import generate_fusion_report
sys.path.insert(0, str(Path(__file__).parent.parent / "bin"))

import pytest
from generate_fusion_report import (
    load_json_report,
    merge_reports,
    render_html,
    load_template,
)


class TestLoadJsonReport:
    """Test cases for load_json_report function."""

    def test_load_valid_json(self):
        """Test loading a valid JSON file."""
        test_data = {"status": "pass", "message": "All checks passed"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            result = load_json_report(temp_path)
            assert result == test_data
        finally:
            os.unlink(temp_path)

    def test_load_none_path(self):
        """Test with None path returns empty dict."""
        result = load_json_report(None)
        assert result == {}

    def test_load_empty_string_path(self):
        """Test with empty string path returns empty dict."""
        result = load_json_report("")
        assert result == {}

    def test_load_missing_file(self):
        """Test loading non-existent file."""
        result = load_json_report("/nonexistent/path/file.json")
        assert "error" in result
        assert "not found" in result["error"]

    def test_load_invalid_json(self):
        """Test loading malformed JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json content")
            temp_path = f.name

        try:
            result = load_json_report(temp_path)
            assert "error" in result
            assert "Malformed JSON" in result["error"]
        finally:
            os.unlink(temp_path)

    def test_load_empty_json_file(self):
        """Test loading empty JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = load_json_report(temp_path)
            assert "error" in result
        finally:
            os.unlink(temp_path)

    def test_load_complex_json(self):
        """Test loading complex nested JSON structure."""
        test_data = {
            "summary": {"status": "warn"},
            "checks": {
                "check1": {"status": "pass", "message": "OK"},
                "check2": {"status": "fail", "message": "Failed"},
            },
            "version": "v1.5.0",
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            result = load_json_report(temp_path)
            assert result == test_data
            assert result["summary"]["status"] == "warn"
        finally:
            os.unlink(temp_path)


class TestMergeReports:
    """Test cases for merge_reports function."""

    def test_merge_all_pass(self):
        """Test merging reports with all pass status."""
        doctor = {"summary": {"status": "pass"}}
        bench = {"summary": {"status": "pass"}}
        objbench = {"summary": {"status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            bench_path = Path(tmpdir) / "bench.json"
            objbench_path = Path(tmpdir) / "objbench.json"

            doctor_path.write_text(json.dumps(doctor))
            bench_path.write_text(json.dumps(bench))
            objbench_path.write_text(json.dumps(objbench))

            result = merge_reports(str(doctor_path), str(bench_path), str(objbench_path))
            assert result["overall_status"] == "pass"

    def test_merge_with_warning(self):
        """Test that warn status takes precedence over pass."""
        doctor = {"summary": {"status": "pass"}}
        bench = {"summary": {"status": "warn"}}
        objbench = {"summary": {"status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            bench_path = Path(tmpdir) / "bench.json"
            objbench_path = Path(tmpdir) / "objbench.json"

            doctor_path.write_text(json.dumps(doctor))
            bench_path.write_text(json.dumps(bench))
            objbench_path.write_text(json.dumps(objbench))

            result = merge_reports(str(doctor_path), str(bench_path), str(objbench_path))
            assert result["overall_status"] == "warn"

    def test_merge_with_failure(self):
        """Test that fail status takes precedence over warn and pass."""
        doctor = {"summary": {"status": "fail"}}
        bench = {"summary": {"status": "warn"}}
        objbench = {"summary": {"status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            bench_path = Path(tmpdir) / "bench.json"
            objbench_path = Path(tmpdir) / "objbench.json"

            doctor_path.write_text(json.dumps(doctor))
            bench_path.write_text(json.dumps(bench))
            objbench_path.write_text(json.dumps(objbench))

            result = merge_reports(str(doctor_path), str(bench_path), str(objbench_path))
            assert result["overall_status"] == "fail"

    def test_merge_with_no_reports(self):
        """Test merging with no reports provided."""
        result = merge_reports(None, None, None)
        assert result["overall_status"] == "pass"
        assert result["reports"]["doctor"] == {}
        assert result["reports"]["bench"] == {}
        assert result["reports"]["objbench"] == {}

    def test_merge_partial_reports(self):
        """Test merging with only some reports provided."""
        doctor = {"summary": {"status": "pass"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            doctor_path.write_text(json.dumps(doctor))

            result = merge_reports(str(doctor_path), None, None)
            assert result["overall_status"] == "pass"
            assert result["reports"]["doctor"] == doctor
            assert result["reports"]["bench"] == {}
            assert result["reports"]["objbench"] == {}

    def test_merge_with_invalid_report(self):
        """Test merging when one report file is invalid."""
        doctor = {"summary": {"status": "pass"}}
        bench_invalid_path = "/nonexistent/bench.json"

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            doctor_path.write_text(json.dumps(doctor))

            result = merge_reports(str(doctor_path), bench_invalid_path, None)
            assert result["overall_status"] == "pass"
            assert result["reports"]["doctor"] == doctor
            assert "error" in result["reports"]["bench"]

    def test_merge_timestamp_present(self):
        """Test that merged report includes timestamp."""
        result = merge_reports(None, None, None)
        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")

    def test_status_aggregation_priority(self):
        """Test that status aggregation follows priority: fail > warn > pass."""
        test_cases = [
            (["pass", "pass", "pass"], "pass"),
            (["pass", "warn", "pass"], "warn"),
            (["pass", "fail", "pass"], "fail"),
            (["warn", "fail"], "fail"),
            (["fail", "fail", "fail"], "fail"),
            (["pass"], "pass"),
            (["warn"], "warn"),
            (["fail"], "fail"),
        ]

        for statuses, expected in test_cases:
            with tempfile.TemporaryDirectory() as tmpdir:
                paths = []
                for i, status in enumerate(statuses):
                    data = {"summary": {"status": status}}
                    path = Path(tmpdir) / f"report{i}.json"
                    path.write_text(json.dumps(data))
                    paths.append(str(path))

                # Pad with None for missing reports
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
        assert "Fusion Diagnostic Report" in html
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
                        "disk": {
                            "status": "warn",
                            "message": "Low disk space",
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
        assert "32GB" in html

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


class TestIntegration:
    """Integration tests for full report generation workflow."""

    def test_full_workflow_with_doctor_data(self):
        """Test complete workflow: load, merge, render."""
        doctor_data = {
            "timestamp": "2026-02-24T10:00:00Z",
            "version": "v1.5.0",
            "summary": {"status": "pass", "message": "All checks passed"},
            "checks": {
                "fuse_device": {
                    "status": "pass",
                    "message": "/dev/fuse is available",
                },
                "kernel": {
                    "status": "pass",
                    "message": "Kernel version 5.15.0 >= 5.10",
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            doctor_path.write_text(json.dumps(doctor_data))

            # Merge
            combined = merge_reports(str(doctor_path), None, None)
            assert combined["overall_status"] == "pass"

            # Render
            html = render_html(combined)
            assert "v1.5.0" in html
            assert "fuse" in html.lower()  # Check name is rendered (case-insensitive)

    def test_full_workflow_with_multiple_reports(self):
        """Test complete workflow with all three report types."""
        doctor_data = {
            "summary": {"status": "pass"},
            "checks": {},
        }
        bench_data = {
            "summary": {"status": "warn"},
            "results": {"throughput": "5 GiB/s"},
        }
        objbench_data = {
            "summary": {"status": "pass"},
            "results": {},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            bench_path = Path(tmpdir) / "bench.json"
            objbench_path = Path(tmpdir) / "objbench.json"

            doctor_path.write_text(json.dumps(doctor_data))
            bench_path.write_text(json.dumps(bench_data))
            objbench_path.write_text(json.dumps(objbench_data))

            # Merge
            combined = merge_reports(str(doctor_path), str(bench_path), str(objbench_path))
            assert combined["overall_status"] == "warn"

            # Render
            html = render_html(combined)
            assert isinstance(html, str)
            assert len(html) > 1000  # Should be substantial HTML


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
        assert "Fuse Device" in html
        assert "Disk Space" in html
        assert "/dev/fuse" in html
        assert "critical" in html
        assert "2 passed" in html

    def test_merge_with_check_summary(self):
        """Test that merge_reports reads status from check_summary.overall."""
        doctor_data = {
            "check_summary": {"overall": "warn", "passed": 3, "failed": 0},
            "checks": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            doctor_path.write_text(json.dumps(doctor_data))

            result = merge_reports(str(doctor_path), None, None)
            assert result["overall_status"] == "warn"

    def test_full_workflow_real_format(self):
        """Test complete workflow with real fusion doctor format."""
        doctor_data = {
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
            "check_summary": {
                "overall": "pass",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            doctor_path = Path(tmpdir) / "doctor.json"
            doctor_path.write_text(json.dumps(doctor_data))

            combined = merge_reports(str(doctor_path), None, None)
            assert combined["overall_status"] == "pass"

            html = render_html(combined)
            assert "2.6.0" in html
            assert "Fuse Device" in html
            assert "Dcrw-rw-rw-" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
