# ARK Roadmap

## v0.1.0 — MVP ✅ (2026-06-08)
- [x] IdempotencyGuard (幂等守护)
- [x] CircuitBreaker (熔断控制器)
- [x] OutputValidator (输出验证)
- [x] Trace (链路追踪)
- [x] LangChain `ARKCallbackHandler`

## v0.1.1 — CrewAI Integration ✅ (2026-06-08)
- [x] CrewAI `ARKCrewCallback`
- [x] GitHub Actions CI (Python 3.9-3.12)

## v0.2.0 — Indispensable Mode ✅ (2026-06-08)
- [x] `auto_init()` — 自动检测框架并初始化ARK
- [x] `detect_frameworks()` — 运行时框架检测
- [x] `ReliabilityScore` — 可靠性评分引擎
- [x] `SchemaRegistry` — 13个预置业务Schema
- [x] GitHub Pages landing page

## v0.3.0 — Dashboard & Gamification ✅ (2026-06-08, 🚀提前7天交付)

### Dashboard UI ✅
- [x] **Trust Monitor**: 实时显示幂等拦截、熔断状态、验证通过率
- [x] **Trace Explorer**: 可视化链路追踪（span tree → flame graph）
- [x] **Agent Scoreboard**: 多Agent可靠性排名

### Achievement System ✅
- [x] 🛡 **Guardian**: 累计拦截1000次重复调用
- [x] ⚡ **Survivor**: 熔断恢复10次
- [x] 🔧 **Inspector**: 验证通过率 > 99%
- [x] 👁 **Watcher**: 追踪 > 10000 spans
- [x] 🎖 **ARK Master**: 四项全满

### PyPI Automation ✅
- [x] GitHub Actions 自动发布到 PyPI
- [x] 版本号自动递增

## v0.5.0 — OpenTelemetry Bridge (生态接入点) ✅ 2026-06-12
- [x] **OTelExporter** — 可靠性事件→OTLP/JSON标准格式
- [x] **8种事件类型** — `ark.idempotency.hit/miss`、`ark.circuit.open/close/half_open`、`ark.validation.fail/pass`、`ark.guardian.intercept`
- [x] **零依赖可选** — 纯标准库实现，未配端点自动禁用
- [x] **批量缓冲** — 100条/批或5秒刷新，降低Collector压力
- [x] **Langfuse/Jaeger/Tempo兼容** — 标准OTLP协议，直接接入现有观测栈
- [x] **零侵入埋点** — Guard/Breaker/Validator 内部自动 emit，OTel关闭时 zero overhead（一次if判断），开启时一行环境变量激活
- [x] **运行时激活** — 函数内读取env，确保 `ARK_OTEL_ENDPOINT` 任何时候设置都生效
- [ ] Multi-language SDK (TypeScript/Go)
- [ ] Cloud Dashboard (hosted version)
- [ ] 原生 `opentelemetry-sdk` 集成（当前为零依赖OTLP/JSON）

## Long-term Vision
- **ARK Cloud**: 托管信任基础设施，Agent接入即获信任
- **Trust-as-a-Service**: 按Agent数量/API调用量定价
- **Open Standard**: 成为AI Agent可靠性的事实标准
