# Testing Requirements

## 核心原则：Codex 编写测试

**所有测试代码由 Codex 编写**，Claude 负责规划测试策略和审查测试质量。

```
WRONG:  Claude 直接编写测试代码
CORRECT: Claude 调用 mcp__codex__codex 发送测试编写指令
```

---

## Minimum Test Coverage: 95%

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

---

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED) - **通过 Codex**
2. Run test - it should FAIL
3. Write minimal implementation (GREEN) - **通过 Codex**
4. Run test - it should PASS
5. Refactor (IMPROVE) - **通过 Codex**
6. Verify coverage (95%+)

### Codex 测试指令模板

```markdown
## Task
为 [功能名称] 编写单元测试

## 具体要求
1. 测试文件放在 __tests__/ 目录
2. 使用 Jest + @testing-library/react
3. 覆盖正常流程和边界情况
4. Mock 外部依赖

## Test Cases
- [ ] Case 1: 正常输入返回预期结果
- [ ] Case 2: 空输入抛出错误
- [ ] Case 3: 边界值处理正确

## Files to Create/Modify
- [path] - [描述]
```

---

## Troubleshooting Test Failures

1. Use **tdd-guide** agent 分析失败原因
2. 通过 Codex 修复实现代码（不是测试代码，除非测试本身有误）
3. Check test isolation
4. Verify mocks are correct

---

## Agent Support

- **tdd-guide** - Use PROACTIVELY for new features, enforces write-tests-first
- **code-reviewer** - After Codex writes tests, review for quality

---

## 测试质量检查清单

在 Codex 完成测试编写后，Claude 必须验证：
- [ ] 测试覆盖正常流程
- [ ] 测试覆盖边界情况
- [ ] 测试覆盖错误处理
- [ ] Mock 设置正确
- [ ] 测试隔离性好
- [ ] 测试命名清晰
- [ ] 无硬编码数据
