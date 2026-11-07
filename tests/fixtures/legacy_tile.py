"""The 0.3.1 hand-built tile, frozen (BRIEF RS-W2-1b §2.3): `curation_coverage_tile`'s reshape exactly as it was in
trellis_analytics/portal.py at v0.3.1 (only the reader opening is left out: it is handed the result). The 0.4 renderer
is proven byte-identical against this copy, which stays here after the library and RE delete the original."""
from __future__ import annotations

import re

_CHARTED = ("measured", "nothing_found")


def _family_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", family.lower()).strip("_") or "unnamed"


def _kpis(result) -> list[dict]:
    out, seen = [], set()
    for g in result.groups:
        for l in g.lines:
            key = f"{g.key}.{l.key}" + (f".{_family_slug(l.family)}" if l.family else "")
            base, n = key, 2
            while key in seen:
                key, n = f"{base}_{n}", n + 1
            seen.add(key)
            out.append({"key": key, "group": g.key, "label": l.label, "value": l.count, "rows": l.rows,
                        "names": l.names})
    return out


def legacy_tile(result, function: str = "curation_coverage_tile") -> dict:
    env = result.envelope
    state = env.result_state.value
    tile: dict = {
        "state": state,
        "state_reason": env.result_state_reason,
        "subtitle": env.result_state.words + (f" · {env.result_state_reason}" if env.result_state_reason else ""),
        "provenance": f"from trellis-analytics {env.producer_version} · curation coverage · as of {env.measured_at}",
        "manifest": {"function": function, "routine": "trellis_analytics.routines.curation_coverage",
                     "version": env.producer_version, "as_of": env.measured_at, "read_back_at": result.as_of,
                     "scope": env.scope},
        "summary": result.summary,
        "groups": [{"key": g.key, "words": g.words} for g in result.groups],
        "kpis": _kpis(result),
    }
    if state in _CHARTED:
        published = result.count("published", "schemas")
        tile["Published"] = published
        tile["Not yet published"] = result.known_schemas - published - result.count("blocked", "blocked")
    return tile
