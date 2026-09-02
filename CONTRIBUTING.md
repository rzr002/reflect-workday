# 参与贡献

感谢你改进 Reflect Workday。这个项目处理私人工作线索，因此隐私正确性和功能正确性同样重要。

## 开始之前

1. Fork 仓库并创建一个短分支。
2. 使用合成数据复现问题。
3. 不要把真实报告、session、主机清单或凭据加入仓库。

## 本地验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_*.py' -v
```

修改页面模板时，还应运行对应的 Playwright 布局检查：

```bash
node scripts/check_browser_layout.js DAILY_HTML DAILY_SCREENSHOT
node scripts/check_weekly_layout.js WEEKLY_HTML WEEKLY_SCREENSHOT
```

检查项包括七日顺序、卡片重叠、文本裁切、横向溢出、只读约束和详情弹窗。

## 代码风格

- Python 保持标准库优先，避免为小功能引入依赖。
- 采集器只输出短标题和必要元数据。
- 错误信息使用安全错误码，不回显远端路径或认证原文。
- 新增数据字段时，同步更新 `references/` 中的契约和测试。
- 页面应保持离线可用，并在桌面与移动宽度下可读。

## 隐私检查清单

提交前确认：

- [ ] 没有真实姓名、用户名、邮箱、IP、域名或绝对路径。
- [ ] 没有密码、动态码、令牌、私钥、Cookie 或 SSH 配置。
- [ ] 没有真实 Codex 对话、业务日志、trace ID 或项目记录。
- [ ] 示例数据使用 `示例用户`、`sample-service` 等合成内容。
- [ ] 新的远端功能仍要求先展示计划并获得用户确认。
- [ ] 原始 session 不会离开被扫描的主机。

## Pull Request

请在 PR 中说明：

- 解决的问题；
- 用户可见变化；
- 已运行的测试；
- 对隐私边界是否有影响。

如果变更涉及敏感信息泄露，请不要提交公开 issue 或 PR，改用 [SECURITY.md](SECURITY.md) 中的私下报告方式。
