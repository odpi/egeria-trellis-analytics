"""Host 3 of curation_coverage: the Portal tile (brief 2b, 2d).

The registered function `curation_coverage_tile` (`curation_coverage_kpi` since 0.4) is a thin adapter between the
routine and pyegeria's `exec_report_spec`, which can only hand an analytic function JSON parameters and only chart a
flat {category: number} dict. Since 0.4 it builds nothing by hand: it opens the two readers, runs the routine and renders
the result with the generic KPI renderer from the routine's declaration (`render.kpi_tile`). Every number, id, word,
version and time is read off the result. `report_specs()` is the FormatSet for the tile. Installing the package
registers it through the `pyegeria.report_specs` entry point (pyegeria ISSUE-173); no `PYEGERIA_REPORT_SPEC_MODULES`
setting is needed. The spec names the tile's function by its registered name, `curation_coverage_tile` (Q2(b)).

When the state is `not_established` or `not_applicable` the dict carries no number at the top level, so a BAR
request cannot draw a chart of zeros. Since pyegeria 6.2.17 (#518) the executor returns kind "absent" for those
states: a sentence in `content`, no `data`, and this dict under `detail`.
"""
from __future__ import annotations

import os
import warnings

from trellis_analytics.declaration import LegacyApiWarning
from trellis_analytics.readers import CATALOGUE_SCOPE, ODS, ReaderMissing, open_reader
from trellis_analytics.render import _kpis as _render_kpis
from trellis_analytics.render import kpi_tile
from trellis_analytics.routines import curation_coverage
from trellis_analytics.routines.curation_coverage import no_reader

TILE_LABEL = "Trellis - Curation Coverage"
#: The tile function's registered name (manifests.CURATION_COVERAGE_TILE, installed through the pyegeria.analytics entry
#: point). A report spec names it by this, never by its Python path (Q2(b), project owner 2026-10-31).
TILE_FUNCTION = "curation_coverage_tile"


def _kpis(result) -> list[dict]:
    """The tile's KPI rows for a CoverageResult (the KPI renderer's, `render._kpis`)."""
    return _render_kpis(result.groups)


def _coverage(slug: str, ods_url: str, resource_type: str):
    url = ods_url or os.environ.get("REGISTRY_DATABASE_URL", "")
    try:
        # RE's catalogue first: without RE neither reader is here, and the catalogue is the absence worth naming.
        catalogue = open_reader(CATALOGUE_SCOPE, url)
        ods = open_reader(ODS, url)
    except ReaderMissing as exc:            # a reader is not installed here: said, never a chart of zeros
        return no_reader(resource_type, slug, exc)
    return curation_coverage(ods, resource_type, slug, catalogue)


def curation_coverage_kpi(slug: str, ods_url: str = "", resource_type: str = "database") -> dict:
    """The tile for one resource, rendered from the routine's declaration (`render.kpi_tile`, format KPI): KPI rows, the
    two counts keyed by their declared labels when there are counts, the envelope's state as subtitle, provenance.
    The function the registered name `curation_coverage_tile` runs since 0.4."""
    from trellis_analytics.manifests import CURATION_COVERAGE_ROUTINE
    return kpi_tile(CURATION_COVERAGE_ROUTINE, _coverage(slug, ods_url, resource_type), function=TILE_FUNCTION)


def curation_coverage_tile(slug: str, ods_url: str = "", resource_type: str = "database") -> dict:
    """DEPRECATED (0.4): the hand-built tile's Python name, kept for one minor release. It returns exactly what it
    returned in 0.3 (proven against a frozen copy of the 0.3 builder, `tests/fixtures/legacy_tile.py`), now rendered from
    the declaration. Call `curation_coverage_kpi`, or name the registered function `curation_coverage_tile` in a spec."""
    warnings.warn("trellis_analytics.portal.curation_coverage_tile is deprecated since 0.4: call "
                  "curation_coverage_kpi (the tile rendered from curation_coverage's declaration)",
                  LegacyApiWarning, stacklevel=2)
    return curation_coverage_kpi(slug, ods_url, resource_type)


def report_specs():
    """The tile's FormatSet, keyed by its label: the loader the `pyegeria.report_specs` entry point names."""
    from pyegeria.view._output_format_models import ActionParameter, Format, FormatSet, FormatSetDict
    return FormatSetDict({TILE_LABEL: FormatSet(
        heading="Curation Coverage",
        description="Published against not yet published, from the curation record (trellis-analytics "
                    "curation_coverage). The subtitle is the result's state; counts carry the ids they count.",
        family="Curation",
        target_type=None,
        formats=[Format(types=["DICT", "JSON", "BAR"], attributes=[])],
        action=ActionParameter(analytic_function=TILE_FUNCTION,      # no action function (pyegeria 6.2.2, ISSUE-141)
                               analytic_spec_params={"resource_type": "database"}),
    )})
