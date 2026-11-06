#!/usr/bin/env python3
"""CI report for pull requests.

`collect <module>` is the last step of every CI job: it reads the machine-readable files the
job's steps left in $REPORT_DIR (test results, lint output, build logs), writes the job summary,
adds annotations GitHub doesn't create on its own and saves <module>.json.

`render` runs in the final `report` job: it merges those files with the job results and timings
into one Markdown comment that is posted (and updated on every push) in the pull request.

Standard library only, so it runs on a bare runner image.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

MARKER = "<!-- ci-report -->"  # the workflow finds the PR comment to update by this line
MODULES = {  # job id -> (title, stack)
    "backend": ("Backend", ".NET"),
    "frontend": ("Frontend", "React"),
    "ai": ("AI", "Python"),
    "infra": ("Infra", "OpenTofu"),
}
ICONS = {"pass": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️", "skip": "⏭️"}
RESULT_ICONS = {"passed": ICONS["pass"], "failed": ICONS["fail"], "skipped": ICONS["skip"]}
MAX_ROWS = 10
WORKSPACE = Path(os.environ.get("GITHUB_WORKSPACE") or os.getcwd())
COMMENT_LIMIT = 60_000  # GitHub rejects comments longer than 65,536 characters
VITE_CHUNK_LIMIT = 500_000  # bytes, Vite's default chunkSizeWarningLimit
SEVERITIES = ["critical", "high", "moderate", "low", "info"]
TRX_OUTCOMES = {"Passed": "passed", "Failed": "failed", "Error": "failed", "Timeout": "failed"}

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
# Canonical compiler/MSBuild message, possibly prefixed with the node of a parallel build, e.g.
#   3:7>/src/Foo.cs(12,19): warning CS8602: Dereference of a possibly null reference. [Foo.csproj]
MSBUILD_LINE = re.compile(
    r"^\s*(?:\d+(?::\d+)?>)?\s*(?P<file>.+?)"
    r"(?:\((?P<line>\d+)(?:,(?P<col>\d+))?(?:,\d+,\d+)?\))?"
    r"\s*:\s*(?P<level>error|warning)\s+(?P<code>[A-Za-z]+\d*)\s*:\s*(?P<msg>.*?)"
    r"(?:\s+\[[^\]]+\])?\s*$"
)
TSC_LINE = re.compile(
    r"^(?P<file>[^\s(][^(]*)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.+)$"
)
DOTNET_FRAME = re.compile(r" in (?P<file>.+?):line (?P<line>\d+)")
PYTEST_LOCATION = re.compile(r"^(?P<file>[^\s:]+\.py):(?P<line>\d+): ", re.M)
NPM_DEPRECATED = re.compile(r"npm warn deprecated (?P<package>\S+): (?P<msg>.+)$", re.M)


# --- Report model ------------------------------------------------------------------------------


@dataclass
class Check:
    name: str  # heading in the details, e.g. "Tests"
    label: str  # short form in the overview row, e.g. "tests"
    status: str  # pass | warn | fail | info | skip
    summary: str = ""  # e.g. "12 passed"; empty when there is nothing to add
    body: str = ""  # Markdown details
    overview: bool = True  # False: in the overview row only when it needs attention
    note: str = ""  # shown in the details when there is no summary, e.g. "no problems"


@dataclass
class ModuleReport:
    module: str
    checks: list[Check] = field(default_factory=list)

    @property
    def status(self) -> str:
        statuses = {check.status for check in self.checks}
        return next((s for s in ("fail", "warn") if s in statuses), "pass")

    def to_json(self) -> dict:
        checks = [asdict(check) for check in self.checks]
        return {"module": self.module, "status": self.status, "checks": checks}

    @classmethod
    def from_json(cls, data: dict) -> ModuleReport:
        return cls(data["module"], [Check(**check) for check in data.get("checks", [])])


@dataclass
class TestCase:
    name: str
    outcome: str  # passed | failed | skipped
    message: str = ""
    details: str = ""
    file: str | None = None  # absolute, or relative to the module directory
    line: int | None = None
    duration: float = 0.0


@dataclass
class TestSuite:
    name: str
    cases: list[TestCase]
    duration: float = 0.0


@dataclass
class Problem:
    level: str  # error | warning
    message: str
    file: str | None = None
    line: int | None = None
    code: str = ""


# --- Markdown ------------------------------------------------------------------------------------


def relative(text: str) -> str:
    """Tool output without the checkout path, so paths read like repository paths."""
    return text.replace(f"{WORKSPACE}{os.sep}", "")


def plain(text: str) -> str:
    """Untrusted text made inert: no HTML, no @mentions."""
    return html.escape(text, quote=False).replace("@", "@\u200b")


def cell(text: str, limit: int = 200) -> str:
    """One-line table cell. Code spans from tool messages are kept, everything else is escaped."""
    text = " ".join(relative(ANSI.sub("", text or "")).split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    out, pos = [], 0
    for match in CODE_SPAN.finditer(text):
        out += [plain(text[pos : match.start()]), match.group(0)]
        pos = match.end()
    out.append(plain(text[pos:]))
    return "".join(out).replace("|", "\\|")


def code(text: str) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    ticks = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def code_block(text: str, keep: str = "head", max_lines: int = 30) -> str:
    lines = relative(ANSI.sub("", text)).strip("\n").splitlines()
    if len(lines) > max_lines:
        lines = [*lines[:max_lines], "…"] if keep == "head" else ["…", *lines[-max_lines:]]
    body = "\n".join(line[:300] for line in lines)
    longest = max((len(run) for run in re.findall(r"`{3,}", body)), default=2)
    fence = "`" * (longest + 1)
    return f"{fence}text\n{body}\n{fence}"


def table(headers: list[str], rows: list[list[str]], align: str = "") -> str:
    marks = {"l": ":--", "c": ":-:", "r": "--:"}
    align = align or "l" * len(headers)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(marks[a] for a in align) + "|"]
    return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in rows])


def more(total: int, shown: int, where: str = "the job log") -> str:
    return f"\n\n<sub>…and {total - shown} more in {where}.</sub>" if total > shown else ""


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def kb(size: int) -> str:
    return f"{size / 1000:.1f} kB"


def seconds(value: float) -> str:
    if value < 1:
        return f"{value * 1000:.0f} ms"
    if value < 10:
        return f"{value:.1f} s"
    if value < 60:
        return f"{value:.0f} s"
    return f"{int(value // 60)} min {int(value % 60)} s"


# --- Paths, links, annotations -------------------------------------------------------------------

ANNOTATION_BUDGET = {"error": 10, "warning": 10}  # GitHub shows at most 10 of each per step


def locate(path: str, base: Path) -> tuple[str, str, bool]:
    """(repository path, path to show, file exists) for a path reported by a tool."""
    absolute = os.path.normpath(path if os.path.isabs(path) else base / path)
    repo = os.path.relpath(absolute, WORKSPACE)
    if repo.startswith(".."):
        return path, path, False
    shown = os.path.relpath(absolute, base)
    return repo, repo if shown.startswith("..") else shown, os.path.isfile(absolute)


def location(path: str | None, line: int | None, base: Path) -> str:
    if not path:
        return ""
    repo, shown, exists = locate(path, base)
    text = code(f"{shown}:{line}" if line else shown)
    repository = os.environ.get("GITHUB_REPOSITORY")
    sha = os.environ.get("HEAD_SHA") or os.environ.get("GITHUB_SHA")
    if not (exists and repository and sha):
        return text
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    anchor = f"#L{line}" if line else ""
    return f"[{text}]({server}/{repository}/blob/{sha}/{quote(repo)}{anchor})"


def annotate(level: str, message: str, path: str | None, line: int | None, base: Path, title: str):
    if ANNOTATION_BUDGET.get(level, 0) <= 0:
        return
    ANNOTATION_BUDGET[level] -= 1

    def data(value: str) -> str:
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    def prop(value: str) -> str:
        return data(value).replace(":", "%3A").replace(",", "%2C")

    props = [f"title={prop(title)}"]
    if path:
        props.append(f"file={prop(locate(path, base)[0])}")
        if line:
            props.append(f"line={int(line)}")
    print(f"::{level} {','.join(props)}::{data(relative(message))}")


# --- Readers -------------------------------------------------------------------------------------


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return ""


def read_json(path: Path):
    try:
        return json.loads(read(path) or "null")
    except json.JSONDecodeError:
        return None


def log_tail(path: Path | None, lines: int = 20) -> str:
    kept = [line for line in ANSI.sub("", read(path)).splitlines() if line.strip()] if path else []
    return "\n".join(kept[-lines:])


def exit_code(path: Path) -> int | None:
    """Exit code saved by `cmd || echo $? > file`; None when the command succeeded."""
    text = read(path).strip()
    return int(text) if text.isdigit() else None


def iso_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", value.replace("Z", "+00:00")))
    except ValueError:
        return None


def parse_msbuild(path: Path) -> list[Problem]:
    problems, seen = [], set()
    for raw in read(path).splitlines():
        match = MSBUILD_LINE.match(raw)
        if not match or match.group("file", "line", "col", "code", "msg") in seen:
            continue
        seen.add(match.group("file", "line", "col", "code", "msg"))
        line = int(match["line"]) if match["line"] else None
        problems.append(Problem(match["level"], match["msg"], match["file"], line, match["code"]))
    return problems


def parse_trx(path: Path) -> TestSuite | None:
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    methods = {
        unit.get("id"): method
        for unit in root.iterfind("t:TestDefinitions/t:UnitTest", ns)
        if (method := unit.find("t:TestMethod", ns)) is not None
    }
    if methods:
        name = Path(next(iter(methods.values())).get("codeBase", path.stem)).stem
    else:  # nothing discovered, but the adapter still logs the assembly it scanned
        found = re.search(r"Discovering: (\S+)", root.findtext(".//t:StdOut", "", ns))
        name = found.group(1) if found else path.stem

    cases = []
    for result in root.iterfind("t:Results/t:UnitTestResult", ns):
        method = methods.get(result.get("testId"))
        class_name = method.get("className", "") if method is not None else ""
        test = result.get("testName", "").removeprefix(f"{class_name}." if class_name else "")
        message = result.findtext("t:Output/t:ErrorInfo/t:Message", "", ns).strip()
        stack = result.findtext("t:Output/t:ErrorInfo/t:StackTrace", "", ns)
        # Frames with a source location are the project's own code; library internals have none
        own = [line.strip() for line in stack.splitlines() if DOTNET_FRAME.search(line)]
        frame = DOTNET_FRAME.search(stack)
        cases.append(
            TestCase(
                name=f"{class_name.rsplit('.', 1)[-1]}.{test}" if class_name else test,
                outcome=TRX_OUTCOMES.get(result.get("outcome", ""), "skipped"),
                message=message,
                details="\n".join([message, "", *(own or stack.strip().splitlines()[:8])]),
                file=frame["file"] if frame else None,
                line=int(frame["line"]) if frame else None,
                duration=timespan(result.get("duration")),
            )
        )
    times = root.find("t:Times", ns)
    start = iso_time(times.get("start")) if times is not None else None
    finish = iso_time(times.get("finish")) if times is not None else None
    duration = (finish - start).total_seconds() if start and finish else 0.0
    return TestSuite(name, cases, duration or sum(case.duration for case in cases))


def timespan(value: str | None) -> float:
    match = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value or "")
    return int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3]) if match else 0.0


def parse_junit(path: Path) -> list[TestSuite]:
    """JUnit XML written by pytest."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    suites = []
    for suite in [root] if root.tag == "testsuite" else root.iter("testsuite"):
        cases = []
        for case in suite.iter("testcase"):
            failure = case.find("failure")
            failure = case.find("error") if failure is None else failure
            skipped = case.find("skipped")
            text = failure.text or "" if failure is not None else ""
            file, line = case.get("file"), case.get("line")
            line = int(line) + 1 if line and line.isdigit() else None  # pytest counts from 0
            name = (
                f"{file}::{case.get('name')}"
                if file
                else f"{case.get('classname')}.{case.get('name')}"
            )
            if found := PYTEST_LOCATION.findall(text):  # the assertion, not the test header
                file, line = found[-1][0], int(found[-1][1])
            if failure is not None:
                outcome, message = "failed", failure.get("message") or text.strip()
            elif skipped is not None:
                outcome, message = "skipped", skipped.get("message", "")
            else:
                outcome, message = "passed", ""
            duration = float(case.get("time") or 0)
            cases.append(TestCase(name, outcome, message, text, file, line, duration))
        duration = float(suite.get("time") or 0) or sum(case.duration for case in cases)
        suites.append(TestSuite(suite.get("name", ""), cases, duration))
    return suites


