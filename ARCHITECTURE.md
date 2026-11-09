# 架构说明

SSaiyan 是一套**用固定考卷把不同模型放在同一条起跑线上对比**的工具链。它由四层组成，各层职责单一、单向依赖：

```
benchmark/          考卷（静态题库，git 发布）
     │
     ▼
templates/ssj/      agent 本体（冻结成 tar.gz，可复现）
     │
     ▼
case/<id>/          一次实验（考卷 × agent × 模型矩阵 → 报告）
     │
     ▼
arena              调度器（materialize / run / summary）
```

一句话概括：**arena 把某个冻结的 agent 复制成多个进程根，每个进程根配一个模型，跑同一份考卷，最后汇总成一张对比表。**

---

## 1. benchmark —— 考卷

`benchmark/` 是**唯一的题库目录**，由 `manifest.yaml` 索引。

```yaml
suites:
  ceval:  { file: ceval.jsonl, parse: letter, n_items: 12342 }
  cmmlu:  { file: cmmlu.jsonl, parse: letter, n_items: 11582 }
  mmlu:   { file: mmlu.jsonl,  parse: letter, n_items: 14042 }
  demo:   { file: demo.jsonl,  parse: letter, n_items: 30 }
```

**条目格式**（一行一条，jsonl）：

| 字段 | 说明 |
|------|------|
| `id` | 全库唯一 |
| `prompt` | 完整题干，含选项文本与作答指令 |
| `choices` | 选项映射（`letter` 套件为 `A`–`D`） |
| `answer` | 金标，与 `choices` 的键同型 |
| `parse` | 解析器类型：`letter`（默认）/ `one_zero` / `yes_no` |
| `metadata` | 人读备注，不参与判分 |

**约定**：题库只进不改。新增套件要同步 `manifest.yaml` 的 `n_items`，并在 `NOTICE` 里写明上游许可。

当前 `ceval` / `cmmlu` 为 **CC BY-NC-SA 4.0（禁止商业使用）**，`mmlu` 为 MIT —— 详见 [NOTICE](NOTICE)。

---

## 2. templates/ssj —— agent 本体

`ssj` 是一个**单轮白板个体**：能在进程根里读配置、发一次模型请求、按 `parse` 规则解析回复。`templates/ssj/<version>/` 是它的冻结发布物：

| 文件 | 作用 |
|------|------|
| `ssj-<ver>.tar.gz` | 源码快照（`ssj/` + `cli/` + 必要的 `shared/`），**不含 `__pycache__`** |
| `MANIFEST.yaml` | 模板文件清单 |
| `AGENT_VERSION.yaml` | `line` / `version` / `mode` |
| `models.yaml` | 模型代号 → LiteLLM id |
| `.env.example` | 该 profile 需要的密钥键名（值恒为空） |
| `chat-profiles/` | 答题预设（`system_prompt`、`max_tokens`、`timeout`） |

**为什么冻结成 tar.gz**：`arena init` 解压后即可运行，不需要 `pip install`，也不需要联网拉代码。同一份 tar 在任何机器上行为一致，这是「可复现」的前提。

`BUNDLE_MANIFEST.yaml` 里记录了每个文件的 SHA-256，可校验解压完整性。

---

## 3. case/<id> —— 一次实验

`case/case001-4llm-demo/` 是一次具体实验的工作区：

```
case/case001-4llm-demo/
├── case.yaml              # 实验配方：考卷、agent 版本、模型矩阵、运行参数
├── MODELS.md              # 人读说明：每个 profile 用哪个模型、要哪些密钥
├── ssj/0.1.0/             # 从 tar.gz 解压出的 agent（gitignore，可随时重建）
├── ssj-ds/                # profile「ds」的独立进程根
├── ssj-kimi/
├── ssj-jev/
├── ssj-mimo/
├── reports/<profile>/     # 汇总层：arena run 从各进程根拷贝而来
└── export/                # arena summary 生成的可读报告（index.html + summary.json）
```

### 进程根隔离

每个 `ssj-<profile>/` 是一个**独立的 ssj 进程根**（`SSJ_ROOT == cwd`）：

| 文件 | 说明 |
|------|------|
| `config.yaml` | `profile` / `max_steps` / `sandbox` 等运行时配置 |
| `models.yaml` | `default` 指向本 profile 的模型代号 |
| `.env` | **本 profile 专属密钥**，不与其他 profile 共享，**永不入库** |
| `traces/` `inbox/` `session/` | 运行时产物，不入库 |
| `reports/` | 单次 eval 的原始 JSON 暂存 |

密钥不共享是有意设计：某个 profile 的 key 泄漏不会波及其他 profile，也不会影响仓库根。

### 报告的两层路径

| 位置 | 谁写 | 用途 |
|------|------|------|
| `ssj-<profile>/reports/` | `ssj eval`（子进程 cwd） | 单次 eval 暂存，**不入库** |
| `reports/<profile>/` | `arena run` 拷贝 | 实验汇总层，**可入库** |

---

## 4. arena —— 调度器

`arena` 是 CLI（`cli/arena.py`），把上面三层串起来：

| 命令 | 做什么 |
|------|--------|
| `arena list` | 列出所有 case 及其状态 |
| `arena init --case <id>` | 解压 bundle → 生成各 profile 进程根 → 写入 `models.yaml` → 可选 ping 验证 |
| `arena check --case <id>` | 校验配方与进程根是否完整、密钥是否齐备 |
| `arena run --case <id> all` | 对每个 profile 逐个跑 `ssj eval`，收集报告 |
| `arena summary --case <id>` | 聚合 `reports/` → `export/index.html` + `summary.json` |
| `arena del <id>` | 删除工作区（可先确认） |

