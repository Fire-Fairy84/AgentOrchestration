#!/usr/bin/env python3
"""Validate that workflow action references are pinned to commit SHAs."""

from __future__ import annotations

from pathlib import Path
import re
import sys


DEFAULT_WORKFLOW_DIR = Path(".github/workflows")
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
USES_LINE = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)")


def is_local_action(reference: str) -> bool:
    return reference.startswith("./") or reference.startswith("../")


def find_mutable_action_refs(
    workflow_dir: Path = DEFAULT_WORKFLOW_DIR,
) -> list[str]:
    failures: list[str] = []
    for workflow in sorted(workflow_dir.glob("*.y*ml")):
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = USES_LINE.match(line)
            if not match:
                continue

            action_ref = match.group(1)
            if is_local_action(action_ref):
                continue

            if "@" not in action_ref:
                failures.append(
                    f"{workflow}:{line_number}: missing @ref in {action_ref}"
                )
                continue

            version = action_ref.rsplit("@", 1)[1]
            if not FULL_SHA.fullmatch(version):
                failures.append(
                    f"{workflow}:{line_number}: pin {action_ref} to a full "
                    "40-character commit SHA"
                )

    return failures


def main() -> int:
    failures = find_mutable_action_refs()
    if not failures:
        print("All external workflow actions are pinned to full commit SHAs.")
        return 0

    print("Mutable workflow action references found:")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
