import pytest
import yaml

from tt_autoapply.profile_import import (
    map_pairs,
    merge_profile,
    missing_fields,
    parse_height_cm,
    parse_list,
    parse_playing_age,
    write_profile,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("18 - 25", {"min": 18, "max": 25}),
        ("18-25", {"min": 18, "max": 25}),
        ("18 to 25", {"min": 18, "max": 25}),
        ("18–25 years", {"min": 18, "max": 25}),
        ("21", {"min": 21, "max": 21}),
        ("not stated", None),
    ],
)
def test_parse_playing_age(value, expected):
    assert parse_playing_age(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("180cm", 180),
        ("180 cm", 180),
        ("1.80m", 180),
        ("5'11\"", 180),
        ("5ft 11", 180),
        ("6'", 183),
        ("180", 180),
        ("tall", None),
    ],
)
def test_parse_height_cm(value, expected):
    assert parse_height_cm(value) == expected


def test_parse_list_splits_and_dedupes():
    assert parse_list("Guitar, Piano; Stage Combat") == ["Guitar", "Piano", "Stage Combat"]
    assert parse_list("RP\nRP\nCockney") == ["RP", "Cockney"]
    assert parse_list("") == []


def test_map_pairs_reads_a_realistic_profile_page():
    pairs = [
        ("Name", "Test Performer"),
        ("Playing Age", "18 - 25"),
        ("Height", "5'11\""),
        ("Ethnic Appearance", "White British"),
        ("Eye Colour", "Blue"),
        ("Special Skills", "Guitar, Football, Driving Licence"),
        ("Accents", "RP, Cockney"),
        ("Favourite Colour", "Green"),  # unmapped, must be ignored
    ]
    got = map_pairs(pairs)
    assert got["name"] == "Test Performer"
    assert got["playing_age"] == {"min": 18, "max": 25}
    assert got["height_cm"] == 180
    assert got["ethnicity"] == "White British"
    assert got["eyes"] == "Blue"
    assert got["skills"] == ["Guitar", "Football", "Driving Licence"]
    assert got["accents"] == ["RP", "Cockney"]
    assert "Favourite Colour" not in got and "favourite_colour" not in got


def test_map_pairs_takes_the_first_occurrence():
    got = map_pairs([("Playing Age", "18-25"), ("Playing age", "40-50")])
    assert got["playing_age"] == {"min": 18, "max": 25}


def test_merge_keeps_values_the_import_did_not_find():
    existing = {"name": "Me", "email": "me@example.com", "phone": "07700 900000"}
    imported = {"playing_age": {"min": 18, "max": 25}, "email": ""}
    merged, changes = merge_profile(existing, imported)

    assert merged["phone"] == "07700 900000", "untouched field must survive"
    assert merged["email"] == "me@example.com", "empty import must not blank a real value"
    assert merged["playing_age"] == {"min": 18, "max": 25}
    assert any("playing_age" in c for c in changes)


def test_merge_reports_overwrites():
    merged, changes = merge_profile({"ethnicity": "Wrong"}, {"ethnicity": "White British"})
    assert merged["ethnicity"] == "White British"
    assert changes == ["ethnicity: Wrong -> White British"]


def test_merge_is_quiet_when_nothing_changed():
    _, changes = merge_profile({"name": "Me"}, {"name": "Me"})
    assert changes == []


def test_missing_fields_flags_what_the_matcher_needs():
    assert "playing_age" in missing_fields({"name": "Me"})
    complete = {
        "name": "Me",
        "email": "me@example.com",
        "base": "London",
        "gender": "male",
        "ethnicity": "White British",
        "playing_age": {"min": 18, "max": 25},
    }
    assert missing_fields(complete) == []


def test_write_profile_backs_up_the_previous_version(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("name: Old Name\n")

    backup = write_profile(path, {"name": "New Name"})

    assert yaml.safe_load(path.read_text())["name"] == "New Name"
    assert backup is not None
    assert yaml.safe_load(backup.read_text())["name"] == "Old Name"


def test_write_profile_with_no_existing_file(tmp_path):
    path = tmp_path / "profile.yaml"
    assert write_profile(path, {"name": "Me"}) is None
    assert yaml.safe_load(path.read_text())["name"] == "Me"
