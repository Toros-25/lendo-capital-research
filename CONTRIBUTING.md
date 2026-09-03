# Contributing

## Code style

- Follow **PEP 8**. Line length: 88 characters (enforced by `ruff`).
- Use **type hints** on every public function signature.
- Use **Google-style docstrings** on every public function.

Example:

```python
def load_ohlcv(path: str, ticker: str) -> pd.DataFrame:
    """Load raw OHLCV data from a CSV file.

    Args:
        path: Absolute or relative path to the CSV file.
        ticker: Ticker symbol used to label the data.

    Returns:
        DataFrame with a DatetimeIndex and columns
        [open, high, low, close, volume].

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
```

## Linting and formatting

We use **ruff** for linting and import sorting (configured in `pyproject.toml`).

```bash
pip install ruff
ruff check .          # lint
ruff check --fix .    # auto-fix safe issues
```

Run `ruff check .` before every commit. CI will block on lint failures.

## Git workflow

- **Branches:** cut feature branches off `main` — e.g. `feat/week2-data-loader`.
- **Commits:** imperative mood, present tense — "Add load_ohlcv function", not "Added…".
- **PRs:** open a PR for anything non-trivial (new modules, schema changes, new notebooks that others will depend on). One logical change per PR.
- **Merges:** squash-merge into `main` to keep history clean.

## Testing

- Tests live in `tests/`. Mirror the `src/` layout — `src/returns.py` → `tests/test_returns.py`.
- Run with `pytest` from the repo root.
- Every public function in `src/` should have at least one test.
