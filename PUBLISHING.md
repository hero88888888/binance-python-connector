# Publishing Guide

End-to-end guide to get binance-book on PyPI, GitHub, and docs live.

---

## Step 1: Create GitHub Repository

```bash
cd /Users/jae/binance-python-connector

# Initialize git
git init
git add .
git commit -m "Initial release: binance-book v0.1.0"

# Create repo on GitHub (use GitHub CLI or web UI)
# Option A: GitHub CLI
gh repo create binance-book --public --source=. --push

# Option B: Manual
# 1. Go to github.com → New Repository → name: "binance-book" → Public → Create
# 2. Then:
git remote add origin https://github.com/YOUR_USERNAME/binance-book.git
git branch -M main
git push -u origin main
```

**After push:** Update all URLs in `README.md`, `mkdocs.yml`, and `pyproject.toml` to use your actual GitHub username instead of `jae`.

---

## Step 2: Enable GitHub Pages (for docs)

1. Go to your repo → **Settings** → **Pages**
2. Under "Build and deployment", set Source to **GitHub Actions**
3. The `.github/workflows/docs.yml` will auto-deploy on push to `main`
4. Your docs will be live at `https://YOUR_USERNAME.github.io/binance-book/`

---

## Step 3: Publish to PyPI

### First time: Create PyPI account

1. Go to [pypi.org](https://pypi.org) → Register
2. Go to Account Settings → API tokens → Add API token (scope: entire account)
3. Save the token

### Build and publish

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# This creates:
#   dist/binance_book-0.1.0.tar.gz
#   dist/binance_book-0.1.0-py3-none-any.whl

# Upload to PyPI
twine upload dist/*
# Enter: __token__ as username, paste your API token as password

# Verify it's live
pip install binance-book
```

### Alternative: Using uv

```bash
uv build
uv publish --token YOUR_PYPI_TOKEN
```

---

## Step 4: Update Lovable Landing Page

Add these links/sections to your Lovable website:

### Install command (with copy button)
```
pip install binance-book
```

### Key links
- **PyPI:** `https://pypi.org/project/binance-book/`
- **GitHub:** `https://github.com/YOUR_USERNAME/binance-book`
- **Documentation:** `https://YOUR_USERNAME.github.io/binance-book/`

### Suggested landing page sections

1. **Hero:** "binance-book — Binance orderbook data for AI agents"
2. **Install:** `pip install binance-book` with copy button
3. **Quick code example** (copy from README Quick Start)
4. **Features grid** (typed schemas, 3 orderbook formats, AI tools, data cleaning, etc.)
5. **For AI Agents** section with OpenAI/Anthropic code snippets
6. **Links:** GitHub | PyPI | Docs | Examples

---

## Step 5: Verify Everything Works

```bash
# In a fresh environment:
pip install binance-book

python -c "
from binance_book import BinanceBook
book = BinanceBook()
print(book.ob_snapshot_wide('BTCUSDT', max_levels=3))
print(book.tools(format='openai')[0])
print('SUCCESS')
"
```

---

## Version Bumping (for future releases)

1. Update version in `pyproject.toml`
2. Update `binance_book/__init__.py`
3. Commit + push + tag: `git tag v0.2.0 && git push --tags`
4. Build + publish: `python -m build && twine upload dist/*`

---

## Directory Structure Summary

```
binance-book/
├── .github/workflows/docs.yml    # Auto-deploys docs to GitHub Pages
├── binance_book/                  # Python package (40+ files)
├── docs/                          # MkDocs documentation source
│   ├── index.md                   # Home page
│   ├── getting-started.md         # Installation + config
│   ├── api-reference.md           # Complete API docs
│   ├── examples.md                # Real-world usage patterns
│   └── data-quality.md            # Data issues + filters
├── mkdocs.yml                     # MkDocs configuration
├── pyproject.toml                 # Package metadata + deps
├── README.md                      # PyPI/GitHub landing page
├── LICENSE                        # MIT License
├── PUBLISHING.md                  # This file
└── .gitignore
```
