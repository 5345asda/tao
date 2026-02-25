# Coding Style

## 核心原则：Codex-First

**Claude 不直接编写代码**，所有代码变更通过 Codex MCP 执行：

```
WRONG:  Claude 直接 Edit/Write 修改 src/ 下的代码
CORRECT: Claude 调用 mcp__codex__codex 发送编码指令
```

### 例外情况（Claude 可直接修改）

- `CLAUDE.md`、`README.md` 等文档
- `.env.example`、`package.json` 等配置文件
- 紧急单行 hotfix（需在提交信息注明原因）
- 微小变更：错字修复、注释更新、简单配置 (<20 行)

---

## 不可变性 (CRITICAL)

ALWAYS create new objects, NEVER mutate existing ones:

```
// Pseudocode
WRONG:  modify(original, field, value) → changes original in-place
CORRECT: update(original, field, value) → returns new copy with change
```

Rationale: Immutable data prevents hidden side effects, makes debugging easier, and enables safe concurrency.

## 文件组织

MANY SMALL FILES > FEW LARGE FILES:
- High cohesion, low coupling
- 200-400 lines typical, 800 max
- Extract utilities from large modules
- Organize by feature/domain, not by type

## 错误处理

ALWAYS handle errors comprehensively:
- Handle errors explicitly at every level
- Provide user-friendly error messages in UI-facing code
- Log detailed error context on the server side
- Never silently swallow errors

## 输入验证

ALWAYS validate at system boundaries:
- Validate all user input before processing
- Use schema-based validation where available
- Fail fast with clear error messages
- Never trust external data (API responses, user input, file content)

## 代码质量检查清单

在通过 Codex 完成编码后，Claude 必须验证：
- [ ] Code is readable and well-named
- [ ] Functions are small (<50 lines)
- [ ] Files are focused (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Proper error handling
- [ ] No hardcoded values (use constants or config)
- [ ] No mutation (immutable patterns used)
- [ ] 中文注释完整
- [ ] 无多余 console.log

---

## Linus 三问（决策前必问）

在 Claude 做出任何架构决策或指派 Codex 之前，必须先回答：

### 问题一：为什么要这样做？（Why）
- 这个变更解决什么问题？
- 不做会怎样？
- 有没有更简单的方式达到同样效果？

### 问题二：影响范围是什么？（What Impact）
- 这个改动会影响哪些模块/文件？
- 会不会破坏现有功能？
- 性能、包体积、用户体验有无负面影响？

### 问题三：能回退吗？（Reversible）
- 如果出了问题，能快速回退吗？
- 是否需要 feature flag 保护？
- 回退成本有多高？
