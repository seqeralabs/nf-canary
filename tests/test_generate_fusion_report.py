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

    def test_system_environment_section_present(self):
        """Test that System Environment section is rendered."""
        html = self._render()
        assert "System Environment" in html

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
        assert "10 cores" in html
        assert "12 threads" in html
        assert "i7-1355U" in html

    def test_memory_info_rendered(self):
        """Test memory used and total appear with consistent framing."""
        html = self._render()
        assert "27.7 GB used" in html  # used ~27.7 GB
        assert "31.0 GB" in html  # total ~31 GB
        assert "3.3 GB available" in html  # available shown in parentheses

    def test_swap_warning_rendered(self):
        """Test swap critical warning when swap is nearly full."""
        html = self._render()
        assert "inline-critical" in html  # swap is 99%+ used

    def test_swap_shows_mb_when_under_1gb(self):
        """Test swap free shows MB when under 1 GB (avoids '0.0 GB free')."""
        html = self._render()
        # swap_free_bytes = 417792 (~0.4 MB), should show MB not GB
        assert "MB free" in html
        assert "0.0 GB free" not in html

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
        """Test System Environment section is absent when no system data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert "<h2>System Environment</h2>" not in html

    def test_no_storage_section_when_missing(self):
        """Test Storage section is absent when no storage data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert "NVMe Devices" not in html

    def test_no_resource_section_when_missing(self):
        """Test Resource Limits section is absent when no resource data."""
        html = self._render({"checks": [], "check_summary": {"overall": "pass", "passed": 0, "failed": 0}})
        assert "<h2>Resource Limits</h2>" not in html

    def test_section_renamed_to_validation_checks(self):
        """Test that old 'System & Validation' is now 'Validation Checks'."""
        html = self._render()
        assert "Validation Checks" in html
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

    def test_system_env_collapsed_on_pass(self):
        """System Environment should NOT have 'open' when overall status is pass."""
        html = self._render(overall_status="pass")
        # Find the system-environment details tag
        import re
        match = re.search(r'<details id="system-environment"[^>]*>', html)
        assert match, "system-environment section not found"
        assert "open" not in match.group(0)

    def test_system_env_open_on_fail(self):
        """System Environment should be open when overall status is fail."""
        doctor = dict(self.FULL_DOCTOR_DATA)
        doctor["check_summary"] = {"overall": "fail", "passed": 0, "failed": 1}
        html = self._render(doctor_data=doctor, overall_status="fail")
        import re
        match = re.search(r'<details id="system-environment"[^>]*>', html)
        assert match, "system-environment section not found"
        assert "open" in match.group(0)

    def test_copy_button_on_version(self):
        """Copy button should appear next to Fusion version."""
        html = self._render()
        assert 'data-copy="2.6-develop-1f517df"' in html
        assert "copy-btn" in html

    def test_copy_button_on_check_details(self):
        """Copy button should appear in check details."""
        html = self._render()
        # Check details copy button should contain the JSON of details
        assert 'data-copy="{' in html

    def test_timestamps_use_time_element(self):
        """Timestamps should use <time> elements with local-time class."""
        html = self._render()
        assert '<time datetime="2026-03-04T15:35:35Z" class="local-time">' in html

    def test_timestamp_localization_js(self):
        """JS for localizing timestamps should be present."""
        html = self._render()
        assert "toLocaleString" in html
        assert "local-time" in html

    def test_snap_mounts_filtered_out(self):
        """Snap bind mounts should be filtered from filesystem table."""
        doctor = json.loads(json.dumps(self.FULL_DOCTOR_DATA))  # deep copy
        doctor["storage"]["filesystems"].append({
            "device": "/",
            "mount_point": "/var/snap/firefox/common/host-hunspell",
            "type": "ext4",
            "total_bytes": 981132795904,
            "available_bytes": 152799973376,
        })
        html = self._render(doctor_data=doctor)
        assert "host-hunspell" not in html

    def test_zero_size_filesystems_filtered_out(self):
        """Filesystems with total_bytes=0 should be filtered out."""
        doctor = json.loads(json.dumps(self.FULL_DOCTOR_DATA))
        doctor["storage"]["filesystems"].append({
            "device": "none",
            "mount_point": "/tmp/.mount_app",
            "type": "fuse.appimage",
            "total_bytes": 0,
            "available_bytes": 0,
        })
        html = self._render(doctor_data=doctor)
        assert ".mount_app" not in html

    def test_filesystems_sorted_by_usage_desc(self):
        """Filesystems should be sorted by usage percentage descending."""
        doctor = json.loads(json.dumps(self.FULL_DOCTOR_DATA))
        doctor["storage"]["filesystems"] = [
            {"device": "/dev/a", "mount_point": "/low", "type": "ext4",
             "total_bytes": 100000000000, "available_bytes": 90000000000},  # 10% used
            {"device": "/dev/b", "mount_point": "/high", "type": "ext4",
             "total_bytes": 100000000000, "available_bytes": 10000000000},  # 90% used
        ]
        html = self._render(doctor_data=doctor)
        pos_high = html.index("/high")
        pos_low = html.index("/low")
        assert pos_high < pos_low, "Higher usage filesystem should appear first"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
