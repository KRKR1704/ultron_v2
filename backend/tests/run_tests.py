"""
run_tests.py — Master test runner for the ULTRON backend test suite.

Usage:
    python tests/run_tests.py
    python tests/run_tests.py --no-slow
    python tests/run_tests.py --file test_01_health.py

Runs pytest, parses output, prints a color-coded Rich table, saves JSON results,
and exits with code 1 if any failures occurred.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Rich is required — fail fast with a helpful message if missing
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    print("ERROR: 'rich' is not installed. Run: pip install rich")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_BACKEND_DIR = _HERE.parent
_RESULTS_FILE = _HERE / "last_run_results.json"

console = Console()


# ---------------------------------------------------------------------------
# Pytest output parsing
# ---------------------------------------------------------------------------

_FILE_SUMMARY_RE = re.compile(
    r"(tests[\\/]test_\S+\.py)\s+"           # file path
    r"(?P<dots>[\.FESxX\s]+)"                # result chars
)

_TOTALS_RE = re.compile(
    r"=+\s*"
    r"(?:(?P<failed>\d+) failed)?"
    r"[\s,]*"
    r"(?:(?P<passed>\d+) passed)?"
    r"[\s,]*"
    r"(?:(?P<skipped>\d+) skipped)?"
    r"[\s,]*"
    r"(?:(?P<errors>\d+) error)?"
    r".*in\s+(?P<duration>[\d.]+)s"
)

_SHORT_SUMMARY_RE = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED)\s+(tests[\\/].+?)\s*$", re.MULTILINE)


def _parse_output(output: str) -> dict:
    """
    Parse pytest -v output and return a dict:
    {
        "files": {
            "tests/test_01_health.py": {"passed": 4, "failed": 0, "skipped": 0, "errors": 0}
        },
        "totals": {"passed": N, "failed": N, "skipped": N, "errors": N},
        "duration": float,
        "raw": str,
    }
    """
    files: dict[str, dict] = {}
    totals = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    duration = 0.0

    # Parse individual test results from verbose output
    # Format: tests/test_XX.py::test_name PASSED/FAILED/SKIPPED
    test_line_re = re.compile(
        r"(tests[\\/]test_\S+?)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)"
    )

    for m in test_line_re.finditer(output):
        filepath = m.group(1).replace("\\", "/")
        status = m.group(3)

        if filepath not in files:
            files[filepath] = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        if status == "PASSED":
            files[filepath]["passed"] += 1
        elif status in ("FAILED", "ERROR"):
            files[filepath]["failed"] += 1
        elif status == "SKIPPED":
            files[filepath]["skipped"] += 1
        elif status in ("XFAIL", "XPASS"):
            files[filepath]["passed"] += 1  # treat as pass for display

    # Parse totals line
    for m in _TOTALS_RE.finditer(output):
        totals["passed"] = int(m.group("passed") or 0)
        totals["failed"] = int(m.group("failed") or 0)
        totals["skipped"] = int(m.group("skipped") or 0)
        totals["errors"] = int(m.group("errors") or 0)
        duration = float(m.group("duration") or 0)
        break

    return {
        "files": files,
        "totals": totals,
        "duration": duration,
        "raw": output,
    }


# ---------------------------------------------------------------------------
# Rich display
# ---------------------------------------------------------------------------

def _build_table(results: dict) -> Table:
    """Build and return the Rich result table."""
    table = Table(
        title="[bold cyan]ULTRON Backend Test Results[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        expand=False,
        min_width=70,
    )

    table.add_column("Test File", style="white", min_width=35)
    table.add_column("Passed", justify="right", style="green", min_width=8)
    table.add_column("Failed", justify="right", style="red", min_width=8)
    table.add_column("Skipped", justify="right", style="yellow", min_width=8)
    table.add_column("Status", justify="center", min_width=10)

    files = results["files"]

    if not files:
        table.add_row(
            "[dim]No test results found — check pytest output above[/dim]",
            "", "", "", "",
        )
        return table

    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for filepath, counts in sorted(files.items()):
        p = counts["passed"]
        f = counts["failed"]
        s = counts["skipped"]
        e = counts["errors"]

        total_passed += p
        total_failed += f + e
        total_skipped += s

        # Row color logic
        if f + e > 0:
            row_style = "on #3d0000"
            status_text = Text("FAIL", style="bold red")
        elif s > 0 and p == 0:
            row_style = "on #2d2d00"
            status_text = Text("SKIP", style="bold yellow")
        elif s > 0:
            row_style = ""
            status_text = Text("PASS*", style="bold green")
        else:
            row_style = ""
            status_text = Text("PASS", style="bold green")

        # Shorten path for display
        short_path = filepath.replace("tests/", "")

        table.add_row(
            f"[dim]{short_path}[/dim]",
            str(p) if p else "[dim]0[/dim]",
            f"[bold red]{f + e}[/bold red]" if f + e else "[dim]0[/dim]",
            str(s) if s else "[dim]0[/dim]",
            status_text,
            style=row_style,
        )

    # Summary row
    table.add_section()
    overall_status = (
        Text("ALL PASSED", style="bold green")
        if total_failed == 0
        else Text(f"{total_failed} FAILED", style="bold red on dark_red")
    )
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold green]{total_passed}[/bold green]",
        f"[bold red]{total_failed}[/bold red]" if total_failed else "[dim]0[/dim]",
        f"[yellow]{total_skipped}[/yellow]" if total_skipped else "[dim]0[/dim]",
        overall_status,
    )

    return table


# ---------------------------------------------------------------------------
# JSON results
# ---------------------------------------------------------------------------

def _save_results(results: dict, exit_code: int) -> None:
    output = {
        "timestamp": datetime.now().isoformat(),
        "exit_code": exit_code,
        "duration_seconds": results["duration"],
        "totals": results["totals"],
        "files": results["files"],
    }
    try:
        _RESULTS_FILE.write_text(json.dumps(output, indent=2))
        console.print(
            f"\n[dim]Results saved to [cyan]{_RESULTS_FILE}[/cyan][/dim]"
        )
    except Exception as err:
        console.print(f"[yellow]Warning: could not save results file: {err}[/yellow]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Build pytest command
    extra_args = sys.argv[1:]
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--no-header",
        "-q",
    ] + extra_args

    console.rule("[bold cyan]ULTRON Test Suite[/bold cyan]")
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    start = time.monotonic()

    proc = subprocess.run(
        cmd,
        cwd=str(_BACKEND_DIR),
        capture_output=False,   # let pytest stream to terminal directly
        text=True,
    )

    # Re-run capturing to parse output
    proc_capture = subprocess.run(
        cmd,
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
    )

    elapsed = time.monotonic() - start

    output = proc_capture.stdout + "\n" + proc_capture.stderr
    results = _parse_output(output)
    results["duration"] = results["duration"] or elapsed

    console.rule("[bold cyan]Results[/bold cyan]")
    table = _build_table(results)
    console.print(table)

    totals = results["totals"]
    console.print(
        f"\n[dim]Duration: {results['duration']:.2f}s  |  "
        f"Passed: [green]{totals['passed']}[/green]  "
        f"Failed: [red]{totals['failed']}[/red]  "
        f"Skipped: [yellow]{totals['skipped']}[/yellow][/dim]"
    )

    exit_code = proc.returncode
    _save_results(results, exit_code)

    if exit_code != 0:
        console.print("\n[bold red]TESTS FAILED[/bold red] — see output above for details.")
    else:
        console.print("\n[bold green]ALL TESTS PASSED[/bold green]")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
