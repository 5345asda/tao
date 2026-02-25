# Hooks System

## Hook Types

- **PreToolUse**: Before tool execution (validation, parameter modification)
- **PostToolUse**: After tool execution (auto-format, checks)
- **Stop**: When session ends (final verification)

---

## ⚠️ 强制流程：Skill-First 工作流

### PreToolUse 检查（所有复杂任务）

**在执行以下操作前，必须先调用 Skill：**

| 操作类型 | 必须先调用的 Skill |
|----------|-------------------|
| 新功能开发 | `brainstorming` → `writing-plans` |
| Bug 修复 | `systematic-debugging` |
| 代码重构 | `brainstorming` → `writing-plans` |
| 知识收集/研究 | `brainstorming` 或 `find-skills` |
| 代码审查 | `requesting-code-review` |
| 测试编写 | `tdd-workflow` 或 `test-driven-development` |

### 流程检查清单

```markdown
收到用户请求后，立即执行：

1. [ ] 判断任务类型（开发/修复/研究/审查）
2. [ ] 调用对应的 Skill 工具
3. [ ] 等待 Skill 指导
4. [ ] 按 Skill 流程执行
```

### 违规检测

如果 Claude 在没有调用 Skill 的情况下直接：
- 启动 Task 子代理
- 调用 mcp__codex__codex
- 执行复杂代码分析

**应该立即停止，返回调用 Skill**

### 唯一例外

以下情况可以直接执行，无需 Skill：
- 简单文件读取（"读一下这个文件"）
- 用户明确说"跳过 skills"或"直接做"
- 纯文档编辑（.md 文件，无代码逻辑）
- Git 操作（commit/push/status）
- 单行配置修改

---

## Codex MCP 调用验证

### PreToolUse 检查

在调用 `mcp__codex__codex` 前验证：

```javascript
// 必须包含的参数
const requiredParams = {
  model: "gpt-5.3-codex",
  sandbox: "danger-full-access",
  approval-policy: "never"
};

// 检查是否缺少必需参数
if (!hasAllRequiredParams(call, requiredParams)) {
  throw new Error("Codex MCP 调用缺少必需参数");
}
```

### PostToolUse 检查

Codex 完成编码后自动触发：
1. **code-reviewer** agent 审查代码质量
2. 检查是否有硬编码的 secrets
3. 检查是否有 any 类型泄漏

---

## Auto-Accept Permissions

Use with caution:
- Enable for trusted, well-defined plans
- Disable for exploratory work
- Never use dangerously-skip-permissions flag
- Configure `allowedTools` in `~/.claude.json` instead

---

## TodoWrite / TaskList Best Practices

Use TaskCreate / TaskUpdate tools to:
- Track progress on multi-step tasks
- Verify understanding of instructions
- Enable real-time steering
- Show granular implementation steps

Task list reveals:
- Out of order steps
- Missing items
- Extra unnecessary items
- Wrong granularity
- Misinterpreted requirements

---

## 代码变更自动检查

### Claude 直接修改代码时警告

如果 Claude 尝试直接 Edit/Write `src/` 下的文件（非例外情况）：

```
⚠️ 警告：检测到 Claude 直接修改业务代码
建议：通过 mcp__codex__codex 调用 Codex 执行编码任务
例外：文档、配置、<20行的微小变更
```

### 提交前自动验证

```
✅ 必须通过：
- pnpm build
- pnpm lint
- pnpm test

❌ 如果失败：
- 使用 systematic-debugging skill 定位问题
- 通过 Codex 修复
- 重新验证
```

---

## 子代理启动验证

当启动子代理执行编码任务时：

```markdown
✅ 正确方式：
Launch agent → Agent calls mcp__codex__codex → Codex writes code

❌ 错误方式：
Launch agent → Agent directly writes code (unless trivial)
```
