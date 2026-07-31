# ARK repro: langchain-exa#39167 — `_get_metadata()` crashes on optional
# attributes, and silently deletes them when they are present-but-falsy.
#
# Two defects in ONE seven-line function, pointing in opposite directions.
#
# -------------------------------------------------------------------------
# The code (langchain_exa/retrievers.py::_get_metadata)
# -------------------------------------------------------------------------
#     metadata = {
#         "title": result.title, "url": result.url, "id": result.id,
#         "score": result.score, "published_date": result.published_date,
#         "author": result.author,
#     }
#     if getattr(result, "highlights"):        # <-- TWO-ARG getattr
#         metadata["highlights"] = result.highlights
#     if getattr(result, "highlight_scores"):
#         metadata["highlight_scores"] = result.highlight_scores
#     if getattr(result, "summary"):
#         metadata["summary"] = result.summary
#
# Defect 1 — THE GUARD THAT ISN'T.
#   `getattr(x, "y")` with no default is *exactly* `x.y`. It raises
#   AttributeError on a missing attribute. The author wrote `getattr(...)`
#   — the universal Python idiom for "tolerate absence" — but omitted the
#   third argument that provides the tolerance. The code READS as defensive
#   and BEHAVES as `result.summary`. The defense is decorative.
#   The correct guard is `getattr(result, "summary", None)`.
#
# Defect 2 — TRUTHINESS USED AS PRESENCE.
#   Even when the attribute exists, `if <value>:` drops `[]`, `""`, `0.0`.
#   So `highlights=[]` ("Exa searched and found no highlights") and
#   "highlights were never requested" collapse into the same output: the key
#   is simply absent. A downstream consumer cannot distinguish them.
#   Meanwhile the dict literal above unconditionally keeps `title=None`,
#   `score=0.0`, `author=None`. Two opposite null policies, six lines apart,
#   in one function.
#
# -------------------------------------------------------------------------
# Why this is NOT a mock-only artifact (the reporter used MagicMock(spec=...))
# -------------------------------------------------------------------------
#   langchain-exa 1.1.0 declares `exa-py>=1.0.8,<2.0.0`.
#   `Result` in exa_py 1.0.8 has text/highlights/highlight_scores — and NO
#   `summary` field (summary landed in a later exa_py).
#   So `pip install langchain-exa "exa-py==1.0.8"` — a resolution the package
#   itself authorises — makes `_get_metadata()` raise AttributeError on a
#   REAL, library-constructed `Result`. No mock required.
#
#   Additionally, within a single modern exa_py, `_get_metadata` is annotated
#   `result: Any` but is only safe for `Result`. The sibling classes that the
#   `search_and_contents()` overloads DECLARE as return types
#   (`ResultWithText`, `ResultWithTextAndHighlights`) lack those very fields,
#   and `_Result` — the element type of `Result.subpages` — lacks all four.
#
# Usage:
#   python -m venv venv
#   venv/bin/pip install langchain-exa
#   venv/bin/python repro_39167_exa_fake_getattr_guard.py
#
#   Optional arm H (real-object crash, no mock):
#   venv/bin/pip install "exa-py==1.0.8"
#
# Exit code 0 = defect reproduced as described. Non-zero = behaviour changed.
from __future__ import annotations

import dataclasses
from typing import Any

import importlib.metadata as M
from exa_py.api import Result, ResultWithText, ResultWithTextAndHighlights, _Result
from langchain_exa.retrievers import _get_metadata

SEP = "=" * 78

OPTIONALS = ("highlights", "highlight_scores", "summary")


def _declared(cls: Any) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


# True when the installed exa_py's `Result` carries all three optionals.
# False on older in-range pins (e.g. 1.0.8, which predates `summary`).
RESULT_IS_COMPLETE = all(k in _declared(Result) for k in OPTIONALS)


def _try(obj: Any) -> tuple[str, Any]:
    try:
        return "ok", _get_metadata(obj)
    except AttributeError as e:
        return "AttributeError", str(e)


# --------------------------------------------------------------------------
# Arm A — modern Result with optionals defaulting to None.
# CONTROL on a complete exa_py; DEFECT on an older in-range pin.
# --------------------------------------------------------------------------
def arm_a() -> tuple[str, Any]:
    return _try(Result(url="https://example.com", id="r1", title="T", score=0.9,
                       published_date="2024-01-01", author="A"))


