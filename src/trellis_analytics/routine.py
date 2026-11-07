"""The routine declaration (0.4; owner decision D2, BRIEF RS-W2-2 §2.1): what a routine, producer, processor or step
says about how it is called, beside what its results are (`Declaration`).

The library authors this schema first; pyegeria mirrors it (it may not import the library) and cross-validates by
loading its own declarations here. So the schema is kept small, and every field but `name` has a default:

    RoutineDeclaration
      name          identifier; the registered name a report spec uses
      kind          producer | processor | routine | step                       (STAGE_KINDS + "step")
      description, version, source, family, tags
      generic       is WHAT it counts a parameter (True) or fixed in its code (False, said in binding_note)
      binding_note
      inputs        role words: egeria_client:<Class>, reader:<name>, viewer, subject
      params        [ParamDeclaration(name, type, default | required, category, description)]
      constants     {name: value}: values fixed for every call, never a param's name
      in            the input shape a processor reads (Shape | [Field] | registered shape name)
      declaration   the results (`Declaration`: result_kind, measures, absence, out, ...)
      pushdown      words for what the routine asks its source to do (a count by the repository, a filter)
      tile_safe     TileSafety(safe, cap, reason): may it run on a tile's request path, and why
      admission     Admission(resource_types, test_only)
      bindings      [Binding(kind: python | egeria_query | sql | step, target)]; at most one python binding
      annotation_type   a step's Egeria annotation type; "" for a routine

`out` is not a routine field: it is `declaration.out`, so a result's fields are declared in one place (`out_fields()`).

`ReaderDeclaration` says what a reader of the seam (`trellis_analytics.readers`) yields, read by read: each a
registered shape. A reader is a producer whose implementation is installed, not called by path, so it has no binding.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field as _Default
from pydantic import model_validator

from trellis_analytics.declaration import (_TYPE_PATTERN, FIELD_NAME_PATTERN, SHAPES, STAGE_KINDS, Declaration, Field,
                                           Shape, _Strict, _words, resolve_fields)

#: What a declaration declares: a stage of a micro-flow, or a step (a routine deployed to an engine host).
ROUTINE_KINDS = STAGE_KINDS + ("step",)

#: How a routine is reached. `python`: an importable `module.attr` path; `egeria_query`: a saved Egeria query by name;
#: `sql`: a named query a reader owns; `step`: a step's registered name.
BINDING_KINDS = ("python", "egeria_query", "sql", "step")

#: What a parameter changes: what is counted (`content`), how the result is laid out (`shape`), or only how fast or how
#: much is read (`performance`, which never changes a value).
PARAM_CATEGORIES = ("content", "shape", "performance")

#: The role words a routine's `inputs` use. `egeria_client` and `reader` take a qualifier after a colon.
INPUT_ROLES = ("egeria_client", "reader", "viewer", "subject")

_INPUT = re.compile(r"^(?:egeria_client:[A-Za-z_][A-Za-z0-9_]*|reader:[a-z_][a-z0-9_]*|viewer|subject)$")
_PYTHON_TARGET = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


class Binding(_Strict):
    """How the routine is reached: one of `BINDING_KINDS` and its target."""
    kind: Literal["python", "egeria_query", "sql", "step"]
    target: str

    @model_validator(mode="after")
    def _target(self) -> "Binding":
        if not _words(self.target):
            raise ValueError(f"a {self.kind} binding names no target")
        if self.kind == "python" and not _PYTHON_TARGET.fullmatch(self.target):
            raise ValueError(f"python binding target '{self.target}' is not a dotted import path (module.attr)")
        return self


class ParamDeclaration(_Strict):
    """One parameter a caller may set. Either it has a default or it is required, never both."""
    name: str
    #: The parameter's type in Python words ("str", "int", "list[str]"), as pyegeria's `AnalyticParam.type`.
    type: str = "str"
    default: Any = None
    required: bool = False
    category: Literal["content", "shape", "performance"] = "content"
    description: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "ParamDeclaration":
        if not re.fullmatch(FIELD_NAME_PATTERN, self.name or ""):
            raise ValueError(f"parameter name '{self.name}' is not an identifier")
        if self.required and self.default is not None:
            raise ValueError(f"parameter '{self.name}' is required and has a default: a required parameter has none")
        return self


class TileSafety(_Strict):
    """May the routine run on a tile's request path? `safe` with no `cap` is a yes at any size; a `cap` (param -> value)
    is a yes only within it. The reason is the evidence (a timing, a cost class) and is always said."""
    safe: bool
    cap: dict[str, Any] = _Default(default_factory=dict)
    reason: str

    @model_validator(mode="after")
    def _reason(self) -> "TileSafety":
        if not _words(self.reason):
            raise ValueError("tile_safe declares no reason: say the evidence (a timing, a cost class)")
        if self.cap and not self.safe:
            raise ValueError("tile_safe declares a cap and safe false: a cap says within what it IS safe")
        return self


class Admission(_Strict):
    """Where the routine may be offered: the resource types it is about ([] = any), and whether only in tests."""
    resource_types: list[str] = _Default(default_factory=list)
    test_only: bool = False


class RoutineDeclaration(_Strict):
    """What a routine says about how it is called and what it returns (module docstring)."""
    name: str
    kind: Literal["producer", "processor", "routine", "step"] = "routine"
    description: str = ""
    version: str = ""
    source: str = ""
    family: str = ""
    tags: list[str] = _Default(default_factory=list)
    generic: bool = False
    binding_note: str = ""
    inputs: list[str] = _Default(default_factory=list)
    params: list[ParamDeclaration] = _Default(default_factory=list)
    constants: dict[str, Any] = _Default(default_factory=dict)
    #: The shape a processor reads (`in` in JSON: a Python keyword, so the attribute is `in_`).
    in_: Shape | list[Field] | str | None = _Default(default=None, alias="in")
    declaration: Declaration | None = None
    pushdown: list[str] = _Default(default_factory=list)
    tile_safe: TileSafety | None = None
    admission: Admission = _Default(default_factory=Admission)
    bindings: list[Binding] = _Default(default_factory=list)
    annotation_type: str = ""

    model_config = {**_Strict.model_config, "populate_by_name": True}

    @model_validator(mode="after")
    def _whole(self) -> "RoutineDeclaration":
        if not re.fullmatch(FIELD_NAME_PATTERN, self.name or ""):
            raise ValueError(f"routine name '{self.name}' is not an identifier")
        label = f"routine '{self.name}'"
        bad = [i for i in self.inputs if not _INPUT.fullmatch(i or "")]
        if bad:
            raise ValueError(f"{label} input {', '.join(repr(b) for b in bad)} is not a role word "
                             "(egeria_client:<Class>, reader:<name>, viewer, subject)")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError(f"{label} declares an input more than once")
        names = [p.name for p in self.params]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise ValueError(f"{label} declares parameter {', '.join(twice)} more than once")
        clash = sorted(set(names) & set(self.constants))
        if clash:
            raise ValueError(f"{label} declares {', '.join(clash)} as a parameter and a constant: a constant is fixed "
                             "for every call, so it is not a parameter")
        if sum(1 for b in self.bindings if b.kind == "python") > 1:
            raise ValueError(f"{label} declares more than one python binding: one routine, one function")
        if isinstance(self.in_, str) and self.in_ not in SHAPES:
            raise ValueError(f"{label} reads shape '{self.in_}' (in), which is not registered")
        if self.in_ is not None and self.kind != "processor":
            raise ValueError(f"{label} declares in and is a '{self.kind}': only a processor reads a previous stage's "
                             "shape; a routine or producer names its inputs")
        if self.generic and _words(self.binding_note):
            raise ValueError(f"{label} is generic and declares a binding_note: the note names what is fixed, and a "
                             "generic routine fixes nothing")
        return self

    def python_target(self) -> str:
        """The python binding's target, or "" when it has none."""
        return next((b.target for b in self.bindings if b.kind == "python"), "")

    def out_fields(self) -> list[Field]:
        """The result's fields (`declaration.out`), resolved; [] when not declared."""
        return self.declaration.out_fields() if self.declaration is not None else []

    def in_fields(self) -> list[Field]:
        if self.in_ is None:
            return []
        if isinstance(self.in_, list):
            return list(self.in_)
        return [f for _, f in resolve_fields(self.in_)]

    def words(self) -> str:
        """The routine's name in words: "curation_coverage" -> "curation coverage"."""
        return self.name.replace("_", " ")


