# Confab Templates

## Overview

When a confab is synced to GitHub, it is stored as a directory of structured files in the user's selected repository. Each confab gets its own branch and pull request, enabling review before merge.

---

## Directory Structure

```
confabs/
  {slug}/
    Confab.toml
    PURPOSE.md
    GUARDRAILS.md
    TESTS.md
```

**Slug derivation:** lowercase the confab name and replace spaces with hyphens.

---

## File Formats

### Confab.toml

Configuration metadata in TOML format:

```toml
[confab]
name = "{confab_name}"
description = "{description}"
version = "1.0.0"
created_at = "{ISO 8601 datetime}"

[metadata]
author = "Let's Confab"
license = "MIT"
```

### PURPOSE.md

Defines the confab's purpose, objectives, use cases, and expected behavior. Structured with these sections:

- **Purpose statement** — A paragraph describing what the confab is designed to do.
- **Primary Objectives** — Bullet list of goals.
- **Target Use Cases** — Scenarios where the confab excels.
- **Expected Behavior** — How the confab should respond in different situations.

### GUARDRAILS.md

Defines safety constraints and behavioral boundaries. Structured with these sections:

- **Safety Constraints** — Content the confab must not generate (harmful, illegal, unethical).
- **Behavioral Boundaries** — Scope limits, impersonation rules, communication standards.
- **Content Guidelines** — Accuracy, citation, and uncertainty acknowledgment requirements.
- **Error Handling** — How the confab should handle ambiguous or unclear requests.

### TESTS.md

Defines test scenarios as checklists. Structured with these sections:

- **Unit Tests** — Basic functionality and edge cases.
- **Integration Tests** — API connections, data flow, UI interactions.
- **Performance Tests** — Response time and resource usage under load.
- **Security Tests** — Input validation and access control.
- **Test Scenarios** — Happy path, error recovery, and complex query narratives.

---

## Branch and Pull Request Workflow

### Branch Naming

| Operation | Pattern |
|-----------|---------|
| Create | `confab-{slug}-{timestamp}` |
| Update | `update-confab-{slug}-{timestamp}` |

### Pull Request Format

| Field | Create | Update |
|-------|--------|--------|
| Title | `Add confab: {name}` | `Update confab: {name}` |
| Body | Description of the confab | Description of the confab |
| Base | Default branch | Default branch |
| Head | The newly created branch | The newly created branch |

### Workflow

1. Branch from the repository's default branch.
2. Commit all four confab files to the new branch.
3. Open a pull request targeting the default branch.
4. Store the PR URL on the confab record.

On update, a new branch and new PR are created (the old PR is not modified).

---

## Repository Initialization

When a user first sets up their GitHub integration, the system can create a new repository with:

- Auto-initialization (README)
- A standard gitignore template
- A test confab structure to verify the integration works
