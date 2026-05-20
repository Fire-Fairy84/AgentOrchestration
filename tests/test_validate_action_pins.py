from pathlib import Path
import importlib.util


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github/scripts/validate_action_pins.py"
)
SPEC = importlib.util.spec_from_file_location(
    "validate_action_pins",
    SCRIPT_PATH,
)
validate_action_pins = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_action_pins)


def write_workflow(tmp_path: Path, content: str) -> Path:
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yml").write_text(content, encoding="utf-8")
    return workflow_dir


def test_accepts_full_sha_and_local_actions(tmp_path: Path):
    workflow_dir = write_workflow(
        tmp_path,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: ./.github/actions/local-action
""",
    )

    assert validate_action_pins.find_mutable_action_refs(workflow_dir) == []


def test_rejects_tag_refs(tmp_path: Path):
    workflow_dir = write_workflow(
        tmp_path,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""",
    )

    failures = validate_action_pins.find_mutable_action_refs(workflow_dir)

    assert len(failures) == 1
    assert "actions/checkout@v4" in failures[0]


def test_rejects_missing_refs(tmp_path: Path):
    workflow_dir = write_workflow(
        tmp_path,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout
""",
    )

    failures = validate_action_pins.find_mutable_action_refs(workflow_dir)

    assert len(failures) == 1
    assert "missing @ref" in failures[0]
