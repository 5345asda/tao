# Common Patterns

## Codex 调用模式

### 标准编码任务流程

```
1. Claude 分析需求 → Linus 三问
2. Claude 设计方案 → 编写结构化指令
3. Claude 调用 mcp__codex__codex "编码指令"
4. Codex 执行编码 → 返回结果
5. Claude 审查代码 → code-reviewer agent
6. Claude 验证 → build + lint + test
7. Claude 提交 → git commit
```

### 多任务并行执行

对于 2+ 个独立编码任务，使用 **dispatching-parallel-agents** skill：
- 每个 agent 独立调用 Codex
- 避免共享状态
- 完成后汇总结果

---

## Skeleton Projects

When implementing new functionality:
1. Search for battle-tested skeleton projects
2. Use parallel agents to evaluate options:
   - Security assessment
   - Extensibility analysis
   - Relevance scoring
   - Implementation planning
3. Clone best match as foundation
4. 通过 Codex 迭代开发

---

## Design Patterns

### Repository Pattern

Encapsulate data access behind a consistent interface:
- Define standard operations: findAll, findById, create, update, delete
- Concrete implementations handle storage details (database, API, file, etc.)
- Business logic depends on the abstract interface, not the storage mechanism
- Enables easy swapping of data sources and simplifies testing with mocks

### API Response Format

Use a consistent envelope for all API responses:
- Include a success/status indicator
- Include the data payload (nullable on error)
- Include an error message field (nullable on success)
- Include metadata for paginated responses (total, page, limit)

---

## 分离关注点模式

### Claude 的职责
- ✅ Plan, search, decide, coordinate
- ✅ 分析需求，澄清模糊点
- ✅ 设计技术方案和架构
- ✅ 将需求拆分为可执行的编码任务
- ✅ 编写清晰、完整的编码指令给 Codex
- ✅ 审查 Codex 产出的代码
- ✅ 执行最终验证（build / lint / test）
- ✅ 管理 Git 提交和分支

### Codex 的职责
- ✅ 编写和修改代码
- ✅ 编写测试
- ✅ 分析和修复 Bug
- ✅ 重构和优化代码

---

## 简化数据结构优于修补逻辑

- 复杂的数据转换逻辑 → 重新设计数据结构
- >3 层缩进 → 重新设计流程
- 复杂流程 → 先简化需求
