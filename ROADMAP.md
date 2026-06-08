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

## v0.3.0 — Dashboard & Gamification 🎯 (target: 2026-06-15)

### Dashboard UI
- **Trust Monitor**: 实时显示幂等拦截、熔断状态、验证通过率
- **Trace Explorer**: 可视化链路追踪（span tree → flame graph）
- **Agent Scoreboard**: 多Agent可靠性排名

### Achievement System
- 🛡 **Guardian**: 累计拦截1000次重复调用
- ⚡ **Survivor**: 熔断恢复10次
- 🔧 **Inspector**: 验证通过率 > 99%
- 👁 **Watcher**: 追踪 > 10000 spans
- 🎖 **ARK Master**: 四项全满

### PyPI Automation
- GitHub Actions 自动发布到 PyPI
- 版本号自动递增

## v0.4.0 — Community & Ecosystem (target: 2026-06-30)
- [ ] Community Schema Hub (用户贡献Schema)
- [ ] ARK Benchmarks (性能基准测试)
- [ ] Multi-language SDK (TypeScript/Go)
- [ ] Cloud Dashboard (hosted version)

## Long-term Vision
- **ARK Cloud**: 托管信任基础设施，Agent接入即获信任
- **Trust-as-a-Service**: 按Agent数量/API调用量定价
- **Open Standard**: 成为AI Agent可靠性的事实标准