def parse_tofu_test(path: Path, prefix: str = "") -> list[TestSuite]:
    """`tofu test -json-into` output: one JSON message per line, one suite per *.tftest.hcl file.

    `prefix` is the configuration's directory relative to the report base (file paths in the
    output are relative to the configuration)."""
    runs: dict[str, dict[str, TestCase]] = {}
    previous: datetime | None = None  # runs execute one after another; no start events
    outcomes = {"pass": "passed", "fail": "failed", "error": "failed", "skip": "skipped"}
    for raw in read(path).splitlines():
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        file, run = msg.get("@testfile"), msg.get("@testrun")
        stamp = iso_time(msg.get("@timestamp"))
        if msg.get("type") == "test_abstract":
            previous = stamp
            for test_file, names in (msg.get("test_abstract") or {}).items():
                cases = runs.setdefault(test_file, {})
                for name in names:
                    cases.setdefault(name, TestCase(name, "skipped", file=prefix + test_file))
        elif msg.get("type") == "test_run" and file and run:
            case = runs.setdefault(file, {}).setdefault(run, TestCase(run, "skipped"))
            case.file = prefix + file
            status = (msg.get("test_run") or {}).get("status")
            case.outcome = outcomes.get(status, case.outcome)
            if stamp and previous:
                case.duration = (stamp - previous).total_seconds()
            previous = stamp
        elif msg.get("type") == "diagnostic" and file and run:
            diag = msg.get("diagnostic") or {}
            case = runs.setdefault(file, {}).setdefault(run, TestCase(run, "skipped"))
            text = diag.get("summary", "") + (f": {diag['detail']}" if diag.get("detail") else "")
            case.message = case.message or text
            case.details = "\n".join(filter(None, [case.details, text]))
            where = diag.get("range") or {}
            if where.get("filename") and case.line is None:
                case.file = prefix + where["filename"]
                case.line = (where.get("start") or {}).get("line")
    return [
        TestSuite(prefix + file, list(cases.values()), sum(c.duration for c in cases.values()))
        for file, cases in runs.items()
    ]


