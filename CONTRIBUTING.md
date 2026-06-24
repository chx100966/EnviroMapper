# Contributing to EnviroMapper

## Branch strategy

```
main              ← production-ready, protected
└── develop       ← integration branch, all features merge here first
    ├── feature/backend/<description>
    ├── feature/frontend/<description>
    ├── feature/ai/<description>
    ├── feature/infra/<description>
    └── fix/<module>/<description>
```

- Never commit directly to `main` or `develop`.
- Branch off `develop`, open a PR back to `develop`.
- `develop` is merged to `main` at each project milestone.
- At least **1 approval** required before merging any PR.

---

## Commit message convention

We follow [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, missing semicolons — no logic change |
| `refactor` | Code restructuring — no feature or fix |
| `test` | Adding or fixing tests |
| `chore` | Build process, dependencies, CI config |
| `infra` | Azure / IaC changes |

### Scopes

`backend` · `frontend` · `ai` · `infra` · `iot` · `db` · `auth` · `docs`

### Examples

```
feat(backend): add device registration endpoint
fix(ai): correct anomaly threshold for agriculture mode
chore(frontend): upgrade React to v19
infra: add CosmosDB Bicep module
docs: update quick start instructions
```

---

## Pull Request checklist

- [ ] Branch name follows the convention above
- [ ] All commits follow Conventional Commits
- [ ] Tests added / updated where applicable
- [ ] No secrets or credentials committed
- [ ] PR description explains **what** and **why**
- [ ] Linked to the relevant task / issue

---

## Code style

| Layer | Formatter / Linter |
|-------|--------------------|
| Backend (C#) | `dotnet format` (EditorConfig) |
| Frontend (JS/TS) | ESLint + Prettier |
| AI (Python) | Black + Ruff |

Run formatters before opening a PR.