class ReaderDeclaration(_Strict):
    """What a reader of the seam yields: its registered name, and per read (a method of its Protocol) the registered
    shape of what that read returns (one row of a list, or the one object). A read the reader has and this does not
    list is undeclared, and `undeclared` names it, so a partial declaration says it is partial."""
    name: str
    description: str = ""
    #: read (method name) -> the registered shape of what it returns, or a field type (`map<string,list<int>>`) for a
    #: read that returns a plain value rather than rows.
    reads: dict[str, str] = _Default(default_factory=dict)
    #: True where the read returns a list of rows of the shape; False where it returns one object of it.
    many: dict[str, bool] = _Default(default_factory=dict)

    @model_validator(mode="after")
    def _shapes(self) -> "ReaderDeclaration":
        unknown = {r: s for r, s in self.reads.items() if s not in SHAPES and not _TYPE_PATTERN.fullmatch(s or "")}
        if unknown:
            raise ValueError(f"reader '{self.name}' declares " + ", ".join(f"{r} -> '{s}'" for r, s in unknown.items())
                             + ": neither a registered shape nor a field type")
        stray = [r for r in self.many if r not in self.reads]
        if stray:
            raise ValueError(f"reader '{self.name}' says how many rows {', '.join(stray)} returns and declares no shape "
                             "for it")
        plain = [r for r, many in self.many.items() if many and self.reads.get(r) not in SHAPES]
        if plain:
            raise ValueError(f"reader '{self.name}' says {', '.join(plain)} returns rows of a field type: rows are of a "
                             "shape")
        return self

    def fields(self, read: str) -> list[Field]:
        """The fields of what `read` returns; [] for a read that returns a plain value (a field type)."""
        shape = self.reads[read]
        return [f for _, f in resolve_fields(shape)] if shape in SHAPES else []

    def undeclared(self, all_reads) -> list[str]:
        """The reads in `all_reads` (the Protocol's) this declaration gives no shape for."""
        return [r for r in all_reads if r not in self.reads]


