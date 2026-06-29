"""Release gate. The public web map ships DERIVED outputs only. No SDG&E (or raw
SCE) load-capacity value may appear in any file the browser loads. This test
greps every shipped data file for the utility load fields and asserts they are
absent, and it pins the property schema to an allowlist so a future build cannot
silently add a load column. If this fails, the SDG&E firewall is broken, STOP."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WEB_DATA = Path(__file__).resolve().parents[1] / "web" / "data"

# Utility load-capacity field names that must never ship. SDG&E ICAWNOF_UNILOAD
# is the legal one, the rest are raw SCE / generic load columns guarded for
# defense in depth.
FORBIDDEN = re.compile(
    r"ICAWNOF_UNILOAD|ICAWOF_UNILOAD|UNILOAD|ica_overall_load|"
    r"load_capacity_mw|section_mw|hosting_capacity|LoadCapacity",
    re.IGNORECASE,
)

# Only these derived properties are allowed to ship per file.
ALLOWED_PROPS = {
    "block_groups.geojson": {
        "geoid_bg", "county", "access", "rel_access", "pctile", "is_dac", "pop", "low_pop",
    },
    "candidates.geojson": {"candidate_id", "county", "tier"},
    "counties.geojson": {"county", "name"},
}

SHIPPED = sorted(ALLOWED_PROPS)


def _files():
    return [WEB_DATA / name for name in SHIPPED]


def test_web_data_files_exist():
    missing = [f.name for f in _files() if not f.exists()]
    assert not missing, f"shipped map data missing: {missing}"


@pytest.mark.parametrize("name", SHIPPED)
def test_no_utility_load_field_in_text(name):
    """Grep the raw bytes. No load-capacity field name anywhere in the file."""
    text = (WEB_DATA / name).read_text(encoding="utf-8")
    hits = sorted(set(m.group(0) for m in FORBIDDEN.finditer(text)))
    assert not hits, f"FIREWALL LEAK in {name}: forbidden token(s) {hits}"


@pytest.mark.parametrize("name", SHIPPED)
def test_property_schema_is_allowlisted(name):
    """No feature may carry a property outside the derived allowlist."""
    gj = json.loads((WEB_DATA / name).read_text(encoding="utf-8"))
    allowed = ALLOWED_PROPS[name]
    seen: set[str] = set()
    for feat in gj.get("features", []):
        seen.update((feat.get("properties") or {}).keys())
    extra = seen - allowed
    assert not extra, f"{name} ships non-allowlisted propert(ies): {sorted(extra)}"
