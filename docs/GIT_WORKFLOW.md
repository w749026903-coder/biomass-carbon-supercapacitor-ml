# 每次任务完成后的Git同步

用户已授权本项目在任务完成时正常commit和push；不需要每次再询问是否同步。授权限定当前项目的已核实origin，不包含公开仓库、其它远程、账号权限或付费设置。

## 收尾步骤

1. 在自己负责的目录完成任务和适当检查。
2. 记录结果、文件、核验、限制与下一步；更新自己的交接/manifest。
3. 查看工作区和暂存区，避免纳入其他agent未完成的改动。
4. 提交本任务文件和进度增量，正常push当前分支。
5. 比对远程分支SHA与本地提交。只有远程包含本次提交才说“已同步”。

建议使用本项目工具，路径可为本任务拥有的文件或目录：

```bash
python tools/sync_task.py --message "docs: 完成某项任务" --summary "完成内容" --checks "实际执行的核验" --next "下一步或未决项" --paths "本任务目录" --dry-run
python tools/sync_task.py --message "docs: 完成某项任务" --summary "完成内容" --checks "实际执行的核验" --next "下一步或未决项" --paths "本任务目录"
```

工具要求暂存区起初为空，拒绝项目外路径，自动追加进度，只stage显式路径；不自动pull/merge/rebase/stash，不强推。执行前仍须由agent检查任务diff和对应目录归属。它不是文件后台监听器。

## 并行任务

- 同一工作目录提交时使用本工具的仓库锁，避免两个任务争抢暂存区。
- 不使用 `git add .` 作日常收尾。首次初始化保存全目录是此次用户单独授权的初始快照。
- 其他agent已有暂存内容时不要替它提交或清除；等待其完成后继续。
- 远程拒绝fast-forward时先fetch并检查历史；保留本地提交，明确冲突后再协调，不用force解决。
- SQLite按完整快照版本化，不能文本合并二进制库。只更新自己任务的数据库版本。

## 认证与故障

GitHub CLI认证可用 `gh auth status` 检查；必要时由用户完成 `gh auth login --hostname github.com --git-protocol https --web` 的官方浏览器登录/设备授权。不要让用户在聊天或仓库粘贴Token。

Git LFS和普通Git都要成功。遇到额度、权限或网络错误，不启用付费、不关闭TLS、不更换未经授权远程，也不把LFS指针当资料上传完成。修复认证后可用 `git lfs push origin <branch>` 和普通push补传；先查看日志确认哪些步骤已完成。

项目不自动安装全局工具，不修改Windows代理或防火墙。需要现有本地代理时仅对该次命令设置，不写全局Git配置。

## 大文件

`.gitattributes`将PDF、压缩包、Word、工作簿和SQLite纳入LFS；保留原始字节。克隆后运行 `git lfs pull`。官方说明：[Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)、[大文件限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。
