# ARK repro: langchain#39100 — ChatAnthropic forwards SystemMessage v1 content
# blocks verbatim, so create_text_block()'s minted `id` reaches the Anthropic API
# and triggers 400 "system.0.id: Extra inputs are not permitted".
#
# Deterministic OFFLINE verification (no API key needed):
# inspect the payload produced by langchain_anthropic's message formatting and
# show the asymmetry: human/assistant text blocks are narrowed to supported
# fields, while system text blocks pass the `lc_` id through verbatim.
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.content import create_text_block

from langchain_anthropic.chat_models import _format_messages

SEP = "=" * 78


def block_dump(label, payload):
    print(f"\n--- {label} ---")
    print(json.dumps(payload, indent=2, default=str))


def main():
    print(SEP)
    print("ARK repro #39100: system v1 text block id forwarded verbatim")
    print(SEP)

    sys_block = create_text_block("You are a helpful assistant.")
    print(f"\ncreate_text_block() minted id: {sys_block.get('id')!r}")
    assert str(sys_block.get("id", "")).startswith("lc_"), "expected lc_ id"

    system = SystemMessage(content_blocks=[sys_block])
    human_block = create_text_block("Say hi.")
    human = HumanMessage(content_blocks=[human_block])
    ai_block = create_text_block("hi")
    ai = AIMessage(content_blocks=[ai_block])

    formatted_system, formatted_messages = _format_messages([system, human, ai])

    block_dump("formatted SYSTEM payload (goes to Anthropic verbatim)", formatted_system)
    block_dump("formatted human/assistant messages", formatted_messages)

    # --- Assertions ---------------------------------------------------------
    sys_blocks = formatted_system if isinstance(formatted_system, list) else []
    sys_has_id = any("id" in b for b in sys_blocks if isinstance(b, dict))

    role_has_id = False
    for m in formatted_messages:
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text" and "id" in b:
                    role_has_id = True

    print("\n" + SEP)
    print(f"system text block still carries `id`      : {sys_has_id}")
    print(f"human/assistant text block carries `id`   : {role_has_id}")
    print(SEP)

    if sys_has_id and not role_has_id:
        print(
            "REPRODUCED: system blocks are forwarded verbatim (id kept) while\n"
            "human/assistant text blocks are narrowed (id stripped).\n"
            "Anthropic API rejects unknown keys on system blocks ->\n"
            '400 "system.0.id: Extra inputs are not permitted".'
        )
    elif not sys_has_id:
        print("NOT reproduced on this version: system block id was stripped (fixed?).")
    else:
        print("Unexpected: role text blocks also carry id — inspect payloads above.")


if __name__ == "__main__":
    main()
