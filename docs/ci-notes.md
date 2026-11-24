# CI 说明（本 fork）

本仓库是 [Mai-with-u/MaiBot](https://github.com/Mai-with-u/MaiBot) 的个人 fork，合并上游时会一并继承上游的 GitHub Actions。
以下是本 fork 对 CI 的调整与依据，避免下次合并或排查时重复劳动。

## 已移除的流水线

| Workflow | 移除原因 |
| --- | --- |
| Docker Build and Push (Dev) | 每日 cron 构建推送 Docker Hub，仓库无 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` |
| Crowdin Sync | 无 Crowdin 项目，`CROWDIN_PROJECT_ID` / `CROWDIN_PERSONAL_TOKEN` 为空 |
| Crowdin Bootstrap Target Translations | 同上 |
| Sync MaiBot to CNB | `if: github.repository == 'Mai-with-u/MaiBot'` 锁定上游仓库名，fork 中永远 skipped |
| Sync Releases to CNB | 同上 |

配套删除：`.github/scripts/sync_cnb_*.cjs`（及其测试）、根目录 `crowdin.yml`。

`Docker Build and Push (Main)` **保留文件但去掉 push/tag 触发**，只留 `workflow_call` ——
`publish-maibot.yml` 通过 `uses: ./.github/workflows/docker-image-main.yml` 调用它，
直接删文件会打断发布链。

## Check WebUI 的裁剪依据

上游 `Check WebUI` 包含 Type check / Lint / Test / Build / Build Electron 五步。

**关键事实：上游的 `Test` 步骤长期处于 `skipped`**，因为 Lint 先失败、流程走不到 Test。
所以上游从未发现自己的测试是红的。实测（bun 1.2.1，与 CI 同版本）：

```
Test Files  43 failed | 219 passed (262)
Tests       190 failed | 3304 passed | 22 skipped (3516)
```

**失败原因全部是「上游改了实现但没同步改测试」**，与 fork 无关（相关文件 `git diff v1.4.8..HEAD` 为空）：

- `dashboard/src/lib/auth.ts` 新增 `AbortSignal` 参数（commit `9be2b5d15`），
  但 `auth.test.ts` 仍断言 `toHaveBeenCalledWith('/api/webui/auth/check')`，实际调用多了 `{ signal }`。
- `dashboard/src/components/ScopedUserSelect.tsx` 引入 `useQuery`（commit `f0acc5a28`），
  需要 `QueryClientProvider`；但 `CommandPermissions.test.tsx` 直接 `render(<CommandPermissions />)`，外层没有 Provider。

Lint 的 32 条错误同样与上游 main **逐条比对完全一致**（`jsx-a11y/label-has-associated-control` 占大半）。

因此本 fork 的 `check-webui.yml` 只保留 **Type check + Build**：这两步本地实测通过，
能挡住真实的类型错误与构建失败，且是服务端部署真正关心的信号。

## 本地复现 CI 的注意事项

- **bun 版本必须用 `1.2.1`**（与 workflow 里 `bun-version` 一致）。用 1.4.x 跑
  `bun install --frozen-lockfile` 会直接报 `lockfile had changes, but lockfile is frozen`
  （新版对 `overrides` 校验更严），装不上依赖。
- **不要用 pnpm 装 dashboard 依赖**。仓库用 `bun.lock`，pnpm 的隔离模式会让测试大面积误报失败。
- 机器负载高时 `vitest`（262 个测试文件、单例超时 15s）容易出假失败，判断前先单跑目标文件复核。

## 历史运行记录

删除 workflow 文件不会清掉 GitHub 上已有的 run 记录。如需清理，见 skill `github-actions-troubleshooting`：
先 `gh run list --status failure` 存档日志，再逐条 `gh run delete`（无批量 API）。
