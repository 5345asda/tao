# Git Workflow

## Commit Message Format

```
<type>(<scope>): <description>

[可选 body]
```

### Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(game): 新增石像鬼角色技能` |
| `fix` | Bug 修复 | `fix(llm): 修复 SSE 流中断后未重试的问题` |
| `refactor` | 重构 (不改变功能) | `refactor(store): 拆分 game-machine atoms` |
| `style` | 样式/格式调整 | `style(ui): 调整投票面板间距` |
| `docs` | 文档更新 | `docs: 更新 CLAUDE.md 协作规范` |
| `test` | 测试相关 | `test(modes): 补充经典模式胜利条件测试` |
| `chore` | 构建/工具/依赖 | `chore: 升级 next 到 16.x` |
| `perf` | 性能优化 | `perf(render): 减少发言列表重渲染` |
| `ci` | CI/CD 配置 | `ci: 添加构建缓存` |

### Scope 范围

根据项目结构定义，例如：
- `game` - 游戏核心逻辑
- `ui` - 界面组件
- `store` - 状态管理
- `llm` - LLM 相关
- `api` - 后端通信

---

## 提交频率

- **每完成一个独立功能点**立即提交，不要攒大提交
- **每次 Codex 完成任务且通过审查后**立即提交
- **文档更新**独立提交，不混在代码提交中

---

## 提交前检查清单

Claude 在每次 git commit 前必须执行：

```bash
pnpm build        # ✅ 构建通过
pnpm lint         # ✅ 无 lint 错误
pnpm test         # ✅ 测试通过
```

---

## Feature Implementation Workflow

1. **Plan First (Claude)**
   - Use **planner** agent to create implementation plan
   - 执行 Linus 三问
   - Identify dependencies and risks
   - Break down into phases

2. **Code (Codex)**
   - Claude 调用 `mcp__codex__codex` 发送编码指令
   - Codex 编写代码和测试
   - TDD: Write tests first (RED) → Implement (GREEN) → Refactor

3. **Code Review (Claude)**
   - Use **code-reviewer** agent 审查 Codex 产出
   - Address CRITICAL and HIGH issues
   - 不通过 → 返回 Step 2 让 Codex 修复

4. **Verify (Claude)**
   - pnpm build
   - pnpm lint
   - pnpm test
   - 不通过 → 使用 **systematic-debugging** → Codex 修复

5. **Commit & Push (Claude)**
   - Detailed commit messages
   - Follow conventional commits format

---

## Pull Request Workflow

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Include test plan with TODOs
5. Push with `-u` flag if new branch

---

## 分支策略

```
main (生产分支)
  │
  ├── feat/xxx    # 功能分支，开发完成后合并到 main
  ├── fix/xxx     # 修复分支
  └── refactor/xxx # 重构分支
```

- 简单任务：直接在 `main` 上提交
- 复杂任务（涉及 3+ 文件）：创建功能分支，使用 `skill: using-git-worktrees`
- 完成后使用 `skill: finishing-a-development-branch` 决策合并方式
