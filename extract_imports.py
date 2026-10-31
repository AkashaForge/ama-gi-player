"""Разовый скрипт: вытащить все импорты и отфильтровать stdlib + internal."""
import ast
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path.cwd()

# Внутренние модули проекта (верхний уровень пакета)
INTERNAL = {
    "config", "controllers", "core", "database", "legal_gate",
    "legal_texts", "main", "search", "services", "tests", "tools", "ui",
}

# stdlib (Python 3.10+)
STDLIB = set(sys.stdlib_module_names)

# Собираем: top_module -> {(full_import, file)}
imports = defaultdict(set)

for py_file in ROOT.rglob("*.py"):
    parts = py_file.parts
    if ".venv" in parts or "venv" in parts or "__pycache__" in parts:
        continue
    if py_file.name == "extract_imports.py":
        continue
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except Exception as e:
        print(f"# SKIP {py_file}: {e}", file=sys.stderr)
        continue
    rel = str(py_file.relative_to(ROOT))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name
                top = full.split(".")[0]
                if top in INTERNAL or top in STDLIB:
                    continue
                imports[top].add((full, rel))
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # relative import
            if not node.module:
                continue
            full = node.module
            top = full.split(".")[0]
            if top in INTERNAL or top in STDLIB:
                continue
            imports[top].add((full, rel))

print("=" * 72)
print(f"THIRD-PARTY MODULES: {len(imports)}")
print("=" * 72)
for top in sorted(imports):
    full_imports = sorted({f for f, _ in imports[top]})
    files = sorted({file for _, file in imports[top]})
    print(f"\n### {top}")
    print(f"    imports: {', '.join(full_imports)}")
    print(f"    files:   {len(files)} (e.g. {files[0]})")
    if len(files) > 1:
        for f in files[1:4]:
            print(f"             {f}")
        if len(files) > 4:
            print(f"             ... и ещё {len(files) - 4}")
print()
