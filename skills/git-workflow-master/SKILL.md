---
name: git-workflow-master
description: "Git workflows: branching strategy, rebasing, conflict resolution, bisect, interactive rebase, cherry-pick. Use when: managing branches, resolving conflicts, investigating regressions, cleaning history."
version: 1.0.0
---

# Git Workflow Master

## Purpose

Expert Git operations: branching, rebasing, conflict resolution, history management.

## Branching Strategy

```
main ← production releases
  └── feature/xyz ← short-lived feature branches
  └── fix/issue-123 ← bug fixes
  └── copilot/task-name ← AI-generated branches
```

## Key Operations

### Rebase (prefer over merge for clean history)

```bash
git fetch origin
git rebase origin/main
# If conflicts:
git status  # See conflicts
# Fix files, then:
git add .
git rebase --continue
```

### Interactive Rebase (clean up commits before merge)

```bash
git rebase -i HEAD~5
# pick = keep, squash = combine with previous, drop = remove
# reword = change message, fixup = squash without message
```

### Bisect (find regression)

```bash
git bisect start
git bisect bad   # Current commit is bad
git bisect good v1.0  # Known good commit
# Git checks out middle commit — test and mark:
git bisect good  # or: git bisect bad
# Repeat until found, then:
git bisect reset
```

### Cherry-Pick (apply specific commit)

```bash
git cherry-pick abc1234  # Apply one commit
git cherry-pick abc1234..def5678  # Range
```

### Stash (save WIP without committing)

```bash
git stash push -m "WIP: feature X"
git stash list
git stash pop  # Apply and remove
```

## Conflict Resolution

1. Read BOTH sides of the conflict carefully
2. Check `git log --merge` for context
3. Use `git diff --name-only --diff-filter=U` to list conflicted files
4. Resolve minimally — preserve intent of both changes
5. Run tests after resolution

## Rules

1. NEVER force-push to shared branches without asking
2. NEVER rewrite published history
3. Keep commits atomic — one logical change per commit
4. Write descriptive commit messages: `type(scope): description`
5. Delete merged branches promptly
