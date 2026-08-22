"""Setting profile details from the command line, so no YAML editing."""

import pytest
import yaml

from tt_autoapply.cli import SETTABLE, build_parser, cmd_set
from tt_autoapply.profile_import import missing_fields

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "config.yaml").write_text(
        (ROOT / "config.example.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "profile.yaml").write_text(
        (ROOT / "profile.example.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def run(workspace, *argv) -> int:
    args = build_parser().parse_args(
        ["-c", str(workspace / "config.yaml"), "set", *argv]
    )
    return cmd_set(args)


def profile(workspace) -> dict:
    return yaml.safe_load((workspace / "profile.yaml").read_text())


def test_sets_the_contact_details(workspace):
    assert run(workspace, "--name", "Logan Ahern", "--email", "me@example.com") == 0
    saved = profile(workspace)
    assert saved["name"] == "Logan Ahern"
    assert saved["email"] == "me@example.com"


def test_leaves_everything_else_alone(workspace):
    run(workspace, "--name", "Logan Ahern")
    saved = profile(workspace)
    assert saved["age"] == 21
    assert saved["gender"] == "male"
    assert saved["ethnicity"] == "White British"
    assert saved["playing_age"] == {"min": 18, "max": 25}


def test_keeps_a_backup(workspace):
    run(workspace, "--name", "Logan Ahern")
    backup = workspace / "profile.yaml.bak"
    assert backup.exists()
    assert yaml.safe_load(backup.read_text())["name"] == "Your Name"


def test_age_must_be_a_number(workspace):
    assert run(workspace, "--age", "twentyone") == 1
    assert profile(workspace)["age"] == 21, "a bad value must not overwrite"


def test_age_is_stored_as_a_number(workspace):
    run(workspace, "--age", "22")
    assert profile(workspace)["age"] == 22


def test_no_arguments_reports_status_without_writing(workspace):
    before = (workspace / "profile.yaml").read_text()
    assert run(workspace) == 1
    assert (workspace / "profile.yaml").read_text() == before


def test_filling_in_contacts_completes_the_profile(workspace):
    run(workspace, "--name", "Logan Ahern", "--email", "me@example.com")
    assert missing_fields(profile(workspace)) == []


def test_every_settable_field_round_trips(workspace):
    values = {
        "name": "A Name", "email": "a@example.com", "phone": "07700 900000",
        "base": "Manchester", "age": "30", "gender": "male",
        "ethnicity": "White British",
    }
    argv = [arg for key, value in values.items() for arg in (f"--{key}", value)]
    assert run(workspace, *argv) == 0
    saved = profile(workspace)
    for key, value in values.items():
        assert str(saved[key]) == value
    assert set(values) == set(SETTABLE)
