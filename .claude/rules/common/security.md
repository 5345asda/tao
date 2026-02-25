# Security Guidelines

## Mandatory Security Checks

Before ANY commit (Claude 在提交前必须验证):
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized HTML)
- [ ] CSRF protection enabled
- [ ] Authentication/authorization verified
- [ ] Rate limiting on all endpoints
- [ ] Error messages don't leak sensitive data

---

## Codex 编码安全要求

当通过 Codex 编写代码时，Claude 必须在编码指令中包含安全要求：

```markdown
## Security Requirements
- 验证所有用户输入
- 使用参数化查询防止 SQL 注入
- 对输出进行 HTML 转义防止 XSS
- 不在错误消息中暴露敏感信息
- 使用环境变量存储 secrets
```

---

## Secret Management

- NEVER hardcode secrets in source code
- ALWAYS use environment variables or a secret manager
- Validate that required secrets are present at startup
- Rotate any secrets that may have been exposed

### Codex 不得写入的内容

**在编码指令中明确禁止 Codex 写入：**
- API keys
- Passwords
- Tokens
- Private keys
- Database credentials
- `.env` 文件内容（只允许 `.env.example`）

---

## Security Response Protocol

If security issue found:
1. STOP immediately
2. Use **security-reviewer** agent
3. 通过 Codex 修复 CRITICAL issues
4. Rotate any exposed secrets
5. Review entire codebase for similar issues

---

## 安全审查触发条件

自动触发 **security-reviewer** agent：
- 添加认证功能
- 处理用户输入
- 创建 API 端点
- 处理支付相关功能
- 存储敏感数据

---

## API 安全检查清单

Codex 编写 API 时必须遵循：
- [ ] 所有端点有认证/授权检查
- [ ] 输入验证使用 schema
- [ ] Rate limiting 配置
- [ ] CORS 配置正确
- [ ] 不暴露内部错误信息
- [ ] 敏感操作有日志记录
