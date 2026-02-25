# /export-issues <slug>

Export task breakdown to GitHub Issues, Jira Issues, or local markdown files.

## Inputs
- **slug**: An existing requirement folder at `.sdp/specs/<slug>/` containing `tasks.yml`
- **Export Config**: `.sdp/config/export.yml` (output destination, repository, labels)

## Language Configuration

Read `.sdp/config/language.yml` to determine the output language:
- If `language: en`, generate all content in **English**
- If `language: ja`, generate all content in **Japanese**

Console output should also be in the configured language.

## Context Files
Read these for context:
- `.sdp/specs/<slug>/tasks.yml` - Task breakdown to export
- `.sdp/specs/<slug>/requirement.md` - Original requirement
- `.sdp/config/export.yml` - Export configuration (destination, repo, labels)

## Pre-Check

Before starting, verify that:
- `.sdp/specs/<slug>/` directory exists
- `.sdp/specs/<slug>/tasks.yml` file exists
- `.sdp/config/export.yml` file exists

Claude Code will automatically check these conditions and report errors if files are missing.

## Important: Configure Before Running

**Before running this command, you MUST configure `.sdp/config/export.yml`**:

1. **Set export destination**: Choose `destination: github` or `destination: local`
2. **Configure GitHub settings** (if using GitHub mode):
   - Set `github.repo` to your repository (e.g., "owner/repo")
   - Customize `github.labels` as needed
3. **Configure local settings** (if using local mode):
   - Set `local.out_dir` if different from default

**User should review and edit `.sdp/config/export.yml` before proceeding.**

## Step 1: Load Export Configuration

Read `.sdp/config/export.yml` to determine:
- `destination`: Export target (`github`, `jira`, or `local`)
- Destination-specific settings (repository, project, labels, etc.)
- `issue_mode`: How to organize tasks
  - `sub_issues` / `sub_tasks`: Create parent-child relationships
  - `linked_issues`: Create separate issues with links
  - `single_issue`: Create one comprehensive issue with all tasks

## Step 2: Determine Export Destination

Based on the `destination` field in export.yml:
- **`github`**: Export to GitHub Issues (requires `gh` CLI)
- **`jira`**: Export to Jira Issues (uses REST API v3)
- **`backlog`**: Export to Backlog Issues (uses REST API v2)
- **`local`**: Export to local markdown files (no external tools required)

### Implementation Details

For detailed implementation instructions, refer to:
- **GitHub mode**: `.sdp/docs/export-github.md`
- **Jira mode**: `.sdp/docs/export-jira.md`
- **Backlog mode**: `.sdp/docs/export-backlog.md`
- **Local mode**: `.sdp/docs/export-local.md`

## Step 3: Execute Export

### GitHub Export

If `destination: github`, read `.sdp/docs/export-github.md` for complete implementation details.

**Summary**:
1. Check `gh` CLI availability and authentication
2. Check `gh sub-issue` extension if needed
3. Create main issue using appropriate template
4. Create task issues if using sub_issues or linked_issues mode
5. Generate console output with issue URLs

### Jira Export

If `destination: jira`, read `.sdp/docs/export-jira.md` for complete implementation details.

**Summary**:
1. Check Jira configuration (url, email, project, API token)
2. Load templates and convert Wiki Markup to ADF
3. Create main issue via REST API
4. Create task issues if using sub_tasks or linked_issues mode
5. Generate console output with issue URLs

### Backlog Export

If `destination: backlog`, read `.sdp/docs/export-backlog.md` for complete implementation details.

**Summary**:
1. Check Backlog configuration (space_key, project_key, API key)
2. Get project ID and issue type IDs via REST API
3. Create main issue with Markdown description
4. Create task issues if using sub_tasks or linked_issues mode
5. Generate console output with issue URLs

### Local Export

If `destination: local`, read `.sdp/docs/export-local.md` for complete implementation details.

**Summary**:
1. Create output directory if needed
2. Generate markdown file with issue drafts
3. Generate console output with file path

### Step 3A: Create Main Issue (GitHub Mode)

The content and structure depend on `github.issue_mode`.

#### Issue Title
Format: `[<slug>] <requirement title>`

#### Issue Body Template

**For `issue_mode: single_issue`**:

Read the comprehensive single-issue template:
- **English**: `.sdp/templates/en/issue-single.md`
- **Japanese**: `.sdp/templates/ja/issue-single.md`

Replace placeholders:
- `{{requirement_summary}}`: Brief summary from `.sdp/specs/<slug>/requirement.md` Goal section
- `{{task_count}}`: Total number of tasks
- `{{expected_hours}}`: Expected hours from rollup
- `{{stddev_hours}}`: Standard deviation from rollup
- `{{confidence}}`: Confidence level from rollup
- `{{critical_path}}`: Critical path from rollup (e.g., T-001 → T-003 → T-007)
- `{{task_list}}`: Checklist of all tasks with format:
  ```
  - [ ] **T-001**: <task.title> (Expected: <mean>h, Dependencies: <depends_on>)
  - [ ] **T-002**: <task.title> (Expected: <mean>h, Dependencies: <depends_on>)
  ...
  ```
- `{{task_details}}`: Detailed breakdown of each task with format:
  ```
  ### T-001: <task.title>
  
  **Estimate**: <optimistic>h / <most_likely>h / <pessimistic>h (Expected: <mean>h)  
  **Dependencies**: <depends_on>  
  **Deliverables**: <comma-separated deliverables>  
  **DoD**: <comma-separated DoD items>  
  **Risks**: <task.risks if present>
  
  ---
  ```

**For `issue_mode: sub_issues` or `issue_mode: linked_issues`**:

Read the main issue template (without task details):
- **English**: `.sdp/templates/en/issue-main.md`
- **Japanese**: `.sdp/templates/ja/issue-main.md`

