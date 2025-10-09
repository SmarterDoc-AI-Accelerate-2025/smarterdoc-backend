# scripts/print_clean_tree.py
# Usage:  pip install pathspec
#         python scripts/print_clean_tree.py > PROJECT_TREE_OVERVIEW.txt

from pathlib import Path
import pathspec

ROOT = Path(".").resolve()

# Load .gitignore (if present)
gitignore_lines = []
gi = ROOT / ".gitignore"
if gi.exists():
    gitignore_lines = gi.read_text().splitlines()

# Extra ignores (covers your noisy output)
extra_ignores = [
    # virtualenvs & caches
    "venv/",
    "myenv/",
    ".myenv/"
    "myenv",
    ".venv/",
    "**/site-packages/**",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".cache/",
    ".ipynb_checkpoints/",
    # build/packaging
    "dist/",
    "build/",
    "*.egg-info/",
    "*.dist-info/",
    ".tox/",
    # misc noise
    ".DS_Store",
    "coverage*",
    "*.log",
    "logs/",
    "*.gz",
    # data dumps you don’t want in overview (optional)
    "data/raw/**",
    "npi_tools/temp.gz",
    # editor/IDE
    ".idea/",
    ".vscode/",
    ".myenv/*"
]

spec = pathspec.PathSpec.from_lines("gitwildmatch",
                                    gitignore_lines + extra_ignores)

# Keep only the interesting parts for a FastAPI overview
ALLOW_DIRS = {"app", "npi_tools", "data", ".github", "tests"}
ALLOW_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "README.md",
    ".env.example",
    ".env.template",
    "mypy.ini",
    "ruff.toml",
    "pytest.ini",
    "conftest.py",
    "Makefile",
}


def allowed(p: Path) -> bool:
    if p.is_dir():
        return p.name in ALLOW_DIRS
    return p.name in ALLOW_FILES or p.suffix == ".py"


def keep(p: Path) -> bool:
    rel = str(p.relative_to(ROOT))
    if spec.match_file(rel):
        return False
    if allowed(p):
        return True
    # Keep a directory if it contains any allowed descendant
    if p.is_dir():
        try:
            return any(keep(c) for c in p.iterdir())
        except PermissionError:
            return False
    return False


def walk(d: Path, prefix=""):
    kids = [p for p in d.iterdir() if keep(p)]
    kids.sort(key=lambda p: (p.is_file(), p.name.lower()))
    for i, p in enumerate(kids):
        elbow = "└── " if i == len(kids) - 1 else "├── "
        print(prefix + elbow + p.name)
        if p.is_dir():
            ext = "    " if i == len(kids) - 1 else "│   "
            walk(p, prefix + ext)


print(ROOT.name)
walk(ROOT)