# --- Checks shared by several modules ------------------------------------------------------------


def not_run(name: str, label: str, outcome: str | None) -> Check | None:
    if outcome in (None, "", "skipped", "cancelled"):
        return Check(name, label, "skip", "not run")
    return None


def problems_table(problems: list[Problem], base: Path, code_header: str = "Rule") -> str:
    ordered = sorted(problems, key=lambda p: (p.level != "error", p.file or "", p.line or 0))
    shown = ordered[:MAX_ROWS]
    with_code = any(p.code for p in shown)
    headers = ["", "Location", *([code_header] if with_code else []), "Message"]
    rows = []
    for p in shown:
        icon = ICONS["fail" if p.level == "error" else "warn"]
        rule = [code(p.code) if p.code else ""] if with_code else []
        rows.append([icon, location(p.file, p.line, base), *rule, cell(p.message)])
    return table(headers, rows, "c" + "l" * (len(headers) - 1)) + more(len(problems), len(rows))


def count_summary(problems: list[Problem]) -> str:
    errors = sum(p.level == "error" for p in problems)
    counts = [(errors, "error"), (len(problems) - errors, "warning")]
    return ", ".join(plural(count, word) for count, word in counts if count)


def lint_check(
    name: str, problems: list[Problem], outcome: str | None, base: Path, fixable: int, fix: str
) -> Check:
    if skipped := not_run(name, "lint", outcome):
        return skipped
    if not problems:
        if outcome == "failure":
            return Check(
                name, "lint", "fail", "failed", "No problems were recorded — see the job log."
            )
        return Check(name, "lint", "pass", note="no problems")
    status = "fail" if outcome == "failure" or any(p.level == "error" for p in problems) else "warn"
    body = problems_table(problems, base)
    if fixable:
        body += f"\n\n{plural(fixable, 'problem')} can be fixed automatically with {code(fix)}."
    return Check(name, "lint", status, count_summary(problems), body)


