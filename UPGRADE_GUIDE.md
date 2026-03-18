# ESI-Lite 升级指南

本文件只讨论在现有 Lite 项目基础上的务实升级路径。

## 优先级 1：补齐资金市场压力指标

这些指标最直接增强离岸美元压力刻画：

- FRA-OIS
- CP-OIS
- EUR/USD basis
- USD/JPY basis

建议做法：

1. 在 `config.yaml` 的 `premium_indicators.definitions` 中启用目标指标
2. 在 `data_sources/premium_adapter.py` 对应 provider 中实现 `fetch_series`
3. 保持 unavailable 可降级，不要让主流程因单指标失败退出

## 优先级 2：增强公开数据覆盖

目前免费版本已经使用：

- FRED
- New York Fed
- BIS

可继续增强：

- NY Fed 增加 ON RRP / SRF 公开接口
- BIS 增加更多美元信用维度
- FRED 增加备用利差或资金量代理变量

## 优先级 3：提升报告质量

建议优先做：

- HTML 邮件模板分层：摘要 / 明细 / 风险提示
- PDF 页面增加事件窗口解读
- 增加异常说明，例如“Lite 因子对 2020-03 刻画偏弱”

## 优先级 4：提升部署体验

### 可选方向

- Docker 化
- 在线托管 dashboard
- 对接对象存储保存历史报告

### 不建议过早做的事

- 实时 websocket
- 复杂数据库
- 机器学习预测层

这些会明显增加维护成本，但对当前 Lite 版本价值有限。

## 付费数据接口建议

`premium_adapter.py` 目前已经为以下来源预留统一接口：

- CSV
- Bloomberg
- Refinitiv
- Wind / iFinD

建议实现顺序：

1. CSV 手工导入
2. Bloomberg
3. Refinitiv
4. Wind / iFinD

原因：

- CSV 最快验证指标逻辑
- Bloomberg / Refinitiv 更适合生产环境
- Wind / iFinD 更适合本地中国用户场景

## 指数方法升级建议

如果未来允许偏离 Lite 版的固定配方，可以考虑：

- 对 SOFRVOL 使用更稳定的 volume stress proxy
- 对低频 BIS 指标加入发布滞后控制
- 将事件验证从“regime 命中”升级为“相对基线抬升”

但当前 Lite 版本建议保持方法透明和可解释，不要过早增加模型复杂度。
