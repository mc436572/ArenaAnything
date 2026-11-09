# Case profiles（Arena `arena init <case_id>`）

每个 `<case_id>.yaml` 是一场 Case 的 **锁定配方**（矩阵、套件、ssj 版本）。`arena init` 将配方物化到仓库根下 `case/<case_id>/`（含 `ssj-<profile>/`）。

新增 Case：在此目录增加 `<case_id>.yaml`（`case_id` 字段须与文件名一致），可选子目录 `<case_id>/` 放置 `MODELS.md`、`README.md` 等一并拷贝的工件。
