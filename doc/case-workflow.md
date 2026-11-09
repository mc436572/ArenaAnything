# 跑一场评测（Case workflow）

一场 **Case** = 一份考卷 × 一个冻结 agent × 一组模型 profile。`arena` 负责把这件事编排起来。

## 前置条件

- Linux / WSL（`arena` 用 Unix 路径与 env 约定）
- Python 3.12+，仓库已 `pip install -e .`（注册 `ssj` / `arena` 两个入口）
- 有模型 API key

## 五步流程

```bash
# 0. 密钥：复制模板后填入真实 key（.env 不入库）
cp .env.example .env

# 1. 看有哪些 Case
arena list

# 2. 构建工作区：解压 agent、建各 profile 进程根、写入 models.yaml
arena init --case case001-4llm-demo

# 3. 体检：矩阵、进程根、密钥是否齐备
arena check --case case001-4llm-demo

# 4. 跑：逐 profile 执行 ssj eval，成功后自动汇总
arena run --case case001-4llm-demo all

# 5. 需要时单独重跑汇总
arena summary --case case001-4llm-demo
```

产物：

| 路径 | 内容 |
|------|------|
| `case/<id>/reports/<profile>/*.json` | 每 profile 的原始报告 |
| `case/<id>/export/summary.json` | 机器可读汇总 |
| `case/<id>/export/index.html` | 可读对比表（模型 × 准确率 × 耗时） |

## 关键参数

### `arena init`

| 参数 | 作用 |
|------|------|
| `--no-key` | 不写 `.env`，只建骨架 |
| `--rebuild` | 删除整个 `case/<id>/` 后重建（**会覆盖密钥**） |
| `--no-ping` | 跳过初始化后的连通性验证 |

### `arena check`

`--strict` 让校验错误返回非零退出码（默认只打印警告/错误，仍返回 0），适合接 CI。

### `arena run`

- 位置参数 `scope` 目前只接受 `all`（profile 列表来自 `case.yaml` 的 `matrix.profiles`）
- `--suite <name>` 可多次传入，只跑指定考卷

## 一次 Case 的目录

```
case/case001-4llm-demo/
├── case.yaml              # 配方：考卷、agent 版本、模型矩阵、运行参数
├── MODELS.md              # 人读：每个 profile 用哪个模型、要哪些密钥
├── ssj/0.1.0/             # 解压出的 agent（arena init 生成，不入库）
├── ssj-ds/                # profile「ds」的进程根（含独立 .env）
├── ssj-kimi/
├── reports/<profile>/     # 汇总层（arena run 拷贝而来，可入库）
└── export/                # summary.json + index.html（可入库）
```

## 新增一场 Case

1. 复制 `templates/case/<existing>.yaml` → `templates/case/<new-id>.yaml`
2. 改 `case_id`、`benchmark.suites`、`matrix.profiles`、`eval.profile`
3. `arena init --case <new-id>`
4. 填各 `ssj-<profile>/.env`

配方字段含义：

| 字段 | 说明 |
|------|------|
| `agent.line` / `agent.version` | 用哪一代冻结 agent |
| `benchmark.suites` | 跑哪些考卷（对应 `benchmark/manifest.yaml`） |
| `matrix.profiles` | 模型矩阵，每项对应一个 `ssj-<profile>/` |
| `eval.profile` | 答题预设（`chat-profiles/*.yaml`，含 system prompt、max_tokens） |
| `run.temperature` / `run.timeout_sec` | 采样参数与单题超时 |
| `output.reports_dir` | 汇总报告子目录名 |

## 报告字段

`reports/<profile>/*.json` 里有：

| 字段 | 说明 |
|------|------|
| `n` / `correct` / `accuracy` | 题数 / 答对数 / 准确率 |
| `litellm_model` | **实际调用的模型名**（见下方约定） |
| `temperature` | 采样温度 |
| `duration_sec` / `throughput` | 总耗时 / 题每秒 |
| `items[]` | 每题 `id` / `answer` / `parsed` / `correct` / `reply` / `latency_ms`，失败时含 `error` |

> **模型名的权威来源是报告里的 `litellm_model`。**
> 仓库根 `models.yaml` 是开发默认清单，`case/<id>/ssj-<profile>/models.yaml` 是运行时副本 —— 两者都可能与历史报告不一致。三者冲突时，一律以报告为准。

## 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `arena init` 报找不到 bundle | 缺 `templates/ssj/<ver>/ssj-<ver>.tar.gz` | 见 [freeze.md](freeze.md) |
| 某 profile 全部答错 | 密钥缺失或无效，`error` 字段会有提示 | `arena check` 后补 `.env` |
| `arena run` 中途卡住 | 单题超时（`run.timeout_sec`） | 调大超时或换模型 |
| 报告数与题数不符 | 有 profile 跑失败，只看成功的 | 检查 `reports/.progress/` |

## 相关

- 四层架构：[ARCHITECTURE.md](../ARCHITECTURE.md)
- 冻结 agent：[freeze.md](freeze.md)
- 考卷格式：[benchmark/README.md](../benchmark/README.md)
