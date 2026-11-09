# SSaiyan

Agent 对标（Arena Case、`ssj` 白板、`benchmark` 静态套件）。**本地开发仅支持 Linux / WSL**（Python 3.12+），不要在 Windows 原生 Python 下安装或运行 `ssj` / `arena`（`arena run` 会用同一 venv 的 Python 子进程跑冻结 bundle，路径与 env 按 Unix 约定）。

## Clone 后构建环境

```bash
git clone <repo-url> SSaiyan
cd SSaiyan

python3.12 -m venv venv_wsl
source venv_wsl/bin/activate
pip install -U pip
pip install -r requirements.txt    # 1) 第三方依赖
pip install -e . --no-deps         # 2) 本仓 editable + ssj / arena 入口
```

- 依赖真源：**[`pyproject.toml`](pyproject.toml)**；[`requirements.txt`](requirements.txt) 与其同步（改依赖时两处一起改）。
- 第 2 步注册 **`ssj`**、**`arena`**（`[project.scripts]`）；本地会生成 `ssaiyan.egg-info/`，勿提交。
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

Arena 跑分产物在 **`case/<id>/reports/<profile>/`**（不是仓库根 `reports/`）。  
发布 agent 代际：冻结包由维护者构建并放在 `templates/ssj/<ver>/ssj-<ver>.tar.gz`；`arena init` 直接解压该包，本地无需重新构建。

## 结构

```
benchmark/          考卷（manifest + jsonl，git 发布）
templates/ssj/      agent 本体（冻结 tar.gz，可复现）
templates/case/     实验配方模板
case/<id>/          一次实验：各 profile 进程根 + reports/ + export/
cli/ ssj/ shared/   源码（ssj 与 arena 两个入口）
```

**四层怎么串起来、为什么不合并**：见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 示例 Case

[`case001-4llm-demo`](case/case001-4llm-demo/) — 4 个模型（ds / kimi / jev / mimo）× 30 题 demo，含跑分结果与可读报告。

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
