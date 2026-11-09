<p align="center">
  <img src="assets/banner.jpg" alt="ArenaAnything — measurable agent arena" width="100%">
</p>

# ArenaAnything

**一套极简的、可定量评估、可持续迭代、最终走向 RSI（Recursive Self-Improvement，递归自我改进）的智能体框架。**

把不同模型放进同一份考卷、同一个冻结 agent、同一套进程隔离里跑，结果可复现、可追溯、可横比。

> **项目状态：刚刚起步。**
> 第一个轻量级可对比 agent（`ssj @ 0.1.0`）已经跑通并在真实模型上完成验证，
> 首个 Case 见 [`case001-4llm-demo`](case/case001-4llm-demo/)。

## 命名

| 名称 | 指什么 |
|------|--------|
| **ArenaAnything** | **项目名**（唯一正式名称） |
| **`ssj`** | 智能体 CLI 入口（命令名） |
| **`arena`** | 对比 / 分析 CLI 入口（命令名） |
| **`arenaanything`** | Python 包名（`pip` 中显示的名字） |

本地克隆目录叫什么与应用无关 —— 下文示例统一用 `ArenaAnything`。

## 两个入口

框架提供两个 CLI 入口，职责单向分离：

| 入口 | 角色 | 管什么 |
|------|------|--------|
| **`ssj`** | **智能体入口** | 一个白板 agent 如何加载配置、发请求、解析回答、报告结果。管的是「**这一个个体怎么活**」。 |
| **`arena`** | **对比 / 分析入口** | 把 N 个 profile（不同模型）放到同一份考卷上跑，收集报告、生成横向对比。管的是「**谁更好，为什么**」。 |

```text
      ssj                        arena
  ┌────────────┐            ┌────────────────┐
  │ 单个体      │            │ 多 profile     │
  │ 单次调用    │  ←──────  │ 矩阵编排        │
  │ 答题解析    │            │ 汇总对比        │
  └────────────┘            └────────────────┘
       个体                         赛道
```

`arena` 调用 `ssj`（子进程 + 独立进程根），`ssj` 不知道 `arena` 的存在 —— **单向依赖**。

## 首个 Case 的实际结果

[`case001-4llm-demo`](case/case001-4llm-demo/) —— 4 个模型 × 30 题，agent 冻结在 `ssj @ 0.1.0`：

| Profile | 实际模型 | 准确率 | 耗时 |
|---------|----------|:------:|-----:|
| `jev` | `typesafe/jev-latest` | **93.3%** (28/30) | 12.4s |
| `ds` | `deepseek/deepseek-chat` | **86.7%** (26/30) | 26.4s |
| `mimo` | `openrouter/xiaomi/mimo-v2.6-flash` | **80.0%** (24/30) | 61.1s |
| `kimi` | `moonshot/kimi-k3` | **60.0%** (18/30) | 282.5s |

可读报告：[`export/index.html`](case/case001-4llm-demo/export/index.html) ·
机器可读：[`export/summary.json`](case/case001-4llm-demo/export/summary.json)

> 模型名以报告里的 `litellm_model` 为准 —— 那是实际发出去请求的名字。

## 为什么这样设计

| 原则 | 说明 |
|------|------|
| **可定量** | 同一份 jsonl 考卷、同一个 `parse` 规则、同一套判分，分母恒为题目总数 |
| **可复现** | agent 冻结成 `tar.gz`，`arena init` 解压即跑，不依赖 `pip install` |
| **可迭代** | 换 agent 版本只改 `agent.version`；加考卷只加一个 jsonl + manifest 条目 |
| **极简** | 单轮白板，无工具、无多步规划。先把「一次问答的准确性」量准，再谈复杂 |

三件事叠起来，才有资格谈 RSI：**先能测量，才能迭代；能迭代，才谈得上自我改进。**

## 怎么玩

### 玩法一：复制一个 `ssj`，就是一个智能体

一个 agent 的最小形态，**就是一个目录**。它自己的配置、密钥、会话、轨迹全在里面，和别的 agent 完全隔离。

```bash
mkdir my-agent && cd my-agent

ssj setup                  # 初始化 config.yaml / models.yaml
ssj model add mymodel      # 加一个模型代号（交互式填 litellm id）
ssj model set mymodel      # 配 API base 与密钥（只写本目录 .env）
ssj model ping -m mymodel  # 验证连通

ssj chat --text "用一句话解释什么是递归自我改进"
```

此刻 `my-agent/` 里已经有 `config.yaml`、`models.yaml`、`.env`、`session/`、`traces/`。
**把这个目录整个复制一份，就又多了一个独立智能体** —— 换模型、换 prompt、换参数，互不干扰。

`ssj chat` 可选参数：`--system-prompt`、`--with-context`、`--with-profile`、`--timeout`、`--max-tokens`。

### 玩法二：配自己的测试集，拉自己的模型进来比

**第一步，加考卷。** 往 `benchmark/` 放一个 jsonl，一行一题：

```jsonl
{"id": "my-001", "suite": "mytest", "prompt": "题干……\n\n选项：\nA. ……\nB. ……\n\n请只回答 A 或 B。", "choices": {"A": "……", "B": "……"}, "answer": "B", "parse": "letter"}
```

**第二步，注册到 `benchmark/manifest.yaml`：**

```yaml
suites:
  mytest:
    file: mytest.jsonl
    lang: zh
    parse: letter
    n_items: 1
    source: 自建
```