内部实现要点：

- **子进程隔离**（`shared/ssj_subprocess.py`）：每个 profile 独立启动 Python 子进程，`cwd` 设为其进程根，环境变量只注入本 profile 的密钥。
- **进度追踪**（`shared/arena_progress.py`）：通过 `SSJ_PROGRESS_FILE` 回传，`arena run` 汇总成一条进度条。
- **输出生成**（`shared/arena_output.py`）：把多份报告拼成横向对比表。

---

## 5. ssj 的请求路径

跑一道题时，`ssj` 会：

```
item['prompt']
    │
    ├─ chat_probe_reply()            # 组装 messages
    │      │
    │      ├─ resolve_transport()    # 决定走 chat 还是 decisions 协议
    │      │      ├─ chat_openai → LiteLLM /chat/completions
    │      │      └─ decisions   → SystemOne 协议（如 JEV）
    │      │
    │      └─ 返回纯文本
    │
    └─ parse_probe_reply(item, model, reply)   # 按 item['parse'] 分派
           ├─ letter    → parse_choice_letter / parse_mcq_choice
           ├─ one_zero  → parse_one_zero
           └─ yes_no    → parse_yes_no_zh
                  │
                  └─ 得到规范化答案 → 与 item['answer'] 比对 → correct: bool
```

**关键设计**：解析器按 `parse` 字段分派，而不是按模型名硬编码。加一个新题型只需要在数据里写 `parse: xxx` 并在 `model_reply.py` 注册一个解析函数，不动调度逻辑。

调用失败（超时、网络错误）**计为答错**，但会记录 `error` 字段，便于事后区分「模型不会」和「接口挂了」。

---

## 6. 模型路由

`models.yaml` 里的代号映射到 LiteLLM 的 provider 前缀，由 `ssj/model_transport.py` 决定走哪条协议：

| 前缀 | 协议 | 需要的密钥 |
|------|------|-----------|
| `deepseek/` `moonshot/` `openrouter/` `openai/` `zai/` `xai/` 等 | `chat_openai` | 对应 `*_API_KEY` |
| `typesafe/` | `decisions`（SystemOne，`/alpha/decisions`） | `TYPESAFE_API_KEY` |

`openrouter/typesafe/...` 这种写法也走 `decisions`，但根地址换成 OpenRouter 网关（wire model 保留 `typesafe/` 前缀）。

每个 provider 支持可选的 `*_API_BASE` 覆盖默认地址，便于走代理或自建网关。

---

## 7. 设计取舍

| 决定 | 理由 |
|------|------|
| **考卷与代码分离** | 题库可以独立更新、独立授权；agent 版本迭代不影响历史实验的复现 |
| **agent 冻结成 tar.gz** | 消除「环境不一致」这一类问题；`arena init` 一条命令即可复现 |
| **每 profile 独立进程根** | 密钥隔离 + 单点故障不影响其他 profile |
| **失败计为答错但保留 error** | 保证分数口径统一（分母恒为题目总数），同时保留诊断信息 |
| **`parse` 字段驱动解析** | 题型扩展不改调度代码 |
| **仅支持 Linux / WSL** | 进程根与环境变量按 Unix 约定设计，避免 Windows 路径与 CRLF 的隐性差异 |

---

## 8. 扩展点

| 想做的事 | 改哪里 |
|---------|--------|
| **加一份新考卷** | 放 `benchmark/<name>.jsonl` → 在 `manifest.yaml` 注册（含 `parse`、`n_items`）→ 更新 `NOTICE` 许可 |
| **加一种新题型** | `ssj/model_reply.py` 加解析函数 → `parse_probe_reply` 加分支 → 数据里写 `parse: <新值>` |
| **加一个新模型** | `models.yaml` 加代号 → `.env.example` 加密钥键名 → 在 case 的 `matrix.profiles` 里启用 |
| **发布新 agent 版本** | 冻结到 `templates/ssj/<new-ver>/` → case 的 `agent.version` 指向新版本 |
| **新增实验** | 复制 `templates/case/<id>.yaml` 改配方 → `arena init --case <new-id>` |

---

## 9. 目录速查

| 路径 | 入库 | 说明 |
|------|:----:|------|
| `benchmark/` | ✅ | 考卷 + manifest |
| `templates/ssj/<ver>/` | ✅ | 冻结 agent（含 tar.gz） |
| `templates/case/` | ✅ | 实验配方模板 |
| `case/<id>/case.yaml` `MODELS.md` | ✅ | 实验定义 |
| `case/<id>/reports/` `export/` | ✅ | 实验结果 |
| `case/<id>/ssj/<ver>/` | ❌ | 解压产物，`arena init` 重建 |
| `case/<id>/ssj-<profile>/` | ❌ | 进程根，含密钥与运行时产物 |
| `case/<id>/ssj-<profile>/reports/` | ❌ | 单次 eval 暂存 |
| `cli/` `ssj/` `shared/` `web/` | ✅ | 源码 |
| `tests/` | ✅ | `pytest` 用例 |

---

## 参考

- 安装与环境：[README.md](README.md)
- 许可边界：[LICENSE](LICENSE) · [NOTICE](NOTICE)
