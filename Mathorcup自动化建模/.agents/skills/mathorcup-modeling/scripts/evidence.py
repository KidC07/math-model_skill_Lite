"""File identity snapshots, not claims of mathematical correctness. Stdlib only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def inside(root, relative):
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError(f"Expected a project-relative path: {relative}")
    target = (root / value).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"Path escapes project root: {relative}")
    return target


def fingerprint(path):
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed during hashing: {path}")
    return {"bytes": after.st_size, "sha256": digest.hexdigest()}


def snapshot(root, files, output, command=""):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project root must be a directory")
    destination = inside(root, output)
    sources = list(dict.fromkeys(inside(root, name) for name in files))
    if not sources or destination in sources:
        raise ValueError("Choose source files; output cannot be one of the sources")
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    entries = [{"path": p.relative_to(root).as_posix(), **fingerprint(p)} for p in sources]
    result = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "reproduce_command": command, "files": entries,
              "scope": "File identity only; numerical correctness must be independently checked."}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


def verify(root, manifest):
    root = Path(root).resolve(strict=True)
    record = json.loads(inside(root, manifest).read_text(encoding="utf-8-sig"))
    if record.get("schema") != 1 or not isinstance(record.get("files"), list) or not record["files"]:
        raise ValueError("Unsupported or empty evidence manifest")
    checks = []
    seen = set()
    for entry in record["files"]:
        if not isinstance(entry, dict) or not {"path", "sha256", "bytes"} <= entry.keys():
            raise ValueError("Malformed manifest entry")
        path = inside(root, entry["path"])
        if path in seen:
            raise ValueError("Duplicate path in manifest")
        seen.add(path)
        try:
            actual = fingerprint(path)
            ok = all(actual[key] == entry[key] for key in ("sha256", "bytes"))
            checks.append({"path": entry["path"], "ok": ok, "status": "unchanged" if ok else "changed"})
        except (ValueError, OSError) as exc:
            checks.append({"path": entry["path"], "ok": False, "status": str(exc)})
    return {"ok": all(item["ok"] for item in checks), "checks": checks,
            "note": "Unchanged files do not prove a model or result is correct."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("snapshot")
    create.add_argument("--root", required=True)
    create.add_argument("--files", nargs="+", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--command", default="")
    check = sub.add_parser("verify")
    check.add_argument("--root", required=True)
    check.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        result = snapshot(args.root, args.files, args.output, args.command) if args.action == "snapshot" else verify(args.root, args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
