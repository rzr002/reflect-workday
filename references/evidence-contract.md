# Evidence contract

`evidence.json` 是经过裁剪的数字线索，不是原始日志，也不是对真实工时的判断。

## 顶层字段

- `schema_version`: 当前为 `2`；渲染器仍接受既有版本 `1`。
- `person`: 页面展示姓名及 Git author 匹配串。
- `period`: `start_inclusive`、`end_exclusive`、`timezone`。
- `sources`: 各来源的扫描数、命中数和错误。
- `events`: 按时间排序的短线索。
- `limitations`: 本次采集的局限。
- `collection_status`: 多机结果使用 `complete`、`partial` 或 `failed`；单机结果可省略。

单机 `sources` 包含 `codex` 与 `git`。使用 `--portable` 时必须省略 `root` 和 `roots`，并裁剪错误中的绝对路径。多机合并后的 `sources.hosts` 只包含友好 `host_id`、采集状态、安全错误码、事件数和可选警告码，不包含 SSH 别名、真实主机名、远端路径或认证原文。

## Event

```json
{
  "id": "codex:<turn id>",
  "source": "codex",
  "shape": "interval",
  "start": "2025-03-10T09:11:19+08:00",
  "end": "2025-03-10T09:24:01+08:00",
  "project": "sample-service",
  "title": "核对接口兼容约束",
  "outcome": "确认旧客户端继续使用兼容分支",
  "evidence": "observed"
}
```

- `source`: `codex` 或 `git`。人工补记放在 `reflection.json`。
- `shape`: `interval` 表示可观察到的任务窗口，`point` 表示 Git commit 等时间点。
- `start` / `end`: `end` 可为 `null`。Codex 区间只是 agent 运行窗口，不代表用户持续工作。
- `project`: 只放目录或仓库短名，不放完整路径。
- `title`: 用户请求首个有效文本行，已裁剪和脱敏。
- `outcome`: assistant 最终结果的首个有效文本行；没有则为 `null`。
- `evidence`: 采集器只写 `observed`。
- `host_ids`: 多机合并后出现，列出贡献该线索的友好主机标识。
- `start_utc` / `end_utc`: 多机合并后出现，保存用于跨主机比较的 UTC 时间；原 `start` / `end` 继续用于所选报告时区的页面展示。
- `source_timezones`: 多机合并后出现，列出贡献主机 evidence 声明的来源时区。
- Git 事件额外包含 `repo_fingerprint` 与 `commit_hash`；指纹是不可逆摘要，不包含原始 remote URL。多机去重键为二者组合。

同一个 Codex 稳定事件出现在多台主机时合并 `host_ids`，不复制事件。相同 commit hash 只有在 `repo_fingerprint` 也相同时才合并，避免不同仓库中的同 hash 被错误折叠。

不要从事件数量、token、agent 累计运行时间推断绩效或总工时。并发任务会重叠，Git commit 只是一个时间点。
