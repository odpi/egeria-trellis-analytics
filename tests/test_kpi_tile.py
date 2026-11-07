"""BRIEF RS-W2-1b (0.4): the curation-coverage tile rendered from the routine's declaration (`render.kpi_tile`) is
byte-identical to the 0.3.1 hand-built tile (frozen in tests/fixtures/legacy_tile.py), in every state the routine has.

The same result goes through both, so nothing needs masking: the envelope's timestamp is one value. The readers are
fakes that bind the seam's signatures (RE is not installed here)."""
from __future__ import annotations

import importlib
import json
import sys
import warnings
from pathlib import Path

import pytest

from trellis_analytics import portal
from trellis_analytics.declaration import LegacyApiWarning
from trellis_analytics.manifests import CURATION_COVERAGE_ROUTINE
from trellis_analytics.readers import OdsUnreadable, ReaderMissing
from trellis_analytics.render import kpi_tile
from trellis_analytics.routines import curation_coverage
from trellis_analytics.routines.curation_coverage import no_reader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.legacy_tile import legacy_tile  # noqa: E402

cc = importlib.import_module("trellis_analytics.routines.curation_coverage")


class FakeOds:
    def __init__(self, proofs=(), events=(), outbox=None, broken=False):
        self._proofs, self._events, self._outbox, self._broken = list(proofs), list(events), outbox or {}, broken

    def commit_proofs(self, slug: str) -> list[dict]:
        if self._broken:
            raise OdsUnreadable("the registry did not answer: disk I/O error")
        return [dict(p) for p in self._proofs]

    def catalogue_scope_events(self, slug: str) -> list[dict]:
        return [dict(e) for e in self._events]

    def outbox_status_counts(self, entity_type: str, slug: str) -> dict[str, list[int]]:
        return dict(self._outbox)


class FakeCatalogue:
    def __init__(self, names):
        self._names = names

    def node_set(self, slug: str) -> dict:
        return {"schemas": [{"schema": n, "classification": ""} for n in self._names] +
                           [{"schema": "pg_catalog", "classification": "system"}],
                "chosen": {"kind": "egeria", "as_of": "2026-11-01T10:00:00", "schemas": len(self._names), "tables": 3,
                           "merged": False},
                "egeria": {"state": "measured"}, "local": {}, "disagree": False}


def proof(i, kind, schema="", node="schema", detail=None, at="2026-10-31T12:00:00"):
    return {"id": i, "node_kind": node, "schema_name": schema, "table_name": "", "proof": kind,
            "element_guid": "", "read_at": at, "detail": detail or {}}


def event(i, schema, choice, source):
    return {"id": i, "node_kind": "schema", "schema_name": schema, "table_name": "", "choice": choice,
            "action": "set", "source": source, "proposal_rule": "", "changed_at": "2026-10-31T11:00:00"}


def _resolution(families):
    schemas = {}
    for fam, names in families.items():
        for n in names:
            schemas[n] = [{"guid": f"g-{n}", "family": fam, "own": False}]
    return {"error": "", "schemas": schemas}


SCHEMAS = ["aus", "eu", "hr", "lab", "pack_a", "pack_b", "pack_c", "sales", "us", "x_blocked"]


def _measured():
    proofs = [proof(1, "elements_read_back", "aus", detail={"tables": ["t1", "t2"]}),
              proof(2, "restored", "eu"),
              proof(3, "leave_out_blocked", "x_blocked"),
              proof(4, "report_published", node="database", detail={"annotation_count": 12}),
              proof(5, "endpoint_resolved", node="database",
                    detail={"resolution": _resolution({"Coco Server 1": ["pack_a", "pack_b"], "Coco-Server 1": ["pack_c"]})})]
    events = [event(1, "sales", "catalogue", "person"), event(2, "hr", "leave_out", "rule"),
              event(3, "lab", "catalogue", "rule"), event(4, "us", "leave_out", "person")]
    return FakeOds(proofs, events, outbox={"superseded": [7, 9], "sent": [1]}), FakeCatalogue(SCHEMAS)


RESULTS = {
    "measured": lambda: curation_coverage(*_measured()[:1], "database", "demo", _measured()[1]),
    "nothing_found": lambda: curation_coverage(FakeOds(), "database", "demo", FakeCatalogue(["a", "b"])),
    "not_established_no_survey": lambda: curation_coverage(FakeOds(), "database", "demo", FakeCatalogue([])),
    "not_established_unreadable": lambda: curation_coverage(FakeOds(broken=True), "database", "demo",
                                                            FakeCatalogue(["a"])),
    "not_established_no_reader": lambda: no_reader("database", "demo", ReaderMissing("catalogue_scope")),
    "not_applicable": lambda: curation_coverage(FakeOds(), "repository", "demo", FakeCatalogue(["a"])),
}


