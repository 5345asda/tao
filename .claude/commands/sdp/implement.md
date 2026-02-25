````markdown
# /implement <slug> [task-id]
You are Claude Code. Implement repository changes for the given requirement by executing the scoped development tasks.

## Purpose
- Transform the approved design and task plan into code changes.
- Keep the implementation traceable to the requirement, design, and estimation artifacts.
- Produce verifiable progress records and test evidence.

## Inputs
- **slug**: Requirement identifier referencing `.sdp/specs/<slug>/`
- **task-id** (optional): Specific task ID from `.sdp/specs/<slug>/tasks.yml` (e.g., `T-003`).
  - If omitted, execute **all** tasks listed in `tasks.yml`.
  - Multiple task IDs may be provided, separated by spaces (e.g., `/sdp:implement auth-login T-002 T-004`).

## Language Configuration
Read `.sdp/config/language.yml`:
- `language: en` → generate all summaries in **English**
- `language: ja` → generate all summaries in **Japanese**

Use templates in `.sdp/templates/<lang>/` based on the configured language.

## Context Files
Read the following before implementation (if files exist):
- `.sdp/specs/<slug>/requirement.md`
- `.sdp/specs/<slug>/design.md`
- `.sdp/specs/<slug>/tasks.yml`
- `.sdp/product.md`
- `.sdp/tech.md`
- `.sdp/structure.md`
- `.sdp/specs/<slug>/implementation.md` (for continuity)

## Pre-Check
1. Verify `.sdp/specs/<slug>/` directory exists.
2. Verify `.sdp/specs/<slug>/requirement.md` exists.
3. Verify `.sdp/specs/<slug>/tasks.yml` exists.
4. If `.sdp/specs/<slug>/design.md` is missing, warn the user but proceed with caution.
5. Validate each requested `task-id` exists in `tasks.yml`; fail fast if not found.
6. Ensure working tree is clean or list uncommitted files before starting.

## Task Selection Logic
1. Load all tasks from `.sdp/specs/<slug>/tasks.yml`.
2. If specific task IDs are provided, subset to those tasks (preserving order given).
3. Otherwise, process tasks in the order they appear in `tasks.yml`.
4. Respect dependencies declared in `depends_on`; warn if user-selected subset breaks dependency order.
5. For each task, capture:
   - `title`, `description`
   - `deliverables`
   - `dod`
   - `estimate`
   - `risks`

## Implementation Workflow
For **each** selected task, sequentially:

1. **Align on Intent**
   - Summarize task goal in one paragraph, referencing design decisions and relevant steering docs.
   - Confirm required files/modules from `deliverables` and repository structure.

2. **Plan the Changes**
   - Outline the minimal code edits needed to satisfy `deliverables` and `dod`.
   - Identify new files, tests, migrations, documentation updates.
   - Note potential conflicts or risk mitigations.

3. **Apply Changes**
   - Modify code files using the appropriate tools.
   - Preserve project conventions (linting, formatting, naming).
   - Update or create tests that validate the `dod` criteria.
   - Keep commits atomic per task if possible (but do not run git commands).

4. **Verify**
   - Run targeted tests or commands required by `dod`.
   - If no automated tests exist, describe manual validation performed.
   - Capture failures, retry when feasible, and document unresolved issues.

5. **Document Results**
   - Append a task section to `.sdp/specs/<slug>/implementation.md` (see template requirements below).
   - Record:
     - Date & time
     - Files touched
     - Tests executed and outcomes
     - Follow-up work or new risks

## Implementation Log Template
Use `.sdp/templates/<lang>/implementation.md` as the structural template when creating or updating `.sdp/specs/<slug>/implementation.md`.

- **CREATE mode**: Generate the entire file from template, filling sections for each executed task.
- **UPDATE mode**: Append a new "Iteration" section while preserving existing content. Keep chronological order.
- Each task subsection must include:
  - Task ID & title
  - Goal statement
  - Detailed summary of code changes
  - File list with roles
  - DoD verification notes
  - Test evidence (commands, results)
  - Remaining risks or TODOs

## Output Summary
After implementation, print a summary in the configured language:
```
【実装完了】 / 【Implementation Complete】
📐 要件 / Requirement: <slug>
🛠️ 実行タスク / Tasks executed: <T-IDs>
📁 変更ファイル / Files changed: <count>
✅ テスト結果 / Test status: <pass/fail summary>
⚠️ フォローアップ / Follow-ups: <if any>

💡 次のステップ / Next steps:
  - レビューや追加作業の提案
  - 関連コマンド例（例: /sdp:show-plan <slug>）
```

## Good Practices
- Respect code ownership boundaries—modify only necessary files.
- If design or tasks lack clarity, annotate assumptions in the implementation log.
- Surface blockers immediately with actionable recommendations.
- Avoid leaving the repository in a broken state; if unavoidable, document reasons and rollback instructions.

## Cross-Platform Compatibility
This command relies solely on Claude Code’s native file tools (Read, Write, Edit, File Search, Grep, Apply Patch). No shell-specific commands.

## Allowed Tools
Read, Write, Edit, File Search, Grep only
````