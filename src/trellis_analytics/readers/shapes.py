"""What the seam's readers yield, declared (0.4, BRIEF RS-W2-1b §2.1): a registered shape per read.

The library owns the seam (`OdsRead`, `CatalogueScopeRead`), so it declares the shapes; Resource Explorer's
implementations (`trellis_analytics_re.ods.OdsReader`, `registry_view.CatalogueScopeReader`) yield them and do not
move. A shape lists the fields a routine may rely on: an implementation may return more, never fewer.

Declared so far: the four reads `curation_coverage` makes. `READERS["ods"].undeclared(ODS_READS)` names the rest, so
the declaration says it is partial rather than looking whole.
"""
from __future__ import annotations

from trellis_analytics.declaration import register_shape
from trellis_analytics.readers import CATALOGUE_SCOPE, ODS
from trellis_analytics.routine import ReaderDeclaration


def _f(name, label, type_="string", **kw) -> dict:
    return {"name": name, "label": label, "type": type_, **kw}


#: `OdsRead.commit_proofs`: one row per `catalogue_commit_proofs` row of the database, oldest first.
COMMIT_PROOF = register_shape("CommitProof", {"fields": [
    _f("id", "Proof id", "int"),
    _f("node_kind", "Node kind"),                     # database | schema | table | column
    _f("schema_name", "Schema"),
    _f("table_name", "Table"),
    _f("proof", "Proof"),                             # elements_read_back, restored, leave_out_blocked, egeria_reset, ...
    _f("element_guid", "Element GUID"),               # empty where the proof names no element
    _f("read_at", "Read at"),                         # more than one time form is stored; read as text
    _f("detail", "Detail", "object"),                 # the stored detail_json, parsed ({} when unreadable)
]})

#: `OdsRead.catalogue_scope_events`: one row per scope choice made in Curate, oldest first.
CATALOGUE_SCOPE_EVENT = register_shape("CatalogueScopeEvent", {"fields": [
    _f("id", "Event id", "int"),
    _f("node_kind", "Node kind"),
    _f("schema_name", "Schema"),
    _f("table_name", "Table"),
    _f("choice", "Choice"),                           # catalogue | leave_out | "" (cleared)
    _f("action", "Action"),
    _f("source", "Source"),                           # person | a confirmed proposal's rule
    _f("proposal_rule", "Proposal rule"),
    _f("changed_at", "Changed at"),
]})

#: One schema of Curate's node set (`CatalogueScopeRead.node_set(...)["schemas"]`).
NODE_SET_SCHEMA = register_shape("NodeSetSchema", {"fields": [
    _f("schema", "Schema"),
    _f("classification", "Classification"),           # "system" for a system schema, which is not counted
    _f("tables", "Tables", "list<object>"),
]})

#: `CatalogueScopeRead.node_set`: Curate's node set for one database, and which source it chose.
NODE_SET = register_shape("NodeSet", {"fields": [
    {"name": "schemas", "label": "Schemas", "kind": "dataset", "shape": "NodeSetSchema"},
    _f("chosen", "Chosen source", "object"),          # kind, as_of, schemas, tables, merged
    _f("egeria", "Egeria's survey", "object"),
    _f("local", "RE's own survey", "object"),
    _f("disagree", "Sources disagree", "bool"),
    _f("unreadable", "Unreadable nodes", "int"),
    _f("stats_reset", "Statistics reset at"),
]})

READERS: dict[str, ReaderDeclaration] = {
    ODS: ReaderDeclaration(
        name=ODS,
        description="RE's registry, read only: fixed, parameterised SELECTs (OdsRead).",
        reads={"commit_proofs": "CommitProof", "catalogue_scope_events": "CatalogueScopeEvent",
               "outbox_status_counts": "map<string,list<int>>"},       # outbox status -> outbox row ids
        many={"commit_proofs": True, "catalogue_scope_events": True},
    ),
    CATALOGUE_SCOPE: ReaderDeclaration(
        name=CATALOGUE_SCOPE,
        description="Curate's node set for one database: RE's resolve_node_set over a read-only registry view.",
        reads={"node_set": "NodeSet"},
        many={"node_set": False},
    ),
}
