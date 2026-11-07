"""Renderers: (shape x renderer) pairs that turn a declared result into an output format, with no code per routine
(report-spec-pipeline-model §6; BRIEF RS-W2-1b §2.2). The first is `KPI`: the Portal's text tile.

`kpi_tile(routine, result, function=...)` reads everything off the routine's declaration and the result:

    state, state_reason, subtitle   the result's envelope (`envelope`): its state, the reason, both in words
    provenance                      "from <producer> <version> · <routine in words> · as of <measured_at>"
    manifest                        function (the registered tile name), routine (the python binding's module),
                                    version, as_of (the envelope's), read_back_at (the first measure's as-of field),
                                    scope
    summary                         the result's `summary` field
    groups, kpis                    from a `groups` dataset of shape CountGroup (lines of shape CountLine): each group's
                                    key and words, and one KPI per line keyed "<group>.<line>[.<family slug>]"
    <label>: <value>                one per measure whose value_field is a field of `out`, keyed by that field's label,
                                    ONLY when the state is one that has counts (measured, nothing_found)

When the state has no counts, the tile carries no number at the top level, so a BAR request cannot draw zeros (the
executor then shows the declared absence sentence). No Vega-Lite here: the tile is text (owner).
"""
from __future__ import annotations

import re
from typing import Any

from trellis_analytics.routine import RoutineDeclaration

#: The output format `kpi_tile` renders.
KPI = "KPI"

#: The states whose results have counts to show.
COUNTED_STATES = ("measured", "nothing_found")

#: The shapes the KPI renderer reads `groups` as.
KPI_GROUP_SHAPE, KPI_LINE_SHAPE = "CountGroup", "CountLine"


def _get(obj: Any, name: str) -> Any:
    """A field of a result: a pydantic model's attribute (computed fields included) or a dict's key."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _path(obj: Any, path: str) -> Any:
    for part in path.split("."):
        if obj is None:
            return None
        obj = _get(obj, part)
    return obj


def _state_value(state: Any) -> str:
    return getattr(state, "value", state) or ""


def _family_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", family.lower()).strip("_") or "unnamed"


def _kpis(groups) -> list[dict]:
    """One KPI per line, keyed `<group>.<line>`. A line naming a family is keyed `<group>.<line>.<family slug>`, the
    same key whether one family or several hold schemas, so no two KPIs share a key."""
    out, seen = [], set()
    for g in groups or []:
        for line in _get(g, "lines") or []:
            family = _get(line, "family") or ""
            key = f"{_get(g, 'key')}.{_get(line, 'key')}" + (f".{_family_slug(family)}" if family else "")
            base, n = key, 2
            while key in seen:              # two family names that slug alike stay apart
                key, n = f"{base}_{n}", n + 1
            seen.add(key)
            out.append({"key": key, "group": _get(g, "key"), "label": _get(line, "label"), "value": _get(line, "count"),
                        "rows": _get(line, "rows"), "names": _get(line, "names")})
    return out


def kpi_tile(routine: RoutineDeclaration, result: Any, *, function: str, producer: str = "trellis-analytics") -> dict:
    """The KPI tile for `result`, a result of `routine` (module docstring). `function` is the registered name the tile
    is served under. Refuses a routine whose declaration has no `out`, or whose `out` has no `groups` of CountGroup."""
    d = routine.declaration
    if d is None or d.out is None:
        raise ValueError(f"routine '{routine.name}' declares no out: the KPI tile is rendered from the declared result")
    groups_field = d.out_field("groups")
    if groups_field is None or groups_field.shape != KPI_GROUP_SHAPE:
        raise ValueError(f"routine '{routine.name}' out has no 'groups' dataset of shape {KPI_GROUP_SHAPE}: the KPI "
                         "tile renders that shape")
    env = _get(result, "envelope")
    state = _state_value(_get(env, "result_state"))
    reason = _get(env, "result_state_reason") or ""
    words = state.replace("_", " ")
    version, measured_at = _get(env, "producer_version"), _get(env, "measured_at")
    target = routine.python_target()
    first = d.measures[0] if d.measures else None
    groups = _get(result, "groups") or []
    tile: dict = {
        "state": state,
        "state_reason": reason,
        "subtitle": words + (f" · {reason}" if reason else ""),
        "provenance": f"from {producer} {version} · {routine.words()} · as of {measured_at}",
        "manifest": {"function": function, "routine": target.rpartition(".")[0] if target else "",
                     "version": version, "as_of": measured_at,
                     "read_back_at": _path(result, first.as_of) if first else "",
                     "scope": _get(env, "scope")},
        "summary": _get(result, "summary"),
        "groups": [{"key": _get(g, "key"), "words": _get(g, "words")} for g in groups],
        "kpis": _kpis(groups),
    }
    if state in COUNTED_STATES:
        for m in d.measures:
            f = d.out_field(m.value_field)
            if f is not None:
                tile[f.label] = _path(result, m.value_field)
    return tile