def tests_check(
    suites: list[TestSuite],
    outcome: str | None,
    base: Path,
    *,
    empty: str,
    log: Path | None = None,
    list_all: bool = False,
    tool: str = "Test",
) -> Check:
    if skipped := not_run("Tests", "tests", outcome):
        return skipped
    cases = [case for suite in suites for case in suite.cases]
    if not cases:
        if outcome != "failure":
            return Check("Tests", "tests", "info", "none yet", empty)
        tail = log_tail(log)
        body = "No test results were written." + (f"\n\n{code_block(tail)}" if tail else "")
        return Check("Tests", "tests", "fail", "failed", body)

    failed = [c for c in cases if c.outcome == "failed"]
    skipped = [c for c in cases if c.outcome == "skipped"]
    passed = len(cases) - len(failed) - len(skipped)
    counts = [(len(failed), "failed"), (passed, "passed"), (len(skipped), "skipped")]
    summary = ", ".join(f"{n} {word}" for n, word in counts if n)
    duration = sum(suite.duration for suite in suites)
    parts = [f"<sub>{plural(len(cases), 'test')} in {seconds(duration)}</sub>"]

    if len(suites) > 1:
        rows = []
        for suite in suites:
            outcomes = [case.outcome for case in suite.cases]
            row = [outcomes.count(o) for o in ("passed", "failed", "skipped")]
            rows.append([code(suite.name), *map(str, row), seconds(suite.duration)])
        parts.append(table(["Suite", "Passed", "Failed", "Skipped", "Time"], rows, "lrrrr"))

    if list_all:
        shown = cases[: MAX_ROWS * 2]
        rows = [[cell(c.name), RESULT_ICONS[c.outcome], seconds(c.duration)] for c in shown]
        parts.append(table(["Test", "Result", "Time"], rows, "lcr") + more(len(cases), len(rows)))

    if failed:
        rows = []
        for c in failed[:MAX_ROWS]:
            first_line = c.message.splitlines()[0] if c.message else ""
            rows.append([cell(c.name, 120), cell(first_line), location(c.file, c.line, base)])
        failures = table(["Test", "Error", "Location"], rows) + more(len(failed), len(rows))
        parts.append(f"**Failed**\n\n{failures}")
        outputs = [
            f"{code(c.name)}\n\n{code_block(c.details or c.message, keep='tail', max_lines=25)}"
            for c in failed[:5]
        ]
        parts.append(
            "<details><summary>Failure output</summary>\n\n"
            + "\n\n".join(outputs)
            + "\n\n</details>"
        )
        for c in failed:
            annotate(
                "error",
                c.message or "Test failed",
                c.file,
                c.line,
                base,
                f"{tool} failed: {c.name}",
            )

    if skipped and not list_all:
        items = [
            code(c.name) + (f" — {cell(c.message, 120)}" if c.message else "") for c in skipped[:5]
        ]
        parts.append("**Skipped:** " + " · ".join(items) + more(len(skipped), len(items)))

    if outcome == "failure" and not failed:
        tail = log_tail(log)
        parts.append(
            "The run failed although no test did." + (f"\n\n{code_block(tail)}" if tail else "")
        )
    status = "fail" if failed or outcome == "failure" else "pass"
    return Check("Tests", "tests", status, summary, "\n\n".join(parts))


