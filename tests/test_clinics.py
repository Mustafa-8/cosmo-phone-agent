"""Offline tests for phone_agent/tools/clinics.py. Run from the repo root:

    python -m tests.test_clinics
"""

from phone_agent.tools.clinics import _normalize_district, find_clinics


def test_dentists_all_districts():
    r = find_clinics("dentist")
    assert r["status"] == "ok", r
    assert {c["id"] for c in r["clinics"]} == {"dental-plus-vi", "buda-smile-xi"}


def test_dentist_in_district_arabic_number():
    r = find_clinics("dentist", "11")
    assert [c["id"] for c in r["clinics"]] == ["buda-smile-xi"], r


def test_district_without_match_falls_back():
    r = find_clinics("dermatologist", "XI")
    assert r["status"] == "ok" and len(r["clinics"]) == 1, r
    assert "other districts" in r["note"]


def test_unknown_specialty_is_error():
    r = find_clinics("cardiologist")
    assert r["status"] == "error", r


def test_specialty_is_case_insensitive():
    assert find_clinics(" Dentist ")["status"] == "ok"


def test_normalize_district():
    assert _normalize_district("6") == "VI"
    assert _normalize_district("6th") == "VI"
    assert _normalize_district("vi.") == "VI"
    assert _normalize_district("abc") == ""


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
