# 发布到 GitHub

当前目录已经是一个使用 `main` 分支的干净 Git 仓库。首次公开发布前，建议按下面的顺序操作。

## 1. 最后检查

确认工作区干净：

```bash
git status --short --branch
```

查看将公开的全部路径：

```bash
git ls-files
```

重点确认没有加入真实的 `hosts.json`、工作报告、`evidence.json`、SSH 配置、内部地址或认证材料。

重新运行测试：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_*.py' -v
```

## 2. 创建空仓库

在 GitHub 新建一个 **Public** 仓库。推荐名称：

```text
reflect-workday
```

不要让 GitHub 自动创建 README、`.gitignore` 或 LICENSE，因为本地仓库已经包含这些文件。

## 3. 添加远端并推送

SSH 方式：

```bash
git remote add origin git@github.com:YOUR_ACCOUNT/reflect-workday.git
git push -u origin main
```

HTTPS 方式：

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/reflect-workday.git
git push -u origin main
```

推送会修改外部公开状态，因此应在确认账号、仓库名和 staged 内容后由仓库所有者执行。

## 4. 更新克隆地址

仓库上线后，把 README 中的 `YOUR_REPOSITORY_URL` 换成真实地址，然后提交：

```bash
git add README.md README.en.md
git commit -m "docs: add public repository URL"
git push
```

## 5. 建议的 GitHub 设置

- 在 **Settings → General** 添加项目简介和截图。
- 在 **Settings → Code security** 开启 private vulnerability reporting。
- 在 **About** 中添加 `codex`、`skills`、`privacy`、`productivity` 等主题。
- 首次发布可创建 `v0.1.0` tag，并附上 `CHANGELOG.md` 中的说明。

## 6. 发布 skill 包

仓库的 Release 可以附带 `reflect-workday.skill`。不要把私人报告或本机生成的 `evidence.json` 一并上传。
