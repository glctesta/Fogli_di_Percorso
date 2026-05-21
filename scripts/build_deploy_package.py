"""Build a clean deployment ZIP from git-tracked files.

Uso:
    python scripts\\build_deploy_package.py            # zip dalla HEAD corrente
    python scripts\\build_deploy_package.py v0.6.0-notifications  # zip da un tag

Output: dist/fdp-<version>.zip

Lo ZIP contiene tutti i file tracciati in git eccetto:
- tests/                    (non serve in produzione)
- docs/superpowers/         (planning interno)
- requirements-dev.txt      (solo dev)
- messages.pot              (sorgente i18n; le .mo sono incluse)
- babel.cfg                 (config Babel solo per dev)
- scripts/build_deploy_package.py  (questo file)

I file segreti (db_config.enc, email_*.key, ecc.) sono per design NON
tracciati in git, quindi non finiscono nello ZIP. L'operatore li configura
sul server target tramite `python scripts/configure_db.py`.
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent

_EXCLUDE_PREFIXES = (
    "tests/",
    "docs/superpowers/",
)

_EXCLUDE_EXACT = {
    "requirements-dev.txt",
    "messages.pot",
    "babel.cfg",
    "scripts/build_deploy_package.py",
    ".gitignore",
}


def _ls_files(treeish: str) -> list[str]:
    """Ritorna lista path relativi tracciati al treeish (HEAD o tag)."""
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", treeish],
        cwd=_REPO_ROOT, text=True, encoding="utf-8",
    )
    return [line for line in out.splitlines() if line]


def _should_include(path: str) -> bool:
    if path in _EXCLUDE_EXACT:
        return False
    for prefix in _EXCLUDE_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


def _resolve_version(treeish: str) -> str:
    """Ritorna una stringa version stampabile (tag o sha breve)."""
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match", treeish],
            cwd=_REPO_ROOT, text=True, encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", treeish],
            cwd=_REPO_ROOT, text=True, encoding="utf-8",
        ).strip()
        return f"dev-{sha}"


def build(treeish: str = "HEAD") -> Path:
    version = _resolve_version(treeish)
    dist_dir = _REPO_ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    out_zip = dist_dir / f"fdp-{version}.zip"

    files = _ls_files(treeish)
    included = [p for p in files if _should_include(p)]
    skipped = [p for p in files if not _should_include(p)]

    prefix = f"fdp-{version}/"
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in included:
            src = _REPO_ROOT / rel
            if not src.is_file():
                # symlink o dir vuota — ignora
                continue
            zf.write(src, prefix + rel)

    print(f"Build completata: {out_zip}")
    print(f"  Version: {version}")
    print(f"  File inclusi: {len(included)}")
    print(f"  File esclusi: {len(skipped)}")
    print(f"  Dimensione: {out_zip.stat().st_size / 1024:.1f} KB")
    return out_zip


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    treeish = argv[0] if argv else "HEAD"
    build(treeish)
    return 0


if __name__ == "__main__":
    sys.exit(main())
