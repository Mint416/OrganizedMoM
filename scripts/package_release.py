"""Create a reviewable release using explicit source/artifact allowlists."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("organized_mom", "web", "docs", "tests", "data", "scripts", ".github")
ROOT_FILES = (
    "README.md",
    "PROJECT_PLAN.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "start.command",
    "requirements-tested.txt",
)
ARTIFACT_FILES = (
    "evaluation.json",
    "end-to-end-trace.json",
    "test-results.txt",
    "browser-results.json",
    "mcp-results.json",
    "organized-mom-demo.mp4",
    "organized-mom-demo.srt",
    "video-manifest.json",
)


def main():
    files = []
    for folder in SOURCE_DIRS:
        files.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and p.suffix not in (".pyc", ".pyo")
        )
    files.extend(ROOT / p for p in ROOT_FILES if (ROOT / p).exists())
    files.extend(ROOT / "artifacts" / p for p in ARTIFACT_FILES if (ROOT / "artifacts" / p).exists())
    files.extend((ROOT / "artifacts/screenshots").glob("*.png"))
    manifest = []
    target = ROOT.parent / "organized-mom-github-ready.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            relative = path.relative_to(ROOT)
            if any(part in ("secrets", "runtime", ".venv", "private") for part in relative.parts):
                raise ValueError(f"Private directory reached packaging allowlist: {relative}")
            archive.write(path, Path("organized-mom") / relative)
            manifest.append(
                {
                    "path": str(relative),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        archive.writestr("organized-mom/artifacts/release-manifest.json", json.dumps(manifest, indent=2))
    (ROOT / "artifacts/release-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"archive": str(target), "files": len(files), "bytes": target.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
