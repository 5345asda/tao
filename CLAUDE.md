# CLAUDE.md

> **详细协作规则**：见 `.claude/rules/` 目录

## 核心原则

1. **Codex-First**: 代码变更通过 `mcp__codex__codex` 执行，Claude 只负责规划、审查、验证
2. **例外**：文档、配置文件、<20行的简单修改可由 Claude 直接处理
3. **Linus 三问**：重大决策前必须回答 Why / Impact / Reversible

---

## Codex MCP 调用 (CRITICAL)

**每次调用必须包含以下参数：**

```javascript
mcp__codex__codex({
  model: "gpt-5.3-codex",
  sandbox: "danger-full-access",
  approval-policy: "never",
  prompt: "<结构化编码指令>"
})
```

**指令模板**：
```markdown
## Context
- Tech Stack: [技术栈]
- Files: [路径]: [用途]

## Task
[一句话描述]

## Constraints
- Must preserve: [现有行为]
- 代码注释使用中文

## Acceptance
- [ ] pnpm build 通过
```

---

## Skill-First 工作流

**所有涉及分析/规划/编码/审查/调试的任务，必须先调用 Skill 工具**：

| 任务类型 | 必须调用的 Skill |
|----------|-----------------|
| 新功能开发 | `brainstorming` → `writing-plans` |
| Bug 修复 | `systematic-debugging` |
| 代码重构 | `brainstorming` → `writing-plans` |
| 代码审查 | `requesting-code-review` |
| 测试编写 | `test-driven-development` |

**可直接执行（无需 Skill）**：
- 简单文件读取
- 用户明确说"跳过 skills"
- 纯文档/配置编辑（.md/.json/.yaml，无逻辑）
- Git 操作（commit/push/status）

---

## 开发流程

```
需求 → brainstorming → writing-plans → mcp__codex__codex → code-reviewer → 验证 → git commit
```

### 验证命令

```bash
pnpm build && pnpm lint && pnpm test
```

### Git 提交格式

```
<type>(<scope>): <description>
```

常用 type: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

---

## 可用子代理

| Agent | 用途 |
|-------|------|
| planner | 复杂功能实现规划 |
| architect | 架构设计决策 |
| tdd-guide | 测试驱动开发指导 |
| code-reviewer | Codex 代码审查 |
| security-reviewer | 提交前安全分析 |
| build-error-resolver | 构建错误修复 |
| e2e-runner | E2E 测试 |
| refactor-cleaner | 死代码清理 |

---

## 详细规则索引

| 规则 | 文件 |
|------|------|
| 协作体系 & 任务路由 | `.claude/rules/common/agents.md` |
| 编码规范 & Linus三问 | `.claude/rules/common/coding-style.md` |
| Git 工作流 | `.claude/rules/common/git-workflow.md` |
| 测试规范 | `.claude/rules/common/testing.md` |
| 安全规范 | `.claude/rules/common/security.md` |
| Hooks 系统 | `.claude/rules/common/hooks.md` |
| 性能优化 | `.claude/rules/common/performance.md` |
| 常用模式 | `.claude/rules/common/patterns.md` |
| TypeScript 规范 | `.claude/rules/typescript/` |
| Python 规范 | `.claude/rules/python/` |
| Go 规范 | `.claude/rules/golang/` |
