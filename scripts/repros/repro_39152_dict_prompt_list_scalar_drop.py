# ARK repro: langchain-core#39152 — `DictPromptTemplate.format()` silently
# DELETES every list/tuple item that is not a `str` or a `dict`.
#
# F8 family (semantic inversion / contract drift), NEW sub-shape:
# not "wrong value returned", but "value silently removed from the payload".
# The template is documented as pass-through except for variable substitution;
# instead it is a lossy filter whose loss depends only on the *container* the
# value sits in.
#
# Root cause (offline-verifiable, no API key, no network):
# `langchain_core/prompts/dict.py::_insert_input_variables`, list/tuple branch:
#
#     elif isinstance(v, (list, tuple)):
#         formatted_v = []
#         for x in v:
#             if isinstance(x, str):   formatted_v.append(formatter(x, **inputs))
#             elif isinstance(x, dict): formatted_v.append(_insert_input_variables(x, ...))
#         formatted[k] = type(v)(formatted_v)      # <-- no else: item vanishes
#     else:
#         formatted[k] = v                          # <-- scalar OUTSIDE a list survives
#
# The same `1` is preserved at `{"scalar": 1}` and destroyed at `{"nums": [1]}`.
# The identical omission exists in `_get_input_variables`, so a `{var}` buried
# in a nested list is never even registered as an input variable — the missing
# -variable KeyError that normally protects the user cannot fire.
#
# Real-world trigger: multimodal / tool_use content blocks. Numeric fields
# (`dims`, `bbox`, `amount_cents`, `top_k_scores`, boolean flag arrays) are
# routine in provider content-block schemas and are exactly what disappears.
#
# Usage:
#   python -m venv venv && venv/bin/pip install langchain-core
#   venv/bin/python repro_39152_dict_prompt_list_scalar_drop.py
#
# Exit code 0 = defect reproduced as described. Non-zero = behaviour changed.
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.dict import DictPromptTemplate

SEP = "=" * 78


def _mk(template: dict[str, Any], fmt: str = "f-string") -> DictPromptTemplate:
    return DictPromptTemplate(template=template, template_format=fmt)


# --------------------------------------------------------------------------
# Case A (DEFECT) — scalars inside a list are destroyed
# --------------------------------------------------------------------------
def case_a_scalars_in_list() -> tuple[dict[str, Any], dict[str, Any]]:
    tpl = {
        "type": "tool_use",
        "id": "call_1",
        "name": "search",
        "input": {"query": "{q}", "top_k_scores": [1, 2, 3], "flags": [True, None]},
    }
    return tpl, _mk(tpl).format(q="cats")


# --------------------------------------------------------------------------
# Case B (CONTROL) — the SAME scalars one level up survive intact
# --------------------------------------------------------------------------
def case_b_scalars_outside_list() -> tuple[dict[str, Any], dict[str, Any]]:
    tpl = {"type": "x", "scalar": 1, "nested": {"scalar": 2}}
    return tpl, _mk(tpl).format()


# --------------------------------------------------------------------------
# Case C (DEFECT, escalation) — a template VARIABLE buried in a nested list
# is neither registered nor rendered, and no missing-variable error can fire
# --------------------------------------------------------------------------
def case_c_variable_swallowed() -> tuple[list[str], dict[str, Any], str]:
    p = _mk({"type": "text", "payload": [["prefix", "{q}"]]})
    rendered = p.format()  # deliberately WITHOUT q
    return p.input_variables, rendered, "no-KeyError"


# --------------------------------------------------------------------------
# Case D (CONTROL) — same variable one nesting level shallower behaves
# --------------------------------------------------------------------------
def case_d_variable_control() -> tuple[list[str], dict[str, Any], str]:
    p = _mk({"type": "text", "payload": ["{q}"]})
    try:
        p.format()
        raised = "no-KeyError"
    except KeyError:
        raised = "KeyError"
    return p.input_variables, p.format(q="SECRET"), raised


# --------------------------------------------------------------------------
# Case E — reachable through the fully public ChatPromptTemplate API
# --------------------------------------------------------------------------
def case_e_public_api() -> Any:
    chat = ChatPromptTemplate.from_messages(
        [("ai", [{"type": "text", "text": "{q}", "nums": [1, 2, 3]}])]
    )
    return chat.format_messages(q="hello")[0].content


# --------------------------------------------------------------------------
# Case F — no template variables at all: pure data destruction
# --------------------------------------------------------------------------
def case_f_no_variables() -> dict[str, Any]:
    return _mk({"nums": [1, 2]}, "mustache").format()


def main() -> int:
    failures: list[str] = []

    print(SEP)
    print("ARK repro · langchain-core#39152 · DictPromptTemplate list-item loss")
    print(SEP)

    a_in, a_out = case_a_scalars_in_list()
    print("\n[A · DEFECT] scalars nested inside a list")
    print(f"  template : {a_in}")
    print(f"  formatted: {a_out}")
    if a_out["input"]["top_k_scores"] != [] or a_out["input"]["flags"] != []:
        failures.append("A: expected numeric/bool lists to be emptied")
    else:
        print("  -> [1,2,3] and [True,None] were DELETED")

    b_in, b_out = case_b_scalars_outside_list()
    print("\n[B · CONTROL] the same scalars NOT inside a list")
    print(f"  template : {b_in}")
    print(f"  formatted: {b_out}")
    if b_out != b_in:
        failures.append("B: control arm should be pass-through")
    else:
        print("  -> preserved. The only difference is the container.")

    c_vars, c_out, c_raise = case_c_variable_swallowed()
    print("\n[C · DEFECT] template variable buried in a nested list")
    print(f"  input_variables: {c_vars}   (variable never registered)")
    print(f"  format() with NO inputs supplied: {c_out}   ({c_raise})")
    if c_vars != [] or c_out["payload"] != []:
        failures.append("C: expected variable to be invisible and payload emptied")
    else:
        print("  -> the missing-variable guard cannot fire. Silent by construction.")

    d_vars, d_out, d_raise = case_d_variable_control()
    print("\n[D · CONTROL] same variable one level shallower")
    print(f"  input_variables: {d_vars}")
    print(f"  format(q=...)  : {d_out}")
    print(f"  format() bare  : raises {d_raise}")
    if d_vars != ["q"] or d_raise != "KeyError":
        failures.append("D: control arm should register the var and raise KeyError")
    else:
        print("  -> guard works here. One nesting level decides safety.")

    e_out = case_e_public_api()
    print("\n[E] reached through the public ChatPromptTemplate API")
    print(f"  content: {e_out}")
    if e_out[0].get("nums") != []:
        failures.append("E: expected nums to be emptied through the public API")

    f_out = case_f_no_variables()
    print("\n[F] template with zero variables (mustache)")
    print(f"  formatted: {f_out}")
    if f_out["nums"] != []:
        failures.append("F: expected data loss even with no variables to substitute")
    else:
        print("  -> nothing to substitute, yet data is still destroyed.")

    print("\n" + SEP)
    if failures:
        print("BEHAVIOUR CHANGED — review needed:")
        for f in failures:
            print("  -", f)
        return 1
    print("DEFECT REPRODUCED: list/tuple items that are not str|dict are dropped.")
    print("Loss is decided by the CONTAINER, not the value. No error is raised.")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
