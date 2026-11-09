# case001-4llm-demo — 模型与路由说明（发 GitHub Case 用）

**白板个体：** `ssj` @ **0.1.0**（`templates/ssj/0.1.0`，single-turn，eval + chat；JEV 无 chat）

**套件：** `demo` — 30 题（`benchmark/demo.jsonl`）

**Eval 预设：** `demo-profile`（`system_prompt` 单字母 A–D；MiMo 建议模板内 `max_tokens: 256`）

| Profile | LiteLLM id | 说明 | `.env` 密钥 |
|---------|------------|------|-------------|
| **ds** | `deepseek/deepseek-chat` | DeepSeek Chat (V3) | `DEEPSEEK_API_KEY`，可选 `DEEPSEEK_API_BASE`（默认 `https://api.deepseek.com/v1`） |
| **kimi** | `moonshot/kimi-k3` | Kimi K3.1 Pro（国内 Moonshot） | `MOONSHOT_API_KEY`，可选 `MOONSHOT_API_BASE` |
| **jev** | `typesafe/jev-latest` | JEV 直连 TypeSafe；eval 走 SystemOne **decisions**，wire model **`jev-latest`** | `TYPESAFE_API_KEY`，base `https://api.typesafe.ai` |
| **mimo** | `openrouter/xiaomi/mimo-v2.6-flash` | MiMo V2.6 Flash via OpenRouter | `OPENROUTER_API_KEY` |

每个 profile 对应独立进程根 `ssj-<profile>/`，**密钥不共享、不提交 git**。
