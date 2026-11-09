# 冻结包机制（agent freeze）

`ssj` 是一个**可冻结、可 pin 版本**的白板个体。每场 Case 绑定一个确切的 agent 版本，保证「当时跑的是什么」可以被复现。

## 两个版本概念

| 对象 | 位置 | 含义 |
|------|------|------|
| **agent 冻结版本** | `templates/ssj/<version>/` | 具体某一代 agent；Case 的 `case.yaml` 用 `agent.version` pin 住它 |
| **Python 包版本** | `pyproject.toml` 的 `version` | 整仓 CLI / `shared` 引擎，可与 agent 版本的 patch 号不同步 |

两者独立演进：引擎可以升级而不动已冻结的 agent，反之亦然。

## 冻结目录内容

```text
templates/ssj/0.1.0/
├── ssj-0.1.0.tar.gz      # 代码快照（ssj 包 + 子进程所需的 cli/shared 切片）
├── AGENT_VERSION.yaml    # line / version / mode
├── MANIFEST.yaml         # 模板文件清单
├── BUNDLE_MANIFEST.yaml  # tar 内每个文件的 SHA-256（校验用）
├── RELEASE.md            # 能力边界、known issues
├── README.md
├── models.yaml           # 代号 → LiteLLM id 的快照
├── config.yaml           # 运行时默认配置
├── .env.example          # 该 profile 所需密钥键名（值恒为空）
└── chat-profiles/        # 答题预设
```

**永远不进模板**：`.env`、`reports/`、`traces/`、`session/`。

`ssj-<version>.tar.gz` **不含** `__pycache__` / `*.pyc`；打包时会过滤，`BUNDLE_MANIFEST.yaml` 也不记录它们。

## `arena init` 做了什么

以 `arena init --case case001-4llm-demo` 为例：

1. 解压 `ssj-0.1.0.tar.gz` → `case/<id>/ssj/0.1.0/`
   （`arena run` 的 `PYTHONPATH` 指向这里，**不需要 `pip install`**）
2. 从 `templates/ssj/0.1.0/` 复制配置模板到每个 `ssj-<profile>/`，包含 `models.yaml`
3. 刷新 `config.yaml` 里的路径字段
4. 把 `models.yaml` 的 `default` 设为该 profile 名 —— **Case 矩阵的列名就是这里的 `default`**
5. 按 `default` 对应的 LiteLLM id 重写 `.env.example`，只列出实际需要的密钥键名

可选参数：

| 参数 | 作用 |
|------|------|
| `--no-key` | 不触碰 `.env`（只建骨架） |
| `--rebuild` | 删除整个 `case/<id>/` 后重建（会覆盖密钥） |
| `--no-ping` | 跳过初始化后的连通性验证 |

默认行为会从仓库根 `.env` 或环境变量 `ARENAANYTHING_SECRETS` 补齐各 profile 缺失的 key。
（旧名 `SSAIYAN_SECRETS` 仍兼容，用于已有本地配置。）

## 升级到新版本

```bash
cp -r templates/ssj/0.1.0 templates/ssj/0.1.1
# 编辑 AGENT_VERSION.yaml / MANIFEST.yaml / RELEASE.md 的版本号与变更说明
# 新 Case 写 agent.version: "0.1.1"
```

**已 pin `0.1.0` 的 Case 不会自动迁移**。要切版本就改 `case.yaml` 后重新 `arena init`（注意 `--rebuild` 会清掉密钥）。

## 校验完整性

```bash
# 1. 确认 tar 内无字节码
tar -tzf templates/ssj/0.1.0/ssj-0.1.0.tar.gz | grep -E '__pycache__|\.pyc' || echo "clean"

# 2. 用 BUNDLE_MANIFEST.yaml 逐个比对 SHA-256
```

## 密钥

每个 `ssj-<profile>/` 有**独立**的 `.env`，互不共享。批量分发用 `ssj model set`，或直接编辑该 profile 的 `.env`。

`.env` 永不入库；`.env.example` 只保留键名，值恒为空。

## 相关

- 四层结构：[ARCHITECTURE.md](../ARCHITECTURE.md)
- 许可边界：[LICENSE](../LICENSE) · [NOTICE](../NOTICE)