**第三步，把新模型加进 Case 矩阵。** 编辑 `templates/case/<id>.yaml` 的 `matrix.profiles`，然后：

```bash
arena init --case <id> --rebuild          # 生成新的 ssj-<profile>/ 进程根
cd case/<id>/ssj-mymodel && ssj model set mymodel   # 给新 profile 配密钥
```

**第四步，跑并对比：**

```bash
arena check --case <id>
arena run --case <id> all --suite mytest   # 只跑你的新卷，已有报告不受影响
arena summary --case <id>                  # → export/index.html
```

最后打开 `case/<id>/export/index.html`，就是一张「你的模型 × 你的题」的横向对比表。

## `ssj @ 0.1.0` 的能力边界

**这是一次刻意的最小化。** 0.1.0 只做一件事：把「一次问答准不准」量准。

### 有

| 能力 | 说明 |
|------|------|
| 单轮对话 | `ssj chat --text`，可选 system prompt |
| 会话历史 | 基于文件累积，按 1 MB 分段落盘（`session/`） |
| 静态选择题评测 | `ssj eval`，`parse` 支持 `letter` / `one_zero` / `yes_no` |
| 多 provider 路由 | OpenAI 兼容（chat）与 TypeSafe SystemOne（decisions）双协议 |
| 进程根隔离 | 每目录独立 `config.yaml` / `models.yaml` / `.env` / `session/` / `traces/` |
| 评测进度回传 | `SSJ_PROGRESS_FILE` 快照，供 `arena` 聚合进度条 |
| 失败可见 | 单题失败记 `error` 字段（但仍计为答错，保证分母干净） |

### 没有（有意为之）

| 缺失 | 原因 |
|------|------|
| **Function calling / tool use** | 先把「说对」量准，再谈「做对」 |
| **多步 agent loop** | `config.yaml` 里的 `max_steps` 是**预留字段，当前不生效** |
| 流式输出 | 评测场景不需要 |
| 自动重试 / 退避 | 失败即错，保证分数口径统一 |
| 沙箱 / 代码执行 | 0.1.0 不执行模型产出的任何代码 |
| MCP / 插件 | 单轮白板，无扩展点 |
| 多模态 | 纯文本 |
| 并发跑题 | 串行，便于观察单题行为与限速 |
| token / 费用统计 | 只有耗时与吞吐 |

> **下一步（0.2.0）**：引入 tool use 与多步循环，让「能力」本身也可被测量。

## 环境要求

**本地开发仅支持 Linux / WSL**（Python 3.12+）。不要在 Windows 原生 Python 下安装或运行 `ssj` / `arena` —— `arena run` 会用同一 venv 的 Python 子进程跑冻结 bundle，路径与 env 按 Unix 约定。

## 构建环境

```bash
git clone https://github.com/mc436572/ArenaAnything.git
cd ArenaAnything

python3.12 -m venv venv_wsl
source venv_wsl/bin/activate
pip install -U pip
pip install -r requirements.txt    # 1) 第三方依赖
pip install -e . --no-deps         # 2) 本仓 editable + ssj / arena 入口
```

- 依赖真源：**[`pyproject.toml`](pyproject.toml)**；[`requirements.txt`](requirements.txt) 与其同步（改依赖时两处一起改）。
- 第 2 步注册 **`ssj`**、**`arena`**（`[project.scripts]`）；本地会生成 `*.egg-info/`，勿提交。
- 若图省事可只跑 `pip install -e .`（一步装依赖+入口），与上面两步等价。

## 快速上手

```bash
cp .env.example .env    # 填 API key；勿提交 .env
arena list
arena init --case case001-4llm-demo
arena check --case case001-4llm-demo
arena run --case case001-4llm-demo all
arena summary --case case001-4llm-demo
```

跑分产物在 **`case/<id>/reports/<profile>/`**（不是仓库根 `reports/`）。
冻结包放在 `templates/ssj/<ver>/ssj-<ver>.tar.gz`，`arena init` 直接解压，本地无需重新构建。

## 结构

```
benchmark/          考卷（manifest + jsonl）
templates/ssj/      agent 本体（冻结 tar.gz，可复现）
templates/case/     实验配方模板
case/<id>/          一次实验：各 profile 进程根 + reports/ + export/
cli/ ssj/ shared/   源码（ssj 与 arena 两个入口）
```

**四层怎么串起来、为什么不合并**：见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 文档

- 架构总览：[ARCHITECTURE.md](ARCHITECTURE.md)
- 跑一场评测：[doc/case-workflow.md](doc/case-workflow.md)
- 冻结包机制：[doc/freeze.md](doc/freeze.md)
- 文档索引：[doc/README.md](doc/README.md)
- Cursor / WSL 约定：[.cursor/rules/python-wsl-venv.mdc](.cursor/rules/python-wsl-venv.mdc)

## 许可

- **代码**：Apache-2.0，见 [LICENSE](LICENSE)
- **`benchmark/` 数据**：沿用上游许可，**不受 Apache-2.0 覆盖**。`ceval.jsonl`、`cmmlu.jsonl`（及包含二者的 `demo.jsonl`）为 **CC BY-NC-SA 4.0，禁止商业使用**；`mmlu.jsonl` 为 MIT。详见 [NOTICE](NOTICE)。
- 在仓库仍包含上述数据文件时，**请勿将其用于商业再分发**。
