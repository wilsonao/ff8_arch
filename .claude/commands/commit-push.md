---
description: Stage all changes, commit, and push to GitHub
allowed-tools: Bash(git *), PowerShell(git *)
---

Commit all pending changes and push them to GitHub.

Steps:
1. Run `git status` and `git diff` to see what changed.
2. Stage everything with `git add -A`.
3. Write a concise, descriptive commit message summarizing the actual changes (not just "update files"). If the user provided extra context after the command, use it: $ARGUMENTS
4. Commit the staged changes.
5. Push to the current branch's remote with `git push`. If no upstream is set, use `git push -u origin <current-branch>`. If no remote named `origin` exists, stop and tell the user they need to add a GitHub remote first (e.g. `git remote add origin <url>`).
6. Report the commit hash and confirm the push succeeded.