def routine_declaration(manifest, **extra) -> RoutineDeclaration:
    """A manifest (`RoutineManifest` / `StepManifest`, or pyegeria's `AnalyticFunctionSpec`) read as a
    RoutineDeclaration: its `function` is the one python binding, its `params` become ParamDeclarations; `extra` adds
    what the manifest does not carry (inputs, tile_safe, ...). The compatibility view of BRIEF RS-W2-2 §2.1, run the
    other way."""
    m = manifest
    rt = list(getattr(m, "resource_types", []) or [])
    data: dict[str, Any] = {
        "name": m.name, "kind": getattr(m, "kind", "routine"), "description": getattr(m, "description", ""),
        "version": getattr(m, "version", ""), "source": getattr(m, "source", ""), "family": getattr(m, "family", ""),
        "tags": list(getattr(m, "tags", []) or []), "generic": bool(getattr(m, "generic", False)),
        "binding_note": getattr(m, "binding_note", ""),
        "params": [{"name": p.name, "type": p.type, "default": p.default, "required": p.required,
                    "description": p.description} for p in getattr(m, "params", []) or []],
        "declaration": getattr(m, "declaration", None),
        "admission": {"resource_types": rt},
        "bindings": [{"kind": "python", "target": m.function}] if getattr(m, "function", "") else [],
        "annotation_type": getattr(m, "annotation_type", "") if getattr(m, "kind", "") == "step" else "",
    }
    if data["declaration"] is not None and not isinstance(data["declaration"], Declaration):
        data["declaration"] = data["declaration"].model_dump()
    data.update(extra)
    return RoutineDeclaration.model_validate(data)
