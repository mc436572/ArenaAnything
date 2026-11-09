# 文档

本目录只放**可以公开**的技术文档。内部设计、商业计划与路线图在 `doc/internal/`（不入库）。

## 公开文档

| 文档 | 内容 |
|------|------|
| [case-workflow.md](case-workflow.md) | 怎么跑一场评测：`arena` 五步流程、参数、报告字段、常见问题 |
| [freeze.md](freeze.md) | 冻结包机制：目录内容、`arena init` 行为、版本升级、完整性校验 |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | 四层架构总览（benchmark / agent / case / arena）、设计取舍、扩展点 |
| [../benchmark/README.md](../benchmark/README.md) | 考卷格式与 manifest 约定 |
| [../README.md](../README.md) | 安装、快速上手、许可 |

## 阅读顺序建议

**想跑起来** → `../README.md` → `case-workflow.md`

**想理解设计** → `../ARCHITECTURE.md` → `freeze.md`

**想加内容** → `../ARCHITECTURE.md` §8 扩展点 → `../benchmark/README.md`

## 关于 `internal/`

`doc/internal/` 存放：

- 愿景与定位、数据飞轮、自进化方案
- 实施计划与路线图、双轨 Git 方案
- 商业演进与定价策略
- 场景设计稿（红蓝对抗、行为指纹等）
- 早期调研草案

该目录已被 `.gitignore` 排除，不会出现在公开仓库中。
