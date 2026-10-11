#!/usr/bin/env python3
"""One version for the whole monorepo, worked out from git history.

`compute` finds the newest release tag (vX.Y.Z), reads the Conventional Commits made since then and
bumps it: a breaking change (`feat!:` or a `BREAKING CHANGE:` footer) bumps MAJOR, `feat` bumps MINOR,
anything else bumps PATCH. On `main` the result is a release version (0.2.0); on any other branch
(`develop`) it is a pre-release of that next version, numbered by the commits since the release
(0.2.0-dev.7). With no release tag yet the count starts from 0.0.0.

`stamp <version>` writes the version into the module manifests (frontend/package.json,
ai/pyproject.toml) in the working copy, so a build or image made afterwards carries it. The backend
takes it on the command line instead: `dotnet build -p:Version=<version>`.

Standard library only, so it runs on a bare runner image.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
BREAKING = re.compile(r"^\w+(\([^)]*\))?!:|^BREAKING[ -]CHANGE:", re.MULTILINE)
FEATURE = re.compile(r"^feat(\([^)]*\))?:", re.MULTILINE)
RELEASE_BRANCHES = {"main", "master"}
PRERELEASE_LABEL = "dev"
ROOT = Path(__file__).resolve().parents[2]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def last_release() -> tuple[str | None, tuple[int, int, int]]:
    """Newest vX.Y.Z tag in the repository, reachable or not.

    `develop` never contains the merge commit a release tag sits on, so looking only at its own
    history would miss releases made on `main`.
    """
    best: tuple[str | None, tuple[int, int, int]] = (None, (0, 0, 0))
    for tag in git("tag", "--list", "v*").splitlines():
        match = RELEASE_TAG.match(tag)
        if match:
            version = tuple(int(part) for part in match.groups())
            if best[0] is None or version > best[1]:
                best = (tag, version)  # type: ignore[assignment]
    return best


def compute(branch: str, ref: str = "HEAD") -> dict[str, object]:
    tag, (major, minor, patch) = last_release()
    span = f"{tag}..{ref}" if tag else ref
    # Merge commits count too: GitHub puts the PR title in their body
    messages = git("log", "--format=%B%x00", span).split("\x00")
    messages = [message.strip() for message in messages if message.strip()]
    commits = int(git("rev-list", "--count", span))

    if any(BREAKING.search(message) for message in messages):
        bump, major, minor, patch = "major", major + 1, 0, 0
    elif any(FEATURE.search(message) for message in messages):
        bump, minor, patch = "minor", minor + 1, 0
    else:
        bump, patch = "patch", patch + 1

    release = branch in RELEASE_BRANCHES
    version = f"{major}.{minor}.{patch}"
    if not release:
        version += f"-{PRERELEASE_LABEL}.{commits}"
    return {
        "version": version,
        "tag": f"v{version}",
        "previous": tag or "",
        "bump": bump,
        "commits": commits,
        "release": release,
        # Nothing new since the last release: no new version to give out
        "changed": commits > 0,
    }


def stamp(version: str) -> list[str]:
    changed = []

    package = ROOT / "frontend" / "package.json"
    if package.exists():
        data = json.loads(package.read_text(encoding="utf-8"))
        data["version"] = version
        package.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        changed.append(str(package.relative_to(ROOT)))

    pyproject = ROOT / "ai" / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        # Only the `version` key of the [project] table
        new, count = re.subn(
            r'(\[project\][^\[]*?^version\s*=\s*)"[^"]*"',
            rf'\g<1>"{version}"',
            text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
        if count:
            pyproject.write_text(new, encoding="utf-8")
            changed.append(str(pyproject.relative_to(ROOT)))

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    compute_cmd = commands.add_parser("compute", help="print the version for this commit")
    compute_cmd.add_argument(
        "--branch",
        default=os.environ.get("GITHUB_REF_NAME") or git("rev-parse", "--abbrev-ref", "HEAD"),
    )
    compute_cmd.add_argument("--ref", default="HEAD")
    stamp_cmd = commands.add_parser("stamp", help="write a version into the module manifests")
    stamp_cmd.add_argument("version")
    args = parser.parse_args()

    if args.command == "compute":
        result = compute(args.branch, args.ref)
        print(json.dumps(result, indent=2))
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as file:
                for key, value in result.items():
                    value = str(value).lower() if isinstance(value, bool) else value
                    file.write(f"{key}={value}\n")
    else:
        for path in stamp(args.version):
            print(f"{path}: {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
