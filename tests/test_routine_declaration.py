"""0.4 (owner decision D2; BRIEF RS-W2-1b, RS-W2-2 §2.1): `Declaration.out`, the routine declaration, the reader
shapes, and the census of this package's registry entries (0 undeclared)."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from trellis_analytics.declaration import Declaration, Field, refusal
from trellis_analytics.readers import ODS_READS, CatalogueScopeRead, OdsRead
from trellis_analytics.readers.shapes import READERS
from trellis_analytics.routine import (BINDING_KINDS, ROUTINE_KINDS, Binding, ParamDeclaration, ReaderDeclaration,
                                       RoutineDeclaration, TileSafety, routine_declaration)

ABSENCE = {"not_measured": "a", "not_permitted": "b", "not_applicable": "c", "nothing_found": "d"}
OUT = [{"name": "n", "label": "N", "type": "int"}, {"name": "as_of", "label": "As of", "type": "datetime"},
       {"name": "total", "label": "Total", "type": "int"}]


def decl(**kw):
    body = {"result_kind": "measure", "absence": ABSENCE,
            "measures": [{"name": "n", "unit": "things", "as_of": "as_of", "value_field": "n",
                          "basis": {"denominator_field": "total", "denominator_label": "things in all"}}]}
    return Declaration.model_validate({**body, **kw})


# ── Declaration.out ──

def test_out_is_optional_and_a_03_declaration_loads_unchanged():
    d = decl()
    assert d.out is None and d.out_fields() == []


def test_out_inline_registered_or_shape():
    assert [f.name for f in decl(out=OUT).out_fields()] == ["n", "as_of", "total"]
    assert [f.name for f in decl(out={"fields": OUT}).out_fields()] == ["n", "as_of", "total"]
    from trellis_analytics.declaration import register_shape
    register_shape("TestOutShape", {"fields": OUT})
    assert decl(out="TestOutShape").out_field("total").label == "Total"


@pytest.mark.parametrize("out, words", [
    ("NoSuchShape", "out names shape 'NoSuchShape', which is not registered"),
    (OUT[:2], "basis.denominator_field 'total' names 'total', which is not a field of out"),
    ([OUT[1], OUT[2]], "value_field 'n' names 'n', which is not a field of out"),
    (OUT + [OUT[0]], "out declares field n more than once"),
])
def test_out_refusals_name_the_field(out, words):
    with pytest.raises(ValidationError) as exc:
        decl(out=out)
    assert words in refusal(exc.value)


def test_a_run_as_of_and_a_dotted_or_counted_path_check_their_first_part():
    d = decl(measures=[{"name": "n", "unit": "things", "as_of": "run.read_snapshot", "value_field": "rows[]"}],
             out=[{"name": "rows", "label": "Rows", "type": "list<object>"}])
    assert d.measures[0].value_field == "rows[]"


@pytest.mark.parametrize("type_", ["object", "list<object>", "map<string,list<int>>", "map<string, list<string>>"])
def test_the_04_field_types(type_):
    assert Field(name="x", label="X", type=type_).type == type_


@pytest.mark.parametrize("type_", ["list<list<int>>", "map<int,int>", "map<string,map<string,int>>", "json"])
def test_types_that_stay_refused(type_):
    with pytest.raises(ValidationError, match="is not a field type"):
        Field(name="x", label="X", type=type_)


# ── RoutineDeclaration ──

def test_a_name_is_the_whole_minimum():
    r = RoutineDeclaration(name="r")
    assert (r.kind, r.inputs, r.params, r.bindings, r.declaration, r.tile_safe) == ("routine", [], [], [], None, None)


def test_the_vocabularies():
    assert ROUTINE_KINDS == ("producer", "processor", "routine", "step")
    assert BINDING_KINDS == ("python", "egeria_query", "sql", "step")


@pytest.mark.parametrize("body, words", [
    ({"name": "a.b"}, "routine name 'a.b' is not an identifier"),
    ({"name": "r", "inputs": ["ods"]}, "input 'ods' is not a role word"),
    ({"name": "r", "inputs": ["subject", "subject"]}, "declares an input more than once"),
    ({"name": "r", "params": [{"name": "k"}], "constants": {"k": 1}}, "declares k as a parameter and a constant"),
    ({"name": "r", "params": [{"name": "k"}, {"name": "k"}]}, "declares parameter k more than once"),
    ({"name": "r", "bindings": [{"kind": "python", "target": "a.b"}, {"kind": "python", "target": "a.c"}]},
     "more than one python binding"),
    ({"name": "r", "bindings": [{"kind": "python", "target": "nodots"}]}, "is not a dotted import path"),
    ({"name": "r", "bindings": [{"kind": "rest", "target": "x"}]}, "bindings.0.kind"),
    ({"name": "r", "in": OUT}, "only a processor reads"),
    ({"name": "r", "kind": "processor", "in": "NoSuchShape"}, "reads shape 'NoSuchShape' (in)"),
    ({"name": "r", "generic": True, "binding_note": "fixed"}, "a generic routine fixes nothing"),
    ({"name": "r", "tile_safe": {"safe": True, "reason": " "}}, "tile_safe declares no reason"),
    ({"name": "r", "tile_safe": {"safe": False, "cap": {"page_size": 50}, "reason": "x"}}, "a cap says within"),
    ({"name": "r", "params": [{"name": "k", "required": True, "default": 3}]}, "is required and has a default"),
    ({"name": "r", "colour": "red"}, "colour is not a declaration field"),
])
def test_routine_refusals(body, words):
    with pytest.raises(ValidationError) as exc:
        RoutineDeclaration.model_validate(body)
    assert words in refusal(exc.value)


def test_in_is_the_json_key_and_a_dump_round_trips():
    r = RoutineDeclaration.model_validate({
        "name": "derive_share", "kind": "processor", "in": OUT, "params": [{"name": "k", "type": "int", "default": 3}],
        "constants": {"population": "repository"}, "inputs": ["egeria_client:EgeriaTech", "reader:ods", "viewer"],
        "declaration": decl(out=OUT).model_dump(exclude_none=True), "pushdown": ["count by the repository"],
        "tile_safe": {"safe": True, "cap": {"k": 10}, "reason": "0.2-0.8 s repository count"},
        "admission": {"resource_types": ["database"], "test_only": True},
        "bindings": [{"kind": "python", "target": "pkg.mod.fn"}, {"kind": "egeria_query", "target": "Saved query"}]})
    dumped = json.loads(r.model_dump_json(by_alias=True, exclude_none=True))
    assert "in" in dumped and "in_" not in dumped
    assert RoutineDeclaration.model_validate(dumped) == r
    assert [f.name for f in r.in_fields()] == ["n", "as_of", "total"] and r.python_target() == "pkg.mod.fn"


# ── the three library routines, and the census ──

def test_every_registry_entry_this_package_ships_is_declared():
    """The census, for the library's own entries: none is undeclared (8813 read 3 of 37 undeclared before 0.4)."""
    import tomllib
    from importlib import import_module
    from pathlib import Path
    eps = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    ours = eps["project"]["entry-points"]["pyegeria.analytics"]
    for name, value in ours.items():
        mod, _, attr = value.partition(":")
        m = getattr(import_module(mod), attr)
        assert isinstance(m.declaration, Declaration), f"{name} is undeclared"
        assert m.declaration.absence.nothing_found, name
    from trellis_analytics.manifests import ROUTINES
    assert set(ROUTINES) == set(ours)


