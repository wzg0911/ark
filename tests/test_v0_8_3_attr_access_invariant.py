"""v0.8.3 — Attribute Access Invariant.

Prescription reflow from `langchain-exa#39167` (3rd time a diagnosis aimed at
an upstream project landed a hit on ARK's own code).

Upstream defect:  `getattr(result, "summary")` — two args, no default. Reads as
                  a guard, behaves as `result.summary`. Covers ABSENCE: no.
ARK's own defect: `getattr(response, "llm_output", {}).get(...)` — covers
                  ABSENCE but not NULLITY. `LLMResult.llm_output` is declared
                  `dict | None` with default None, so the guard never fires and
                  `.get()` raises one frame later.

Four arms:
  A  absence  — attribute missing entirely
  B  nullity  — attribute present, holds None   <- the half ARK missed
  C  falsy    — attribute present, holds [] / "" / 0.0 (must NOT be treated absent)
  D  control  — ordinary values pass through untouched
"""

import pytest

from ark.attrs import attr, attr_mapping, attr_text, is_present, prune_absent


class Absent:
    """No optional attributes at all."""


class Null:
    """Optional attributes present, all None."""
    summary = None
    llm_output = None
    description = None
    highlights = None


class Falsy:
    """Optional attributes present, all falsy-but-meaningful."""
    summary = ""
    llm_output = {}
    description = ""
    highlights = []
    score = 0.0


class Filled:
    summary = "a summary"
    llm_output = {"token_usage": {"total_tokens": 42}}
    description = "d" * 200
    highlights = ["h1", "h2"]
    score = 0.9


# ---------------------------------------------------------------------------
# The upstream idiom is not a guard (this is the whole bug in one assert)
# ---------------------------------------------------------------------------

def test_two_arg_getattr_is_not_a_guard():
    with pytest.raises(AttributeError):
        getattr(Absent(), "summary")
    assert getattr(Absent(), "summary", None) is None


def test_ark_original_idiom_was_broken_on_nullity():
    """Regression witness: the exact expression ARK used to ship."""
    with pytest.raises(AttributeError):
        getattr(Null(), "llm_output", {}).get("token_usage", {})
    with pytest.raises(TypeError):
        getattr(Null(), "description", "unknown")[:80]


# ---------------------------------------------------------------------------
# Arm A · absence
# ---------------------------------------------------------------------------

def test_attr_absence():
    assert attr(Absent(), "summary") is None
    assert attr(Absent(), "summary", "fallback") == "fallback"


def test_attr_mapping_absence():
    assert attr_mapping(Absent(), "llm_output") == {}
    assert attr_mapping(Absent(), "llm_output").get("token_usage", {}) == {}


def test_attr_text_absence():
    assert attr_text(Absent(), "description", "unknown") == "unknown"
    assert attr_text(Absent(), "description", "unknown", limit=3) == "unk"


# ---------------------------------------------------------------------------
# Arm B · nullity — the half the original guard missed
# ---------------------------------------------------------------------------

def test_attr_nullity():
    assert attr(Null(), "summary", "fallback") == "fallback"


def test_attr_mapping_nullity_is_safe_to_get():
    assert attr_mapping(Null(), "llm_output") == {}
    assert attr_mapping(Null(), "llm_output").get("token_usage", {}) == {}


def test_attr_text_nullity_is_safe_to_slice():
    assert attr_text(Null(), "description", "unknown", limit=80) == "unknown"


def test_attr_mapping_rejects_wrong_type():
    class Weird:
        llm_output = "not a mapping"

    assert attr_mapping(Weird(), "llm_output") == {}


# ---------------------------------------------------------------------------
# Arm C · falsy-but-present must survive (no truthiness-as-presence)
# ---------------------------------------------------------------------------

def test_is_present_does_not_collapse_falsy():
    f = Falsy()
    assert is_present(f, "highlights") is True
    assert is_present(f, "summary") is True
    assert is_present(f, "score") is True
    assert bool(f.highlights) is False  # what the buggy idiom would have asked


def test_is_present_false_for_absent_and_null():
    assert is_present(Absent(), "highlights") is False
    assert is_present(Null(), "highlights") is False


def test_prune_absent_keeps_empty_containers():
    out = prune_absent(Falsy(), ("highlights", "summary", "score"))
    assert out == {"highlights": [], "summary": "", "score": 0.0}
    assert "highlights" in out, "empty list must stay distinguishable from absent"


def test_prune_absent_omits_absent_and_null_only():
    assert prune_absent(Absent(), ("highlights", "summary")) == {}
    assert prune_absent(Null(), ("highlights", "summary")) == {}


def test_prune_absent_transform():
    out = prune_absent(Filled(), ("description",), transform=lambda k, v: v[:5])
    assert out == {"description": "ddddd"}


# ---------------------------------------------------------------------------
# Arm D · control — real values are untouched
# ---------------------------------------------------------------------------

def test_control_values_pass_through():
    f = Filled()
    assert attr(f, "summary") == "a summary"
    assert attr_mapping(f, "llm_output").get("token_usage") == {"total_tokens": 42}
    assert attr_text(f, "description", limit=80) == "d" * 80
    assert prune_absent(f, ("highlights",)) == {"highlights": ["h1", "h2"]}


def test_attr_text_coerces_non_string():
    class N:
        description = 12345

    assert attr_text(N(), "description") == "12345"
    assert attr_text(N(), "description", limit=3) == "123"


# ---------------------------------------------------------------------------
# Integration — the two real call sites that were crashing
# ---------------------------------------------------------------------------

def test_langchain_callback_survives_null_llm_output():
    from ark.langchain import ARKCallbackHandler

    class Resp:
        llm_output = None
        generations = [[]]

    h = ARKCallbackHandler()
    h.on_llm_start({}, ["p"])
    h.on_llm_end(Resp())  # used to raise AttributeError
    assert h._trace is not None


def test_langchain_callback_survives_missing_generations():
    from ark.langchain import ARKCallbackHandler

    class Resp:
        llm_output = {"token_usage": {"total_tokens": 7}}
        generations = None

    h = ARKCallbackHandler()
    h.on_llm_start({}, ["p"])
    h.on_llm_end(Resp())
    assert h._trace is not None


def test_crewai_callback_survives_null_description():
    from ark.crewai import ARKCrewCallback

    class Task:
        description = None

    class Agent:
        role = None

    cb = ARKCrewCallback()
    cb.on_task_start(Task(), Agent())  # used to raise TypeError
    assert cb._task_count == 1