def format_check(
    files: list[str], code_exit: int | None, fix: str, base: Path, drift: int
) -> Check:
    """Formatting is reported but not enforced yet (see CONTRIBUTING.md)."""
    if code_exit is not None and code_exit != drift:
        body = f"The formatter exited with code {code_exit} — see the job log."
        return Check("Formatting", "format", "info", "not checked", body, overview=False)
    if not files:
        return Check("Formatting", "format", "pass", overview=False, note="all files formatted")
    shown = [location(f, None, base) for f in files[:MAX_ROWS]]
    body = f"Not enforced yet — run {code(fix)} before pushing.\n\n" + " · ".join(shown)
    body += more(len(files), len(shown))
    return Check("Formatting", "format", "info", plural(len(files), "file"), body, overview=False)


# --- Modules -------------------------------------------------------------------------------------


def collect_backend(d: Path, outcomes: dict[str, str], base: Path) -> list[Check]:
    checks = []
    errors = parse_msbuild(d / "msbuild-errors.log")
    warnings = parse_msbuild(d / "msbuild-warnings.log")
    build = outcomes.get("build")
    if skipped := not_run("Build", "build", build):
        checks.append(skipped)
    elif build == "failure":
        summary = plural(len(errors), "error") if errors else "failed"
        problems = errors + warnings
        body = (
            problems_table(problems, base, "Code")
            if problems
            else code_block(log_tail(d / "build.log"))
        )
        checks.append(Check("Build", "build", "fail", summary, body))
    elif warnings:
        body = problems_table(warnings, base, "Code")
        checks.append(Check("Build", "build", "warn", plural(len(warnings), "warning"), body))
    else:
        checks.append(Check("Build", "build", "pass", note="no warnings"))

    suites = [suite for path in sorted((d / "trx").glob("*.trx")) if (suite := parse_trx(path))]
    empty = "The test projects in `backend/tests` don't contain any tests yet."
    checks.append(tests_check(suites, outcomes.get("test"), base, empty=empty, log=d / "test.log"))

    if (d / "format.log").exists():
        files = sorted({p.file for p in parse_msbuild(d / "format.log") if p.file})
        checks.append(format_check(files, exit_code(d / "format.exit"), "dotnet format", base, 2))
    return checks


def collect_frontend(d: Path, outcomes: dict[str, str], base: Path) -> list[Check]:
    checks = []
    if outcomes.get("install") == "failure":
        body = code_block(log_tail(d / "npm-install.log"))
        checks.append(Check("Install", "install", "fail", "npm install failed", body))

    problems, fixable = [], 0
    for result in read_json(d / "eslint.json") or []:
        fixable += result.get("fixableErrorCount", 0) + result.get("fixableWarningCount", 0)
        for msg in result.get("messages", []):
            level = "error" if msg.get("severity") == 2 or msg.get("fatal") else "warning"
            rule = msg.get("ruleId") or ""
            problems.append(
                Problem(
                    level, msg.get("message", ""), result.get("filePath"), msg.get("line"), rule
                )
            )
    fix = "npm run lint -- --fix"
    checks.append(lint_check("Lint (ESLint)", problems, outcomes.get("lint"), base, fixable, fix))

    build = outcomes.get("build")
    if skipped := not_run("Build", "build", build):
        checks.append(skipped)
    elif build == "failure":
        type_errors = []
        for line in ANSI.sub("", read(d / "build.log")).splitlines():
            if match := TSC_LINE.match(line.strip()):
                type_errors.append(
                    Problem("error", match["msg"], match["file"], int(match["line"]), match["code"])
                )
        if type_errors:
            body = problems_table(type_errors, base, "Code")
            checks.append(
                Check("Build", "build", "fail", plural(len(type_errors), "type error"), body)
            )
        else:
            checks.append(
                Check("Build", "build", "fail", "failed", code_block(log_tail(d / "build.log")))
            )
    else:
        passed = Check("Build", "build", "pass", note="type check and production build passed")
        checks += [passed, bundle_check(base / "dist")]

    checks.append(dependencies_check(d))

    if (d / "format.log").exists():
        files = [
            line.removeprefix("[warn] ").strip()
            for line in read(d / "format.log").splitlines()
            if line.startswith("[warn] ") and "Code style issues" not in line
        ]
        checks.append(format_check(files, exit_code(d / "format.exit"), "npm run format", base, 1))
    return [check for check in checks if check]