# --------------------------------------------------------------------------
# Arm B (DEFECT) — ResultWithText: a DECLARED return type of the very call
#                  langchain-exa makes, `search_and_contents(text=...)`
# --------------------------------------------------------------------------
def arm_b() -> tuple[str, Any]:
    return _try(ResultWithText(url="https://example.com", id="r1", title="T",
                               score=0.9, published_date="2024-01-01",
                               author="A", text="body"))


# --------------------------------------------------------------------------
# Arm C (DEFECT) — _Result: the element type of `Result.subpages`
# --------------------------------------------------------------------------
def arm_c() -> tuple[str, Any]:
    return _try(_Result(url="https://example.com", id="sub1"))


# --------------------------------------------------------------------------
# Arm D (DEFECT) — partial surface: has `highlights`, lacks `summary`.
#                  Proves the crash is per-attribute, not per-class.
# --------------------------------------------------------------------------
def arm_d() -> tuple[str, Any]:
    return _try(ResultWithTextAndHighlights(url="https://example.com", id="r1",
                                            text="body", highlights=["h"]))


# --------------------------------------------------------------------------
# Arm E (SEMANTICS) — getattr/2 is not a guard; getattr/3 is
# --------------------------------------------------------------------------
def arm_e() -> tuple[bool, Any]:
    class Bare:
        pass

    bare = Bare()
    try:
        getattr(bare, "summary")
        raised = False
    except AttributeError:
        raised = True
    return raised, getattr(bare, "summary", None)


# --------------------------------------------------------------------------
# Arm F (DEFECT) — present-but-falsy optionals are silently deleted
# --------------------------------------------------------------------------
def arm_f() -> list[tuple[str, str, bool, bool]]:
    # Requires a `Result` that declares every optional, otherwise the *other*
    # defect (arm A/H) fires first and masks this one.
    if not RESULT_IS_COMPLETE:
        return []
    cases = [
        ("highlights", [], "no highlights found"),
        ("highlight_scores", [], "no scores found"),
        ("summary", "", "empty summary returned"),
        ("highlights", ["h"], "control: non-empty"),
        ("highlight_scores", [0.0], "control: non-empty list of 0.0"),
    ]
    out = []
    for field, value, note in cases:
        r = Result(url="https://example.com", id="r1", text="b", **{field: value})
        md = _get_metadata(r)
        out.append((f"{field}={value!r}", note, hasattr(r, field), field in md))
    return out


# --------------------------------------------------------------------------
# Arm G (ASYMMETRY) — required block keeps every falsy value unconditionally
# --------------------------------------------------------------------------
def arm_g() -> dict[str, Any] | None:
    if not RESULT_IS_COMPLETE:
        return None
    return _get_metadata(Result(url="https://example.com", id="r1", score=0.0,
                                title=None, author=None, published_date=None))


# --------------------------------------------------------------------------
# Arm H (DEFECT, no mock) — only fires on exa_py without `Result.summary`
# --------------------------------------------------------------------------
def arm_h() -> tuple[bool, str, Any]:
    if RESULT_IS_COMPLETE:
        return False, "skipped", "installed exa_py's Result declares all optionals"
    r = Result(url="https://example.com", id="r1", title="T", score=0.9,
               published_date="2024-01-01", author="A")
    kind, payload = _try(r)
    return True, kind, payload