@pytest.mark.parametrize("case", sorted(RESULTS))
def test_the_rendered_tile_is_byte_identical_to_the_hand_built_one(case):
    result = RESULTS[case]()
    new = kpi_tile(CURATION_COVERAGE_ROUTINE, result, function=portal.TILE_FUNCTION)
    assert json.dumps(new, ensure_ascii=False) == json.dumps(legacy_tile(result), ensure_ascii=False)


def test_the_cases_cover_every_state_and_the_measured_case_every_line_kind():
    states = {RESULTS[c]().envelope.result_state.value for c in RESULTS}
    assert states == {"measured", "nothing_found", "not_established", "not_applicable"}
    keys = [k["key"] for k in kpi_tile(CURATION_COVERAGE_ROUTINE, RESULTS["measured"](), function="t")["kpis"]]
    assert {"published.report", "blocked.superseded", "not_yet.chosen", "not_yet.left_out_confirmed"} <= set(keys)
    assert "not_yet.in_other_family.coco_server_1_2" in keys, "two families that slug alike stay apart"


@pytest.fixture
def readers_of(monkeypatch):
    def install(ods, catalogue):
        made = {"ods": ods, "catalogue_scope": catalogue}
        monkeypatch.setattr(portal, "open_reader", lambda name, *a, **kw: made[name])
    return install


def test_the_registered_function_and_the_deprecated_name_serve_the_same_tile(readers_of):
    readers_of(*_measured())
    expected = legacy_tile(curation_coverage(*_measured()[:1], "database", "demo", _measured()[1]))
    tile = portal.curation_coverage_kpi("demo", "sqlite:///x")
    strip = lambda t: {**t, "provenance": t["provenance"].split(" · as of ")[0],
                       "manifest": {k: v for k, v in t["manifest"].items() if k != "as_of"}}
    assert strip(tile) == strip(expected)
    with pytest.warns(LegacyApiWarning, match="curation_coverage_kpi"):
        old = portal.curation_coverage_tile("demo", "sqlite:///x")
    assert strip(old) == strip(tile)


def test_counts_only_where_the_state_has_them():
    tile = kpi_tile(CURATION_COVERAGE_ROUTINE, RESULTS["not_established_no_reader"](), function="t")
    assert "Published" not in tile and "Not yet published" not in tile
    nf = kpi_tile(CURATION_COVERAGE_ROUTINE, RESULTS["nothing_found"](), function="t")
    assert (nf["Published"], nf["Not yet published"]) == (0, 2)


def test_the_aggregate_numbers_are_none_never_zero_without_counts():
    r = RESULTS["not_applicable"]()
    assert (r.published_schemas, r.not_yet_schemas) == (None, None)
    d = r.to_dict()
    assert d["published_schemas"] is None and d["not_yet_schemas"] is None


def test_every_declared_measure_field_resolves_on_the_real_result():
    d = CURATION_COVERAGE_ROUTINE.declaration
    r = RESULTS["measured"]().to_dict()
    for m in d.measures:
        assert isinstance(r[m.value_field], int), m.name
        assert m.as_of in r and m.basis.denominator_field in r
    assert set(r) == {f.name for f in d.out_fields()}, "out declares every field the result carries, and no other"


def test_the_renderer_refuses_a_routine_with_no_out():
    from trellis_analytics.manifests import CURATION_COVERAGE_TILE_ROUTINE
    with pytest.raises(ValueError, match="declares no out"):
        kpi_tile(CURATION_COVERAGE_TILE_ROUTINE, RESULTS["measured"](), function="t")


def test_the_registry_name_runs_the_rendered_tile():
    from trellis_analytics.manifests import CURATION_COVERAGE_TILE
    assert CURATION_COVERAGE_TILE.function == "trellis_analytics.portal.curation_coverage_kpi"
    with warnings.catch_warnings():
        warnings.simplefilter("error", LegacyApiWarning)
        tile = portal.curation_coverage_kpi("demo", "sqlite:///never-opened")   # no readers here: no warning, no count
    assert tile["state"] == "not_established"