Replace placeholders:
- `{{requirement_summary}}`: Brief summary from `.sdp/specs/<slug>/requirement.md` Goal section
- `{{task_count}}`: Total number of tasks
- `{{expected_hours}}`: Expected hours from rollup
- `{{stddev_hours}}`: Standard deviation from rollup
- `{{confidence}}`: Confidence level from rollup
- `{{critical_path}}`: Critical path from rollup (e.g., T-001 → T-003 → T-007)

#### Execution

**Important**: Use `grep` and `tr` to extract issue number from output. Do NOT use `--json` flag as it may not be supported in older versions of GitHub CLI.

```bash
# Combine labels from export.yml (labels + main_issue_labels if set)
# Extract issue number from output using grep and tr (compatible with all gh versions)
MAIN_ISSUE=$(gh issue create \
  --title "[<slug>] <requirement title>" \
  --body "<formatted body>" \
  --label "<combined_labels_from_config>" \
  --repo <owner/repo> | grep -oE '#[0-9]+' | tr -d '#')
```

**If `issue_mode: single_issue`**: This is the only issue created. Skip to Step 5A.

**If `issue_mode: sub_issues` or `issue_mode: linked_issues`**: Collect the main issue number for use in creating task issues (proceed to Step 4A).

### Step 4A: Create Task Issues (GitHub Mode)

**Note**: This step is only executed if `issue_mode` is `sub_issues` or `linked_issues`. Skip this step if `issue_mode: single_issue`.

For each task in `.sdp/specs/<slug>/tasks.yml`, create an issue.

**If `issue_mode: sub_issues`**, use `gh sub-issue` extension to create sub-issues with automatic parent-child relationship.

#### Sub-Issue Title
Format: `[<slug>][T-xxx] <task.title>`

#### Sub-Issue Body Template

Read the appropriate template based on language configuration:
- **English**: `.sdp/templates/en/issue-task.md`
- **Japanese**: `.sdp/templates/ja/issue-task.md`

Replace placeholders:
- `{{description}}`: Task description
- `{{deliverables}}`: List of deliverables (bulleted list)
- `{{dod}}`: Definition of Done checklist items
- `{{dependencies}}`: List of dependencies with issue references
- `{{optimistic}}`: Optimistic estimate
- `{{most_likely}}`: Most likely estimate
- `{{pessimistic}}`: Pessimistic estimate
- `{{expected}}`: Expected (mean) estimate
- `{{risks}}`: Risk notes (if present)

#### Execution

**If `issue_mode: sub_issues`**:
Use `gh sub-issue create` to create sub-issues that are automatically linked to the parent:

**Note**: The `gh sub-issue create` command returns the full issue URL, not just the number.

```bash
# Combine labels from export.yml (labels + task_labels if set)
# If labels are set, add --label flag; otherwise omit it
# gh sub-issue returns URL (e.g., https://github.com/owner/repo/issues/123)
if [ -n "$TASK_LABELS" ]; then
  SUB_ISSUE_URL=$(gh sub-issue create --parent ${MAIN_ISSUE} \
    --repo <owner/repo> \
    --title "[T-001] <task.title>" \
    --body "<formatted body>" \
    --label "$TASK_LABELS")
  SUB_ISSUE=$(echo "$SUB_ISSUE_URL" | grep -oE '[0-9]+$')
else
  SUB_ISSUE_URL=$(gh sub-issue create --parent ${MAIN_ISSUE} \
    --repo <owner/repo> \
    --title "[T-001] <task.title>" \
    --body "<formatted body>")
  SUB_ISSUE=$(echo "$SUB_ISSUE_URL" | grep -oE '[0-9]+$')
fi
```

**If `issue_mode: linked_issues`**:
Use regular `gh issue create` and manually reference the parent issue in the body:

**Important**: Extract issue number using `grep` and `tr` (do NOT use `--json` flag).

```bash
# Body includes reference to parent issue
BODY="**Parent Issue**: #${MAIN_ISSUE}

<formatted body>"

# Extract issue number from output using grep and tr (compatible with all gh versions)
if [ -n "$TASK_LABELS" ]; then
  SUB_ISSUE=$(gh issue create \
    --repo <owner/repo> \
    --title "[T-001] <task.title>" \
    --body "$BODY" \
    --label "$TASK_LABELS" | grep -oE '#[0-9]+' | tr -d '#')
else
  SUB_ISSUE=$(gh issue create \
    --repo <owner/repo> \
    --title "[T-001] <task.title>" \
    --body "$BODY" | grep -oE '#[0-9]+' | tr -d '#')
fi
```

Collect the returned issue number and URL for each task.

### Step 5A: Finalize and Collect Results (GitHub Mode)

**If `issue_mode: single_issue`**:
- All tasks are already included in the single issue as checkboxes
- No additional updates needed
- Create a summary for console output showing the single issue URL

**If `issue_mode: sub_issues`**:
- The `gh sub-issue` extension automatically creates a proper parent-child relationship
- The task checklist is automatically maintained in the parent issue by GitHub's sub-issue feature
- No manual update needed

**If `issue_mode: linked_issues`**:
- Update the main issue body to include a task checklist with links to child issues
- Create a mapping table of task ID → issue number/URL and main issue for the console output

---

## Additional Resources

For detailed implementation guides on each export mode, refer to:
- **GitHub Issues**: `.sdp/docs/export-github.md`
- **Jira Issues**: `.sdp/docs/export-jira.md`
- **Backlog Issues**: `.sdp/docs/export-backlog.md`
- **Local Files**: `.sdp/docs/export-local.md`

These files contain complete API reference, template formats, error handling, and manual import instructions.

---

## Allowed Tools
Read, Write, Terminal, File Search, Grep