# Development pipeline

```mermaid
flowchart TD
    A["You type code"] --> B["git commit"]
    B --> C{"pre-commit hooks<br/>local, ~seconds"}
    C -->|"ruff format, ruff check, mypy strict"| D{"All pass?"}
    D -->|"no"| E["Commit blocked:<br/>fix and retry"]
    E --> B
    D -->|"yes"| F["git push feature branch"]
    F --> G{"GitHub Actions CI<br/>clean Ubuntu VM"}
    G -->|"uv sync locked, ruff, mypy,<br/>pytest + coverage 85%+"| H{"CI green?"}
    H -->|"no"| I["Fix on the branch"]
    I --> B
    H -->|"yes"| J["Pull Request"]
    J --> K["Merge to main"]
```

**Why both stages:** pre-commit gives fast local feedback but can be skipped
and runs on my machine; CI runs on a clean VM from `uv.lock` and is the actual
gate. `main` only receives CI-green merges.