def bundle_check(dist: Path) -> Check | None:
    assets = []
    for path in sorted(p for p in dist.rglob("*") if p.is_file() and p.suffix != ".map"):
        data = path.read_bytes()
        is_text = path.suffix in {".js", ".mjs", ".css", ".html", ".svg", ".json", ".txt"}
        gzipped = len(gzip.compress(data, compresslevel=6, mtime=0)) if is_text else len(data)
        assets.append((path.relative_to(dist).as_posix(), len(data), gzipped))
    if not assets:
        return None
    assets.sort(key=lambda asset: -asset[1])
    total, total_gz = sum(a[1] for a in assets), sum(a[2] for a in assets)
    rows = [[code(name), kb(raw), kb(gz)] for name, raw, gz in assets[:8]]
    rows.append(["**Total**", f"**{kb(total)}**", f"**{kb(total_gz)}**"])
    body = table(["Asset", "Size", "Gzip"], rows, "lrr") + more(
        len(assets), len(rows) - 1, "`dist/`"
    )
    large = [name for name, raw, _ in assets if name.endswith(".js") and raw > VITE_CHUNK_LIMIT]
    if large:
        body += (
            f"\n\n{plural(len(large), 'chunk')} over 500 kB slow down the first page load —"
            " consider splitting routes with `import()`."
        )
    return Check("Bundle", "bundle", "warn" if large else "pass", f"{kb(total_gz)} gzip", body)


def audit_fix(fix) -> str:
    if fix is True:
        return "`npm audit fix`"
    if isinstance(fix, dict):
        return "breaking: " + code(f"{fix.get('name', '')}@{fix.get('version', '')}")
    return "none"


def dependencies_check(d: Path) -> Check | None:
    audit = read_json(d / "npm-audit.json") or {}
    deprecated = NPM_DEPRECATED.findall(ANSI.sub("", read(d / "npm-install.log")))
    if not audit and not deprecated:
        return None
    counts = audit.get("metadata", {}).get("vulnerabilities", {})
    summary = [f"{counts[s]} {s}" for s in SEVERITIES if counts.get(s)]
    vulnerable = bool(summary)
    parts = []
    if vulnerable:
        rank = {severity: i for i, severity in enumerate(SEVERITIES)}
        items = sorted(
            audit.get("vulnerabilities", {}).items(),
            key=lambda i: rank.get(i[1].get("severity"), 9),
        )
        rows = []
        for name, vuln in items[:MAX_ROWS]:
            advisory = next((v for v in vuln.get("via", []) if isinstance(v, dict)), None)
            if advisory:
                title = cell(advisory.get("title", ""), 90)
                text = f"[{title}]({advisory['url']})" if advisory.get("url") else title
            else:
                text = "via " + ", ".join(code(v) for v in vuln.get("via", [])[:3])
            direct = "yes" if vuln.get("isDirect") else "no"
            rows.append(
                [
                    code(name),
                    vuln.get("severity", ""),
                    direct,
                    text,
                    audit_fix(vuln.get("fixAvailable")),
                ]
            )
        audit_table = table(["Package", "Severity", "Direct", "Advisory", "Fix"], rows)
        parts.append(f"**npm audit**\n\n{audit_table}" + more(len(items), len(rows), "`npm audit`"))
    if deprecated:
        rows = [[code(package), cell(message, 140)] for package, message in deprecated[:5]]
        parts.append("**Deprecated packages**\n\n" + table(["Package", "Note"], rows))
        summary.append(f"{len(deprecated)} deprecated")
    status = "warn" if vulnerable else "info" if deprecated else "pass"
    body, note = "\n\n".join(parts), "no known vulnerabilities"
    return Check(
        "Dependencies", "deps", status, ", ".join(summary), body, overview=False, note=note
    )


