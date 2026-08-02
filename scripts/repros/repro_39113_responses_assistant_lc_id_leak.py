# ARK repro: langchain#39113 — ChatOpenAI (Responses API) forwards the
# `lc_` id minted by create_text_block() on a *synthetic* AIMessage into the
# Responses API `input[].id` field, triggering
#   400 "Invalid 'input[2].id': 'lc_...'. Expected an ID that begins with 'msg'."
#
# F9 family, 2nd occurrence (mirror of #39100):
#   #39100 — langchain-anthropic, SYSTEM branch leaked lc_ id  -> fixed (PR #39101)
#   #39113 — langchain-openai,   ASSISTANT branch leaks lc_ id -> this repro
#
# Root cause (offline-verifiable): in `_construct_responses_api_input()`
# (langchain_openai/chat_models/base.py), the assistant branch copies
# `block.get("id")` into the outgoing item id whenever `store is not False`,
# with no shape check. Server-issued ids are `msg_*`; framework-minted ids are
# `lc_*` — the latter must never reach the wire.
#
# Deterministic OFFLINE verification (no API key needed): we build the request
# payload via `ChatOpenAI._get_request_payload()` and inspect `input[].id`.
#
# Usage:
#   python -m venv venv && venv/bin/pip install langchain-openai
#   venv/bin/python repro_39113_responses_assistant_lc_id_leak.py
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.content import create_text_block
from langchain_openai import ChatOpenAI

SEP = "=" * 78


def assistant_item(payload):
    return next(i for i in payload["input"] if i.get("role") == "assistant")


def main():
    print(SEP)
    print("ARK repro #39113: synthetic AIMessage lc_ id leaks into Responses API input")
    print(SEP)

    messages = [
        SystemMessage(content_blocks=[create_text_block("You are a helpful assistant.")]),
        HumanMessage(content_blocks=[create_text_block("What is the capital of France?")]),
        AIMessage(content_blocks=[create_text_block("The capital of France is Paris.")]),
        HumanMessage(content_blocks=[create_text_block("And of Italy?")]),
    ]
    minted = messages[2].content_blocks[0].get("id")
    print(f"\ncreate_text_block() minted id on AIMessage: {minted!r}")

    llm = ChatOpenAI(
        model="gpt-5.5",
        output_version="v1",
        use_responses_api=True,
        api_key="sk-fake-offline",
    )

    # Case 1 — default (store=None): lc_ id is forwarded verbatim -> upstream 400
    p1 = assistant_item(llm._get_request_payload(messages))
    print("\n--- case 1: default (store=None) assistant input item ---")
    print(json.dumps(p1, indent=2, default=str))
    leaked = str(p1.get("id", "")).startswith("lc_")

    # Case 2 — store=False: id omitted entirely (per docstring), request valid
    llm_nostore = ChatOpenAI(
        model="gpt-5.5",
        output_version="v1",
        use_responses_api=True,
        api_key="sk-fake-offline",
        store=False,
    )
    p2 = assistant_item(llm_nostore._get_request_payload(messages))
    print("\n--- case 2: store=False assistant input item (id omitted) ---")
    print(f"id present: {'id' in p2}")

    # Case 3 — genuine server id (msg_*) passes through: the intended behavior
    messages_srv = list(messages)
    messages_srv[2] = AIMessage(
        content_blocks=[create_text_block("The capital of France is Paris.", id="msg_abc123")]
    )
    p3 = assistant_item(llm._get_request_payload(messages_srv))
    print("\n--- case 3: server-issued msg_ id (legitimate passthrough) ---")
    print(f"id: {p3.get('id')!r}")

    print()
    print(SEP)
    if leaked:
        print("BUG REPRODUCED ✅  framework-minted lc_ id reached input[].id")
        print("Upstream effect: OpenAI rejects with 400 invalid_value on input[].id")
        print("ARK prescription: OutputValidator wire-schema whitelist per provider +")
        print("InputGuard marks lc_-prefixed self-minted fields as internal;")
        print("any internal field in an outbound payload = contract violation.")
    else:
        print("NOT reproduced — adapter may already strip non msg_ ids (check version)")
    print(SEP)
    return 0 if leaked else 1


if __name__ == "__main__":
    raise SystemExit(main())
