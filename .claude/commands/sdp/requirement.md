# /requirement <text-or-path>
You are Claude Code. Refine a requirement and normalize it for task generation.

## Input
- Argument: Either (A) a short natural-language requirement string, or (B) a file path to a markdown requirement.
- If a path is given, read it. Otherwise, take the argument string as the base requirement.

## Language Configuration

Read `.sdp/config/language.yml` to determine the output language:
- If `language: en`, generate all content in **English**
- If `language: ja`, generate all content in **Japanese**

Use templates from `.sdp/templates/<lang>/` directory based on the configured language.

## Context Files
Read these for context:
- `.sdp/product.md` - Business context and goals
- `.sdp/tech.md` - Technical stack and constraints
- `.sdp/structure.md` - Code structure and organization

## Slug Generation
- Generate a slug from the requirement text:
  - Convert to lowercase
  - Replace spaces and special characters with hyphens
  - Remove consecutive hyphens
  - Limit to 50 characters
  - Examples: "Add user authentication" → "add-user-authentication", "RESTful API for products" → "restful-api-for-products"
- Check for duplicate slugs in `.sdp/specs/` directory by listing existing folders
- If duplicate exists, append `-2`, `-3`, etc.
- Create `.sdp/specs/` directory if it doesn't exist

## Deliverable
- Create or update a file at `.sdp/specs/<slug>/requirement.md` with the refined spec.
- Create the `.sdp/specs/<slug>/` directory if it doesn't exist
- The file must follow `.sdp/templates/<lang>/requirement.md` sections exactly (use the language-specific template).

## Refinement Rules

### Content Alignment
- **Product alignment**: Align with `.sdp/product.md` (goals/KPIs)
- **Technical feasibility**: Consider constraints from `.sdp/tech.md`
- **Structure awareness**: Reference existing modules from `.sdp/structure.md`

### Required Sections (from template)
1. **機能概要**: Business goal and feature purpose statement
2. **ユーザーストーリー**: User stories in "Who/What/Why" format
3. **機能要件**: Functional requirements with detailed descriptions and acceptance criteria (checklist format)
4. **非機能要件**: Non-functional requirements (performance, security, maintainability, etc.) as needed

### Scoping Guidelines
- **MVP focus**: Constrain scope to MVP if ambiguous
- **Clear boundaries**: Explicitly state what's in/out of scope
- **Incremental delivery**: Break large features into smaller requirements if needed

## Output Format

Generate all content based on the configured language (`.sdp/config/language.yml`).

After writing the file, print a summary in the same language as the content:

For Japanese:
```
【要件定義完了】
📋 Slug: <slug>
📝 タイトル: <要件タイトル>
📁 ファイル: .sdp/specs/<slug>/requirement.md

💡 次のステップ:
  - 要件内容を確認し、修正が必要な場合は自然言語で指示してください
  - 要件が確定したら /sdp:pre-design <slug> で設計案を評価してください
```

For English:
```
【Requirement Definition Completed】
📋 Slug: <slug>
📝 Title: <requirement title>
📁 File: .sdp/specs/<slug>/requirement.md

💡 Next Steps:
  - Review the requirement and provide feedback if changes needed
  - When requirement is finalized: Use /sdp:pre-design <slug> to evaluate design options
```

## Cross-Platform Compatibility

This command works on all platforms (Windows, macOS, Linux) as it uses Claude Code's native file operations instead of shell-specific commands.

## Allowed Tools
Read, Write, Edit, File Search, Grep only