def collect_ai(d: Path, outcomes: dict[str, str], base: Path) -> list[Check]:
    checks = []
    if outcomes.get("install") == "failure":
        checks.append(Check("Install", "install", "fail", "pip install failed", "See the job log."))

    problems, fixable = [], 0
    for item in read_json(d / "ruff.json") or []:
        row = (item.get("location") or {}).get("row")
        problems.append(
            Problem(
                "error", item.get("message", ""), item.get("filename"), row, item.get("code") or ""
            )
        )
        fixable += (item.get("fix") or {}).get("applicability") == "safe"
    checks.append(
        lint_check("Lint (Ruff)", problems, outcomes.get("lint"), base, fixable, "ruff check --fix")
    )

    suites = parse_junit(d / "pytest.xml")
    empty = "No tests were collected."
    checks.append(
        tests_check(
            suites, outcomes.get("test"), base, empty=empty, log=d / "pytest.log", tool="pytest"
        )
    )

    if (d / "format.json").exists() or (d / "format.exit").exists():
        files = sorted(
            {
                item["filename"]
                for item in read_json(d / "format.json") or []
                if item.get("filename")
            }
        )
        checks.append(format_check(files, exit_code(d / "format.exit"), "ruff format", base, 1))
    return checks


def collect_infra(d: Path, outcomes: dict[str, str], base: Path) -> list[Check]:
    checks = []
    if outcomes.get("init") == "failure":
        checks.append(Check("Init", "init", "fail", "failed", code_block(log_tail(d / "init.log"))))

    # Root configurations, as (directory relative to base, report file suffix).
    configs = [("", "main"), ("bootstrap/", "bootstrap")]

    validate = outcomes.get("validate")
    if skipped := not_run("Validate", "validate", validate):
        checks.append(skipped)
    else:
        problems, errors = [], 0
        for prefix, suffix in configs:
            result = read_json(d / f"validate-{suffix}.json") or {}
            errors += result.get("error_count") or 0
            for diag in result.get("diagnostics", []):
                where = diag.get("range") or {}
                file = prefix + where["filename"] if where.get("filename") else None
                line = (where.get("start") or {}).get("line")
                message = diag.get("summary", "") + (
                    f": {diag['detail']}" if diag.get("detail") else ""
                )
                level = diag.get("severity", "error")
                problems.append(Problem(level, message, file, line))
                annotate(level, message, file, line, base, "tofu validate")
        if validate == "failure" or errors:
            body = problems_table(problems, base) if problems else "See the job log."
            checks.append(
                Check("Validate", "validate", "fail", count_summary(problems) or "failed", body)
            )
        elif problems:
            body = problems_table(problems, base)
            checks.append(Check("Validate", "validate", "warn", count_summary(problems), body))
        else:
            checks.append(Check("Validate", "validate", "pass", note="configuration is valid"))

    suites = [
        suite
        for prefix, suffix in configs
        for suite in parse_tofu_test(d / f"test-{suffix}.jsonl", prefix)
    ]
    checks.append(
        tests_check(
            suites,
            outcomes.get("test"),
            base,
            empty="There are no `*.tftest.hcl` files.",
            log=d / "test.log",
            list_all=True,
            tool="tofu test",
        )
    )

    if (d / "format.log").exists():
        code_exit = exit_code(d / "format.exit")
        files = read(d / "format.log").split() if code_exit == 3 else []
        checks.append(format_check(files, code_exit, "tofu fmt -recursive", base, 3))
    return checks


COLLECTORS = {
    "backend": collect_backend,
    "frontend": collect_frontend,
    "ai": collect_ai,
    "infra": collect_infra,
}


# --- Rendering -----------------------------------------------------------------------------------


def overview_cell(report: ModuleReport) -> str:
    items = []
    for check in report.checks:
        # Secondary checks (formatting, dependencies) only show up here when they need attention
        if not check.overview and check.status not in ("warn", "fail"):
            continue
        text = f"{check.label}: {check.summary}" if check.summary else f"{check.label} ✓"
        items.append(f"**{text}**" if check.status == "fail" else text)
    return " · ".join(items)


def section(report: ModuleReport) -> str:
    parts = []
    for check in report.checks:
        summary = check.summary or check.note
        head = f"{ICONS[check.status]} **{check.name}**" + (f" — {summary}" if summary else "")
        parts.append(head + (f"\n\n{check.body}" if check.body else ""))
    return "\n\n".join(parts)


def run_url() -> str | None:
    repository, run_id = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_RUN_ID")
    if not repository or not run_id:
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    return f"{server}/{repository}/actions/runs/{run_id}" + (
        f"/attempts/{attempt}" if attempt != "1" else ""
    )


def load_reports(d: Path, needs: dict) -> list[ModuleReport]:
    reports = []
    for module in [m for m in MODULES if m in needs] or [
        m for m in MODULES if (d / f"{m}.json").exists()
    ]:
        result = (needs.get(module) or {}).get("result")
        data = read_json(d / f"{module}.json")
        report = ModuleReport.from_json(data) if data else ModuleReport(module)
        if not data:
            status, text = {
                "failure": ("fail", "failed before writing its report — see the job log"),
                "cancelled": ("skip", "cancelled"),
                "skipped": ("skip", "skipped"),
            }.get(result or "", ("warn", "no report"))
            report.checks.append(Check("Job", "job", status, text))
        elif result == "failure" and report.status != "fail":
            report.checks.append(Check("Job", "job", "fail", "failed — see the job log"))
        reports.append(report)
    return reports


