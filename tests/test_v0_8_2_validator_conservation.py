"""
ARK v0.8.2 — OutputValidator 结构守恒不变式

来源：langchain-core#39152 诊断处方自我落地。

#39152 的教训不是「不该过滤」，而是「过滤不能无声」。
ARK 自身 OutputValidator 犯了同型错误：把 Schema 未声明的字段直接丢弃，
返回 valid=True / errors=[]，调用方拿不到任何信号 —— 与 DictPromptTemplate
删除列表标量后返回合法空数组，是同一个缺陷形状。

不变式：**任何被丢弃的字段都必须可见。**
  1. 记入 ValidationResult.dropped_fields
  2. lossless 属性如实反映
  3. strict_extra=True 时升级为契约违规
  4. 无丢弃时行为与修复前完全一致（向后兼容）

采用 A/B/C/D 四臂对照，与 repro 脚本同款结构：
  A/C = 存在未声明字段（缺陷臂）
  B/D = 字段完全匹配（控制臂）
"""

import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ark import OutputValidator  # noqa: E402
from ark.validator import ValidationResult  # noqa: E402


class Order(BaseModel):
    order_id: str
    amount: float


EXTRA_PAYLOAD = {
    "order_id": "A1",
    "amount": 99.5,
    "currency": "USD",
    "idempotency_key": "k-77",
    "line_items": [1, 2, 3],
}

EXACT_PAYLOAD = {"order_id": "A1", "amount": 99.5}


# ---------------------------------------------------------------- A 臂（缺陷臂）
def test_arm_a_dropped_fields_are_recorded():
    """A：存在未声明字段 → 必须留痕，不能静默。"""
    v = OutputValidator()
    r = v.validate(Order, dict(EXTRA_PAYLOAD))

    assert r.valid is True, "宽松模式下仍应通过"
    assert r.dropped_fields == ["currency", "idempotency_key", "line_items"]
    assert r.lossless is False, "有字段被丢弃，不可自称无损"


def test_arm_a_dropped_appears_in_to_dict():
    """A：留痕必须出现在序列化结果里，否则跨进程边界即丢失。"""
    v = OutputValidator()
    d = v.validate(Order, dict(EXTRA_PAYLOAD)).to_dict()

    assert "dropped_fields" in d
    assert len(d["dropped_fields"]) == 3


def test_arm_a_stats_count_drops():
    """A：丢弃是可度量事件，必须进统计。"""
    v = OutputValidator()
    v.validate(Order, dict(EXTRA_PAYLOAD))
    v.validate(Order, dict(EXTRA_PAYLOAD))

    assert v.stats["dropped"] == 2
    assert v.stats["drop_rate"] == "100.0%"


# ---------------------------------------------------------------- B 臂（控制臂）
def test_arm_b_exact_payload_is_lossless():
    """B：字段完全匹配 → 无丢弃，lossless 为真。"""
    v = OutputValidator()
    r = v.validate(Order, dict(EXACT_PAYLOAD))

    assert r.valid is True
    assert r.dropped_fields == []
    assert r.lossless is True
    assert v.stats["dropped"] == 0


def test_arm_b_backward_compatible_shape():
    """B：无丢弃时，原有字段语义一字不变（向后兼容）。"""
    v = OutputValidator()
    r = v.validate(Order, dict(EXACT_PAYLOAD))

    assert r.data == {"order_id": "A1", "amount": 99.5}
    assert r.errors == []
    assert bool(r) is True


# ---------------------------------------------------------------- C 臂（严格模式）
def test_arm_c_strict_extra_blocks():
    """C：strict_extra=True → 丢弃升级为契约违规。"""
    v = OutputValidator(strict_extra=True)
    r = v.validate(Order, dict(EXTRA_PAYLOAD))

    assert r.valid is False
    assert r.dropped_fields == ["currency", "idempotency_key", "line_items"]
    assert any("undeclared field dropped" in e for e in r.errors)
    assert v.stats["blocked"] == 1


def test_arm_c_strict_error_names_the_fields():
    """C：报错必须点名具体字段，否则排障仍然要靠猜。"""
    v = OutputValidator(strict_extra=True)
    r = v.validate(Order, dict(EXTRA_PAYLOAD))

    msg = " ".join(r.errors)
    for f in ("currency", "idempotency_key", "line_items"):
        assert f in msg


# ---------------------------------------------------------------- D 臂（严格+精确）
def test_arm_d_strict_passes_exact_payload():
    """D：严格模式下精确 payload 仍应通过 —— 严格不等于误伤。"""
    v = OutputValidator(strict_extra=True)
    r = v.validate(Order, dict(EXACT_PAYLOAD))

    assert r.valid is True
    assert r.lossless is True
    assert v.stats["blocked"] == 0


# ---------------------------------------------------------------- 边界与兼容
def test_default_is_permissive():
    """默认必须保持宽松，避免升级即破坏既有集成。"""
    assert OutputValidator().strict_extra is False


def test_validation_failure_still_reports_errors():
    """类型错误路径不受影响，且 dropped_fields 有默认值。"""
    v = OutputValidator()
    r = v.validate(Order, {"order_id": "A1", "amount": "not-a-number"})

    assert r.valid is False
    assert r.errors
    assert r.dropped_fields == []


def test_none_output_still_blocked():
    """None 输出仍按原逻辑拦截。"""
    v = OutputValidator()
    r = v.validate(Order, None)

    assert r.valid is False
    assert r.dropped_fields == []


def test_result_dataclass_defaults():
    """ValidationResult 直接构造时 dropped_fields 默认空且 lossless 为真。"""
    r = ValidationResult(valid=True, data={"a": 1})

    assert r.dropped_fields == []
    assert r.lossless is True


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"order_id": "x", "amount": 1.0}, []),
        ({"order_id": "x", "amount": 1.0, "z": 1}, ["z"]),
        ({"order_id": "x", "amount": 1.0, "b": 1, "a": 2}, ["a", "b"]),
    ],
)
def test_dropped_fields_sorted_and_exact(payload, expected):
    """丢弃清单必须确定性排序，便于断言与告警去重。"""
    v = OutputValidator()
    assert v.validate(Order, payload).dropped_fields == expected


def test_otel_event_type_registered():
    """新增事件类型必须在 OTel 枚举中登记，否则 emit 会被静默吞掉。"""
    from ark.otel_exporter import EventType

    assert EventType("ark.validation.dropped") is EventType.VALIDATION_DROPPED
