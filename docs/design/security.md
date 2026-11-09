# Security

## Baseline (P0.5)

Four layers, each catching something the others can't.

```mermaid
flowchart LR
    A["You type code"] --> B["ruff S rules<br/>pre-commit + CI"]
    B -->|"insecure code patterns"| C["git push"]
    C --> D["Secret scanning<br/>push protection"]
    D -->|"leaked tokens blocked"| E["CI: pip-audit job"]
    E -->|"known CVEs in locked deps"| F["main"]
    G["Dependabot<br/>weekly"] -->|"update PRs for deps + actions"| E
    H["Weekly scheduled CI"] -->|"new CVEs in old deps"| E
```

| Layer | Catches | Runs |
|---|---|---|
| ruff `S` (bandit) | Insecure patterns in our code | pre-commit + CI |
| CodeQL (default setup) | Deeper flaws, e.g. untrusted input reaching a dangerous call across functions; scans Python, Actions and TypeScript | every PR + push to main |
| pip-audit | Known CVEs in locked deps (incl. dev tools) | every PR + weekly |
| Dependabot malware alerts | Known-malicious packages (e.g. typosquats) | continuously |
| `pnpm audit --prod` | Known CVEs in the npm packages that ship to the browser | every PR |
| Dependabot | Outdated Python deps, npm deps (7-day cooldown) and GitHub Actions. TypeScript's minor/major and `@types/node`'s major are ignored, security updates included: [frontend.md](frontend.md#decisions), decisions 1 and 12 | weekly PRs |
| Secret scanning + push protection | Leaked tokens | every push |
| `permissions: contents: read` | CI token can't write to the repo | always |

`assert` is allowed only in tests (S101): `python -O` strips asserts, so shipped code
validates with exceptions.

The weekly scheduled run matters because a CVE can be published against a dependency
that hasn't changed; without it, nothing would notice until the next PR.

## Threat model

Starts in P4.7, when the API adds attack surface.
