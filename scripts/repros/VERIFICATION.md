# ARK Repro 验证记录 (Verification Log)

> 目的：消除历次巡航「repro 可运行性未验证」的诚实缺口。
> 本轮首次在隔离 venv 中**逐一实跑**全部 8 个离线复现脚本并记录结果。
> 全程零付费 API、零网络请求（脚本本身即离线确定性复现）。

## 验证环境

- 日期：2026-08-01（巡航 07:28 CST）
- venv：`/tmp/ark_repro_venv`（Python 3，独立于 ARK `.venv`）
- 关键依赖版本（`pip list` 实测）：

| 包 | 版本 |
|---|---|
| langchain-core | 1.5.3 |
| langchain-anthropic | 1.5.3 |
| langchain-openai | 1.4.1 |
| langchain-exa | 1.1.0 |
| langchain-qdrant | 1.1.0 |
| exa-py | 1.16.2 |
| qdrant-client | 1.18.0 |
| openai | 2.52.0 |
| anthropic | 0.120.2 |
| pydantic | 2.13.4 |

## 逐脚本结果

| # | 脚本 | 结果 | 说明 |
|---|------|------|------|
| 39152 | `repro_39152_dict_prompt_list_scalar_drop.py` | ✅ REPRODUCED | list 内非 str/dict 标量被静默删除；容器决定丢失，无报错 |
| 39163 | `repro_39163_cancelled_leaves_run_pending.py` | ✅ REPRODUCED | 4/4 如预测：BaseException(Cancelled/KeyboardInterrupt) 令 run 永久 pending；ValueError 控制臂正常 |
| 39106 | `repro_39106_list_keys_before_boundary.py` | ✅ REPRODUCED | `before=` 严格 `>=` 边界导致 num_deleted=0（应为 2），陈旧记录漏删 |
| 39113 | `repro_39113_responses_assistant_lc_id_leak.py` | ✅ REPRODUCED | 框架自造 `lc_` id 泄漏进 input[].id；上游 OpenAI 400 invalid_value |
| 39167 | `repro_39167_exa_fake_getattr_guard.py` | ✅ REPRODUCED | `getattr(x,'y')` 伪守护 + 真值当存在性；两个相反 null 策略同存一函数 |
| 39047 | `repro_39047_key_encoder_uuid_break.py` | ✅ REPRODUCED | sha256/sha512/blake2b 全部触发 "not a valid UUID"；库自身弃用建议引向硬崩溃 |
| 39052 | `repro_39052_mmr_lambda_inversion.py` | ✅ REPRODUCED | Qdrant MMR 路径 lambda_mult 语义反转，0.0↔1.0 行为互换 |
| 39100 | `repro_39100_system_block_id_leak.py` | ☑️ FIXED UPSTREAM | 当前版本不再复现——system/human/assistant text block 均已剥离 id，印证 PR #39101 修复已落地（「诊断→合并」闭环成立） |

**汇总：8/8 脚本可运行；7 例复现诊断缺陷，1 例（#39100）确认上游已修复。**

## 说明

- `#39100` 由 REPRODUCED 变为 NOT-reproduced 是**预期且正向**的信号：ARK 在 07-28 诊断
  当天，maintainer 即以 PR #39101 合并修复，方案与 ARK 处方一致。本轮实跑二次印证。
- 依赖为第三方库最新稳定版；各脚本头部标注的「独立 venv + 安装对应库」流程本轮已完整走通。
- 本记录仅追加验证事实，不修改任何脚本逻辑。