def test_each_routine_declaration_is_read_from_its_manifest():
    from trellis_analytics import manifests as M
    for manifest, routine in ((M.CURATION_COVERAGE, M.CURATION_COVERAGE_ROUTINE), (M.CONTEXT_PACK, M.CONTEXT_PACK_ROUTINE),
                              (M.CURATION_COVERAGE_TILE, M.CURATION_COVERAGE_TILE_ROUTINE)):
        assert routine.name == manifest.name and routine.version == manifest.version
        assert routine.bindings == [Binding(kind="python", target=manifest.function)]
        assert routine.declaration is manifest.declaration
        assert routine.admission.resource_types == manifest.resource_types
        assert routine.tile_safe is not None and routine.inputs


def test_the_declared_params_are_the_functions_params():
    import inspect
    from trellis_analytics import manifests as M
    from trellis_analytics.portal import curation_coverage_kpi
    from trellis_analytics.routines import context_pack, curation_coverage
    assert [p.name for p in M.CURATION_COVERAGE_TILE_ROUTINE.params] == list(inspect.signature(curation_coverage_kpi).parameters)
    # curation_coverage's readers are inputs, not params
    assert {p.name for p in M.CURATION_COVERAGE_ROUTINE.params} == set(inspect.signature(curation_coverage).parameters) - {"ods", "catalogue"}
    assert {p.name for p in M.CONTEXT_PACK_ROUTINE.params} == set(inspect.signature(context_pack).parameters) - {"reader", "re_held"}


