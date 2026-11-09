# Case 工作区

每个子目录是一场 Case（`case.yaml` + `ssj-<profile>/` + **`reports/`**）。配方定义在 **`templates/case/<case_id>.yaml`**。

**报告路径（两层）：**

| 位置 | 谁写 | 用途 |
|------|------|------|
| `case/<id>/ssj-<profile>/reports/` | `ssj eval`（子进程 cwd） | 单次 eval JSON 暂存 |
| `case/<id>/reports/<profile>/` | **`arena run`** 从上面拷贝 | Case 汇总层；**`arena summary`** 读这里生成 `export/` |

不要在**仓库根**出现 `reports/`（那是误把仓库根当 ssj 进程根跑 eval；已 gitignore `/reports/`）。

| Case | 说明 |
|------|------|
| [case001-4llm-demo](./case001-4llm-demo/) | 四模型 ds / kimi / jev / mimo × **demo** + `arena run` / `export` |

```bash
arena list
arena init <case_id>          # 例：arena init case001-4llm-demo
arena check --case <case_id>
arena run --case <case_id> all
arena summary --case <case_id>
```

删除工作区：`arena del <case_id>`（确认后删除）；`arena del <case_id> --silent` 不询问
