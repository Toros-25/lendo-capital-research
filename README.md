# Lendo Capital — Quant Research

Weekly quant research tasks: environment setup, data loading, return computation, and portfolio analytics.

## Environment setup

**Requirements:** Python 3.11+, `pip`

```bash
# 1. Clone the repo
git clone <repo-url>
cd lendo-capital-research

# 2. Create and activate a virtual environment (venv)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Install linter
pip install ruff

# 5. Verify the install
python - <<'EOF'
import pandas, numpy, matplotlib, scipy, jupyter
print("All core libraries imported successfully.")
EOF
```

## Running notebooks

```bash
jupyter notebook notebooks/
```

## Linting

```bash
ruff check .
```

## Testing

```bash
pytest
```

## Folder structure

```
.
├── data/
│   ├── raw/            # raw OHLCV files — gitignored, never commit
│   └── processed/      # cleaned/derived data — gitignored
├── notebooks/
│   └── week1/          # weekly exploration notebooks
├── src/                # importable research library
│   └── __init__.py
├── tests/              # pytest test suite
├── requirements.txt
├── pyproject.toml      # build config + ruff/pytest settings
├── CONTRIBUTING.md
└── README.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style, docstring conventions, and git workflow.
