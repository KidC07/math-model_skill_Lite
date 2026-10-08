"""Create a portable ZIP without caches, rendered previews or rejected diagnostics."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", "验证记录"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "Mathorcup自动化建模.zip")
    options = parser.parse_args()
    destination = options.output.resolve()
    if destination.is_relative_to(ROOT):
        parser.error("Place the archive outside the source folder")
    files = [p for p in sorted(ROOT.rglob("*")) if p.is_file()
             and not (set(p.relative_to(ROOT).parts) & SKIP_PARTS)
             and p.suffix not in {".aux", ".log", ".toc", ".out", ".pyc"}]
    entries = []
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        for path in files:
            name = (Path(ROOT.name) / path.relative_to(ROOT)).as_posix()
            data = path.read_bytes()
            archive.writestr(name, data)
            entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        archive.writestr(f"{ROOT.name}/交付文件指纹.json", json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8"))
    with ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Bad archive member: {bad}")
        expected = f"{ROOT.name}/.agents/skills/mathorcup-modeling/SKILL.md"
        if expected not in archive.namelist():
            raise RuntimeError("Missing hidden .agents skill entry")
        for entry in entries:
            if hashlib.sha256(archive.read(entry["path"])).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Hash mismatch: {entry['path']}")
    print(json.dumps({"archive": str(destination), "source_files": len(entries),
                      "bytes": destination.stat().st_size, "crc_and_hashes_valid": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
