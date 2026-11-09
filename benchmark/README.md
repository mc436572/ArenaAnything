# Benchmark（LLM 评测题库）

**唯一 canonical 目录**：`ssj eval --suite <name>` 与 `arena run` 均从本目录的 `manifest.yaml` 加载题面。内容随 **git 发布**；Case 工作区 (`case/<id>/`) **不**复制 jsonl。

```text
benchmark/
├── manifest.yaml    # suite 名 → 文件、由来、许可、题数
├── ceval.jsonl      # 官方 ceval/ceval-exam，全 subject test
├── cmmlu.jsonl      # 官方 haonan-li/cmmlu，全 subject test
├── mmlu.jsonl       # 官方 cais/mmlu，全 subject test
└── demo.jsonl       # 自有冒烟包：ceval/cmmlu/mmlu 各取 10 题
```

## Suite（CLI `--suite`）

| 名称 | 文件 | 说明 |
|------|------|------|
| `ceval` | `ceval.jsonl` | 标准 C-Eval test split（内部 jsonl 格式） |
| `cmmlu` | `cmmlu.jsonl` | 标准 CMMLU test split |
| `mmlu` | `mmlu.jsonl` | 标准 MMLU 全 subject test |
| `demo` | `demo.jsonl` | Harness 联调用 30 题（非独立上游数据集） |

细节与许可见 **`manifest.yaml`** 各 suite 的 `source` / `license` / `origin`。

## 数据许可（重要）

本目录的 `ceval.jsonl`、`cmmlu.jsonl` 来自上游 **CC BY-NC-SA 4.0** 数据集，**不受本仓库根目录 Apache-2.0 覆盖，且禁止商业使用**；`mmlu.jsonl` 为 MIT。详见仓库根 [NOTICE](../NOTICE)。

## 维护者：重新生成 jsonl

上游数据由维护者在仓库外下载与转换（原始下载不入库）：

```bash
# 维护者一侧（需要 datasets / huggingface_hub）
pip install datasets huggingface_hub
# 转换脚本不随仓库发布
```

提交 **`benchmark/manifest.yaml`** 与 **`benchmark/*.jsonl`** 即可。
