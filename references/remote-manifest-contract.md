# Remote manifest contract

`hosts.json` 是仅保存在采集端 Mac 上的 SSH 扫描清单。它描述去哪里运行只读 collector，不保存任何认证材料，也不进入最终报告。

```json
{
  "schema_version": 1,
  "hosts": [
    {
      "host_id": "dev-a",
      "ssh_alias": "sample-server",
      "python_path": "/home/user/miniconda/bin/python3",
      "sessions_root": "/home/user/.codex/sessions",
      "repo_roots": ["/work/projects"]
    }
  ]
}
```

## 字段

- `schema_version`: 固定为 `1`。
- `hosts`: 至少一项；按清单顺序采集和合并。
- `host_id`: 报告中可见的友好稳定标识，只用小写字母、数字和连字符，最多 32 字符；不得写真实主机名或 IP。
- `ssh_alias`: `~/.ssh/config` 中的具体 Host 别名。不要在这里重复 `HostName`、`User`、端口或密钥路径。
- `python_path`: 可选；默认 `python3`。当远端非交互 Shell 的默认 Python 缺少 `zoneinfo` 时，填写支持 Python 3.9+ 的绝对解释器路径。
- `sessions_root`: 远端 Codex sessions 的绝对路径。
- `repo_roots`: 要扫描的远端项目根目录数组；可以为空。

清单中的路径会在执行前计划里展示给用户，但不会写入合并后的 `evidence.json`。

## 认证与执行

1. 先运行不带 `--execute` 的计划模式，核对别名、范围、路径和命令。
2. 需要密码时，让用户在可见的系统终端运行 `ssh <alias>`。OpenSSH 可以原生询问密码，并通过用户 SSH config 的 `ControlPersist` 保持连接。
3. 用户明确批准计划后才运行 `--execute`。调度器使用 `BatchMode=yes`，因此不会在后台等待不可见的密码输入。
4. 调度器把 bundled `collect_activity.py` 送入远端 `python3 -` 的 stdin；脚本不落盘，原始 Codex 会话不离开远端。
5. 每台主机的 stdout 必须只有 `--portable` evidence JSON。stderr 不进入报告。

任何层级出现 `password`、`passphrase`、`private_key`、`identity_file`、`token` 或 `secret` 字段时拒绝整个清单。不得读取私钥或 Shell 历史，不得关闭主机密钥校验。

## 状态

- 成功：`status: collected`，可附 `events`。
- 失败：`status: not_collected`，只写安全 `error_code`：`authentication_failed`、`host_key_failed`、`unreachable`、`timeout`、`ssh_unavailable`、`invalid_evidence` 或 `collection_failed`。
- 远端 `generated_at` 与本机相差超过 5 分钟时保留证据，并添加 `warning_codes: ["clock_skew"]`。
- 部分失败：顶层 `collection_status` 为 `partial`，继续渲染已采集主机并明确说明缺失。
- 全部失败：顶层 `collection_status` 为 `failed`，命令返回非零；不要继续生成回想结论。