def render(d: Path, needs: dict, jobs: list[dict]) -> str:
    reports = load_reports(d, needs)
    failing = sum(report.status == "fail" for report in reports)
    if failing:
        header = f"### ❌ CI failed · {failing} of {plural(len(reports), 'module')}"
    elif any(report.status == "warn" for report in reports):
        header = "### ⚠️ CI passed with warnings"
    else:
        header = "### ✅ CI passed"

    by_name = {job.get("name"): job for job in jobs}
    rows, details = [], []
    for report in reports:
        title, stack = MODULES[report.module]
        job = by_name.get(report.module, {})
        name = f"[**{title}**]({job['html_url']})" if job.get("html_url") else f"**{title}**"
        started, completed = iso_time(job.get("started_at")), iso_time(job.get("completed_at"))
        took = seconds((completed - started).total_seconds()) if started and completed else ""
        icon = ICONS[report.status]
        rows.append([icon, f"{name} <sub>{stack}</sub>", overview_cell(report), took])
        is_open = " open" if report.status == "fail" else ""
        summary = f"<summary>{icon} {title} details</summary>"
        details.append(f"<details{is_open}>\n{summary}\n\n{section(report)}\n\n</details>")

    url = run_url()
    sha = (os.environ.get("HEAD_SHA") or os.environ.get("GITHUB_SHA") or "")[:7]
    footer = [f"Commit {code(sha)}"] if sha else []
    footer += [f"[CI run #{os.environ.get('GITHUB_RUN_NUMBER', '')}]({url})"] if url else []
    footer.append("updated " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    footer.append("this comment is refreshed on every push")
    overview = table(["", "Module", "Checks", "Time"], rows, "cllr")

    def assemble() -> str:
        return (
            "\n\n".join([MARKER, header, overview, *details, f"<sub>{' · '.join(footer)}</sub>"])
            + "\n"
        )

    comment = assemble()
    while len(comment) > COMMENT_LIMIT:  # replace the longest details with a pointer
        i = max(range(len(details)), key=lambda n: len(details[n]))
        title = MODULES[reports[i].module][0]
        where = f"[run summary]({url})" if url else "run summary"
        icon = ICONS[reports[i].status]
        details[i] = f"{icon} {title}: details are too long for a comment, see the {where}."
        comment = assemble()
    return comment


# --- Entry points --------------------------------------------------------------------------------


def report_dir(arg: str | None) -> Path:
    path = Path(
        arg
        or os.environ.get("REPORT_DIR")
        or Path(os.environ.get("RUNNER_TEMP", ".")) / "ci-report"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_summary(markdown: str) -> None:
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")


def cmd_collect(args: argparse.Namespace) -> None:
    d = report_dir(args.dir)
    outcomes = dict(item.split("=", 1) for item in args.outcome)
    report = ModuleReport(args.module, COLLECTORS[args.module](d, outcomes, Path.cwd()))
    (d / f"{args.module}.json").write_text(json.dumps(report.to_json(), indent=2), encoding="utf-8")
    title, stack = MODULES[report.module]
    append_summary(f"## {ICONS[report.status]} {title} ({stack})\n\n{section(report)}\n")
    for check in report.checks:
        print(
            f"{ICONS[check.status]} {check.name}" + (f": {check.summary}" if check.summary else "")
        )


def cmd_render(args: argparse.Namespace) -> None:
    d = report_dir(args.dir)
    needs = json.loads(os.environ.get("NEEDS") or "{}")
    jobs = (read_json(Path(args.jobs)) or {}).get("jobs", []) if args.jobs else []
    comment = render(d, needs, jobs)
    Path(args.out or d / "comment.md").write_text(comment, encoding="utf-8")
    append_summary(comment.removeprefix(MARKER))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="summarise one CI job")
    collect.add_argument("module", choices=sorted(COLLECTORS))
    collect.add_argument("--outcome", action="append", default=[], metavar="STEP=OUTCOME")
    collect.add_argument("--dir", help="report directory (default: $REPORT_DIR)")
    collect.set_defaults(func=cmd_collect)
    render_parser = sub.add_parser("render", help="combine the job reports into the PR comment")
    render_parser.add_argument("--dir", help="report directory (default: $REPORT_DIR)")
    render_parser.add_argument("--jobs", help="JSON from the 'list jobs for a workflow run' API")
    render_parser.add_argument("--out", help="output file (default: <dir>/comment.md)")
    render_parser.set_defaults(func=cmd_render)
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception:  # a broken report must not fail an otherwise green build
        print("::warning title=CI report::The report could not be generated, see the step log.")
        traceback.print_exc(file=sys.stdout)


if __name__ == "__main__":
    main()