def main() -> int:
    failures: list[str] = []

    lc_v = M.version("langchain-exa")
    exa_v = M.version("exa_py")
    print(SEP)
    print("ARK repro · langchain-exa#39167 · fake getattr guard + falsy deletion")
    print(f"langchain-exa {lc_v} | exa_py {exa_v}  (declared range: exa-py>=1.0.8,<2.0.0)")
    print(SEP)

    print("\n[surface] which optionals each exa_py class actually declares")
    for cls in (Result, ResultWithText, ResultWithTextAndHighlights, _Result):
        missing = [k for k in OPTIONALS if k not in _declared(cls)]
        print(f"  {cls.__name__:32} missing={missing}")
    print(f"  Result declares all optionals: {RESULT_IS_COMPLETE}")

    kind, payload = arm_a()
    label = "control" if RESULT_IS_COMPLETE else "DEFECT (older in-range exa_py)"
    print(f"\n[A] {label} · Result, optionals = None")
    print(f"  -> {kind}: {sorted(payload) if kind == 'ok' else payload}")
    if RESULT_IS_COMPLETE and kind != "ok":
        failures.append("A: complete Result should NOT raise")
    if not RESULT_IS_COMPLETE and kind != "AttributeError":
        failures.append("A: incomplete Result should raise AttributeError")

    kind, payload = arm_b()
    print(f"\n[B] ResultWithText — a DECLARED return type of search_and_contents(text=...)")
    print(f"  -> {kind}: {payload if kind != 'ok' else sorted(payload)}")
    if kind != "AttributeError":
        failures.append("B: expected AttributeError on ResultWithText")

    kind, payload = arm_c()
    print(f"\n[C] _Result — element type of Result.subpages")
    print(f"  -> {kind}: {payload if kind != 'ok' else sorted(payload)}")
    if kind != "AttributeError":
        failures.append("C: expected AttributeError on _Result")

    kind, payload = arm_d()
    print(f"\n[D] ResultWithTextAndHighlights — HAS highlights, LACKS summary")
    print(f"  -> {kind}: {payload if kind != 'ok' else sorted(payload)}")
    if kind != "AttributeError":
        failures.append("D: expected AttributeError on the missing `summary` only")
    else:
        print("  -> crash is per-ATTRIBUTE, not per-class: two guards passed, the third blew up.")

    raised, with_default = arm_e()
    print(f"\n[E] is `getattr(x, 'y')` a guard?")
    print(f"  getattr(x, 'summary')        -> raised AttributeError: {raised}")
    print(f"  getattr(x, 'summary', None)  -> {with_default!r}")
    if not raised or with_default is not None:
        failures.append("E: getattr/2 semantics changed")
    else:
        print("  -> getattr/2 is literally `x.summary`. The third argument IS the guard.")

    print(f"\n[F] present-but-falsy optionals (no missing attribute anywhere)")
    f_rows = arm_f()
    if not f_rows:
        print("  -> skipped: installed exa_py's Result lacks an optional; arm A fires first.")
        print("     reproduce with a modern exa_py: pip install -U exa-py")
    else:
        for label, note, on_obj, in_md in f_rows:
            verdict = "kept" if in_md else "DROPPED"
            print(f"  {label:26} on_object={str(on_obj):5} in_metadata={str(in_md):5} {verdict:8} ({note})")
        dropped = [r[0] for r in f_rows if not r[3]]
        if len(dropped) != 3:
            failures.append(f"F: expected exactly 3 falsy drops, got {dropped}")
        else:
            print("  -> `[]` (searched, found none) and 'never requested' are now indistinguishable.")

    g = arm_g()
    print(f"\n[G] required block, all falsy: score=0.0, title=None, author=None")
    if g is None:
        print("  -> skipped: needs a Result declaring all optionals.")
    else:
        print(f"  keys emitted: {sorted(g)}")
        if not {"title", "score", "author"} <= set(g):
            failures.append("G: required keys should survive unconditionally")
        else:
            print("  -> falsy REQUIRED values are kept; falsy OPTIONAL values are deleted.")
            print("     Two opposite null policies, six lines apart, in one function.")

    fired, kind, payload = arm_h()
    print(f"\n[H] real library object, no mock (exa_py without `Result.summary`)")
    if not fired:
        print(f"  -> skipped: {payload}")
        print("     reproduce with: pip install 'exa-py==1.0.8'  (inside the declared range)")
    else:
        print(f"  -> {kind}: {payload}")
        if kind != "AttributeError":
            failures.append("H: expected AttributeError on a real in-range Result")
        else:
            print("     REAL exa_py Result. No MagicMock. Authorised by the dependency pin.")

    print("\n" + SEP)
    if failures:
        print("BEHAVIOUR CHANGED — review needed:")
        for f in failures:
            print("  -", f)
        return 1
    print("DEFECT REPRODUCED:")
    print("  1. `getattr(x, 'y')` without a default is not a guard — it is `x.y`.")
    print("     Code that READS as defensive BEHAVES as unguarded. -> AttributeError.")
    print("  2. Truthiness is used as presence — `[]`/``/`0.0` are silently deleted,")
    print("     while the required block keeps every falsy value. Opposite policies.")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
