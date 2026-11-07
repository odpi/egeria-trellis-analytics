"""The manifests this package ships; each is an entry point in group `pyegeria.analytics`, so installing
the package registers it and a report spec names it by its `name`.

Since 0.4 every one carries a `declaration` (what its results are), and `ROUTINES` holds each as a
`RoutineDeclaration` (how it is called: inputs, params, bindings), read from the manifest so the two cannot disagree."""
from trellis_analytics import __version__
from trellis_analytics.declaration import Declaration
from trellis_analytics.manifest import RoutineManifest
from trellis_analytics.routine import routine_declaration
from trellis_analytics.routines.context_pack import DECLARATION as CONTEXT_PACK_DECLARATION
from trellis_analytics.routines.curation_coverage import DECLARATION as CURATION_COVERAGE_DECLARATION

CURATION_COVERAGE = RoutineManifest(
    name="curation_coverage",
    function="trellis_analytics.routines.curation_coverage.curation_coverage",
    description="Published, not yet published and blocked, counted from the curation record (analysis 1 of Curate's By analysis).",
    returns="CoverageResult (counts with the row ids they count, plus an Envelope)",
    source="ods",
    version=__version__,
    envelope=True,
    resource_types=["database"],
    family="Curation",
    tags=["curation", "coverage"],
    declaration=CURATION_COVERAGE_DECLARATION,
)

CONTEXT_PACK = RoutineManifest(
    name="context_pack",
    function="trellis_analytics.routines.context_pack.context_pack",
    description="Package what Egeria holds about one database for one kind of consumer: a tabular shape, a document shape and a manifest, each fact with its state word and provenance.",
    returns="ContextPack (tabular rows, documents, manifest, plus an Envelope)",
    source="egeria",
    version=__version__,
    envelope=True,
    resource_types=["database"],
    family="Context",
    tags=["context", "pack"],
    declaration=CONTEXT_PACK_DECLARATION,
)

#: The tile's own results: curation_coverage's two counts, keyed by their labels, and the same four sentences. It
#: declares no `out`: its keys are display labels ("Not yet published"), not field names.
CURATION_COVERAGE_TILE_DECLARATION = Declaration(
    result_kind="measure",
    scope="resource",
    measures=[{"name": "published", "unit": "schemas", "as_of": "manifest.read_back_at", "value_field": "Published"},
              {"name": "not_yet_published", "unit": "schemas", "as_of": "manifest.read_back_at",
               "value_field": "Not yet published"}],
    absence=CURATION_COVERAGE_DECLARATION.absence,
)

# The Portal tile's function, registered so its report spec names it `curation_coverage_tile` rather than by a Python
# path (Q2(b), project owner 2026-10-31). Since 0.4 it runs `portal.curation_coverage_kpi`: the tile rendered from
# curation_coverage's declaration by the KPI renderer.
CURATION_COVERAGE_TILE = RoutineManifest(
    name="curation_coverage_tile",
    function="trellis_analytics.portal.curation_coverage_kpi",
    description="The Portal tile for curation_coverage: its counts rendered as KPI rows and two bar values (format KPI, "
                "from the routine's declaration), with the result's state as the subtitle. Computes nothing of its own.",
    returns="dict (tile: state, subtitle, provenance, kpis, and Published / Not yet published when there are counts)",
    source="ods",
    version=__version__,
    envelope=False,
    resource_types=["database"],
    family="Curation",
    tags=["curation", "coverage", "portal"],
    declaration=CURATION_COVERAGE_TILE_DECLARATION,
)

_SUBJECT = [{"name": "resource_type", "type": "str", "default": "database",
             "description": "The resource's type; curation coverage is measured for databases."},
            {"name": "slug", "type": "str", "required": True, "description": "The resource's slug in RE's registry."}]
_REGISTRY_ONLY = {"safe": True, "reason": "runs on the Portal tile's request path today (RE's curation-coverage-tile "
                                          "route): fixed, parameterised registry SELECTs and one node-set resolution, "
                                          "no Egeria call"}

CURATION_COVERAGE_ROUTINE = routine_declaration(
    CURATION_COVERAGE,
    inputs=["reader:ods", "reader:catalogue_scope", "subject"],
    params=_SUBJECT,
    binding_note="Fixed to RE's curation record for one database (commit proofs, scope events, the outbox), counted "
                 "against Curate's node set.",
    tile_safe=_REGISTRY_ONLY,
)

CONTEXT_PACK_ROUTINE = routine_declaration(
    CONTEXT_PACK,
    inputs=["egeria_client:MetadataExpert", "viewer", "subject"],
    params=[{"name": "subject", "type": "str", "required": True,
             "description": "The database: its name, qualified name or GUID."},
            {"name": "consumer_kind", "type": "str", "required": True, "category": "shape",
             "description": "The kind of consumer the pack is for."},
            {"name": "identity", "type": "str", "required": True,
             "description": "Who the pack is read as; the reader must read as the same identity."},
            {"name": "schemas", "type": "list[str]",
             "description": "Only these schemas (the rest are counted in the manifest, never dropped silently)."},
            {"name": "built_at", "type": "str", "description": "The pack's as-of; now when omitted."}],
    binding_note="Fixed to one database's schemas, tables and columns, and the facts the pack carries about them.",
    tile_safe={"safe": False, "reason": "reads every table and column of the database from Egeria, as the viewer; "
                                        "not measured for a tile's request path"},
)

CURATION_COVERAGE_TILE_ROUTINE = routine_declaration(
    CURATION_COVERAGE_TILE,
    inputs=["reader:ods", "reader:catalogue_scope", "subject"],
    params=[{"name": "slug", "type": "str", "required": True, "description": "The resource's slug in RE's registry."},
            {"name": "ods_url", "type": "str", "default": "", "category": "performance",
             "description": "RE's registry URL; REGISTRY_DATABASE_URL when empty."},
            {"name": "resource_type", "type": "str", "default": "database",
             "description": "The resource's type; curation coverage is measured for databases."}],
    binding_note="curation_coverage rendered in format KPI; computes nothing of its own.",
    tile_safe=_REGISTRY_ONLY,
)

#: Every routine this package ships, declared, by registered name.
ROUTINES = {r.name: r for r in (CURATION_COVERAGE_ROUTINE, CONTEXT_PACK_ROUTINE, CURATION_COVERAGE_TILE_ROUTINE)}