def test_curation_coverage_declares_its_out_fields():
    from trellis_analytics.manifests import CURATION_COVERAGE_ROUTINE as R
    names = [f.name for f in R.out_fields()]
    assert names[-2:] == ["published_schemas", "not_yet_schemas"]
    assert [m.basis.denominator_field for m in R.declaration.measures] == ["known_schemas", "known_schemas"]
    groups = R.declaration.out_field("groups")
    assert (groups.kind, groups.shape) == ("dataset", "CountGroup")


def test_a_pyegeria_registry_entry_reads_as_a_routine_declaration():
    """The other direction of the mirror: any AnalyticFunctionSpec reads here (its params and function carried)."""
    from pyegeria.view.analytic_registry import get_analytic_registry
    spec = get_analytic_registry()["count_elements"]
    r = routine_declaration(spec)
    assert r.python_target() == spec.function and [p.name for p in r.params] == [p.name for p in spec.params]
    assert r.generic is True


# ── the readers ──

def test_the_readers_declare_what_curation_coverage_reads():
    assert set(READERS) == {"ods", "catalogue_scope"}
    assert {"commit_proofs", "catalogue_scope_events", "outbox_status_counts"} <= set(READERS["ods"].reads)
    assert set(READERS["ods"].reads) <= set(ODS_READS), "a declared read is a read of the Protocol"
    assert set(READERS["catalogue_scope"].reads) == {n for n in CatalogueScopeRead.__dict__ if not n.startswith("_")}
    assert READERS["ods"].fields("outbox_status_counts") == []
    assert "detail" in [f.name for f in READERS["ods"].fields("commit_proofs")]
    assert READERS["ods"].undeclared(ODS_READS) == [r for r in ODS_READS if r not in READERS["ods"].reads]
    assert hasattr(OdsRead, "commit_proofs")


def test_the_reader_shapes_cover_the_fields_the_routine_reads():
    """Every key curation_coverage reads off a proof, an event or the node set is a declared field."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src/trellis_analytics/routines/curation_coverage.py").read_text()
    read = set(re.findall(r'\b(?:p|e|ev|last|report|endpoint|s)\["([a-z_]+)"\]', src))
    declared = {f.name for r in ("commit_proofs", "catalogue_scope_events") for f in READERS["ods"].fields(r)}
    declared |= {f.name for f in READERS["catalogue_scope"].fields("node_set")}
    from trellis_analytics.declaration import resolve_fields
    declared |= {f.name for _, f in resolve_fields("NodeSetSchema")}
    assert read and read <= declared, read - declared


def test_reader_refusals():
    with pytest.raises(ValidationError, match="neither a registered shape nor a field type"):
        ReaderDeclaration(name="x", reads={"r": "NoSuchShape"})
    with pytest.raises(ValidationError, match="rows are of a shape"):
        ReaderDeclaration(name="x", reads={"r": "int"}, many={"r": True})
    with pytest.raises(ValidationError, match="declares no shape for it"):
        ReaderDeclaration(name="x", many={"r": True})


def test_param_and_tile_safety_models():
    assert ParamDeclaration(name="k").category == "content"
    assert TileSafety(safe=True, reason="0.2 s").cap == {}


def test_the_04_words_pyegeria_mirrors_on_measures_and_fields():
    from trellis_analytics.declaration import MeasureDeclaration
    m = MeasureDeclaration(name="n", unit="things", as_of="as_of", value_field="n", population="repository")
    assert m.population == "repository"
    with pytest.raises(ValidationError, match="population 'scope' is not one of the populations"):
        MeasureDeclaration(name="n", unit="things", as_of="as_of", value_field="n", population="scope")
    assert Field(name="x", label="X", type="int", description="how many").description == "how many"
