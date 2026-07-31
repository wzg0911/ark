"""ARK · Attribute Access Invariant (v0.8.3)

Prescription reflow from `langchain-exa#39167`.

------------------------------------------------------------------------------
The defect family
------------------------------------------------------------------------------
Reading an optional attribute off a foreign object has TWO independent failure
modes, and almost every hand-rolled guard covers exactly one of them:

    ABSENCE   the attribute does not exist          -> AttributeError
    NULLITY   the attribute exists and holds None   -> downstream TypeError

`langchain-exa` wrote `getattr(result, "summary")` — two arguments, no default.
That is *literally* `result.summary`. It reads as defensive and is not; it
covers neither mode.

ARK wrote `getattr(response, "llm_output", {}).get(...)`. That covers ABSENCE
but NOT NULLITY: when the attribute is present and `None` — which is the
declared default of `LLMResult.llm_output` — the default never fires and the
`.get()` explodes one frame later, far from the real cause.

Same shape, opposite halves. Both look guarded at a glance.

A third trap sits next to them: using truthiness as a presence test.
`if result.highlights:` deletes `[]`, `""` and `0.0`, collapsing
"searched, found nothing" into "never asked" — an unrecoverable distinction
loss. Presence is `is not None`, not `bool(...)`.

------------------------------------------------------------------------------
The invariant
------------------------------------------------------------------------------
An optional attribute read must be total: for ANY object, it returns a usable
value of the expected shape, or an explicitly-requested sentinel. It must never
raise, and must never hand a `None` to a caller that is about to subscript it.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, TypeVar

__all__ = [
    "attr",
    "attr_mapping",
    "attr_text",
    "is_present",
    "prune_absent",
]

T = TypeVar("T")

_MISSING = object()


def attr(obj: Any, name: str, default: T = None) -> T:
    """Total optional-attribute read. Absent **or** None both yield `default`.

    This is the fix for both halves of the family:

    >>> class R: summary = None
    >>> attr(R(), "summary", "")        # NULLITY covered
    ''
    >>> attr(object(), "summary", "")   # ABSENCE covered
    ''

    Contrast with the two idioms this replaces:

    >>> getattr(R(), "summary")         # doctest: +SKIP
    None                                 # ... then blows up downstream
    >>> getattr(object(), "summary")    # doctest: +SKIP
    AttributeError

    Note the deliberate asymmetry with `getattr`: a stored `None` is treated as
    "not provided". Callers that must distinguish "explicitly None" from
    "absent" should use :func:`is_present`.
    """
    value = getattr(obj, name, _MISSING)
    if value is _MISSING or value is None:
        return default
    return value


def attr_mapping(obj: Any, name: str) -> Mapping[str, Any]:
    """Read an optional mapping attribute; always safe to `.get()` on.

    Guards the exact ARK self-hit at `ark/langchain.py`:
    `LLMResult.llm_output` is declared `dict | None` and defaults to `None`.

    A present-but-wrong-type value also yields `{}` rather than propagating a
    type error into the caller's `.get()` chain.
    """
    value = attr(obj, name, None)
    if isinstance(value, Mapping):
        return value
    return {}


def attr_text(obj: Any, name: str, default: str = "", limit: Optional[int] = None) -> str:
    """Read an optional attribute as text; always safe to slice.

    Guards the ARK self-hit at `ark/crewai.py`, where
    `getattr(task, "description", "unknown")[:80]` raised `TypeError` on a task
    whose `description` was present and `None`.

    Non-string values are coerced with `str()` so the return type is total.
    """
    value = attr(obj, name, _MISSING)
    if value is _MISSING:
        text = default
    else:
        text = value if isinstance(value, str) else str(value)
    if limit is not None:
        return text[:limit]
    return text


def is_present(obj: Any, name: str) -> bool:
    """Presence test that does NOT collapse falsy values.

    `[]`, `""` and `0.0` are *present*. This is the distinction that
    `if result.highlights:` destroys.

    >>> class R: highlights = []
    >>> is_present(R(), "highlights")
    True
    >>> bool(R().highlights)          # what the buggy idiom actually asks
    False
    """
    return getattr(obj, name, None) is not None


def prune_absent(
    obj: Any,
    names: tuple[str, ...],
    *,
    transform: Optional[Callable[[str, Any], Any]] = None,
) -> dict[str, Any]:
    """Collect optional attributes, keeping every value that is *present*.

    Emits a key when the attribute exists and is not None — so an empty list
    survives and stays distinguishable from an attribute that was never set.
    This is the structural counterpart to the v0.8.2 conservation invariant:
    a value may be omitted for being absent, never for being falsy.
    """
    out: dict[str, Any] = {}
    for name in names:
        value = getattr(obj, name, _MISSING)
        if value is _MISSING or value is None:
            continue
        out[name] = transform(name, value) if transform else value
    return out
