"""Validate this package offline without an external skill validator."""
from pathlib import Path
import ast
import json
import re


def validate():
    skill = Path(__file__).resolve().parents[1]
    package = skill.parents[2]
    errors = []
    entry = skill / "SKILL.md"
    raw = entry.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("SKILL.md must not have a BOM")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        errors.append("Missing YAML frontmatter")
    else:
        front = text.split("---", 2)[1]
        if not re.search(r"(?m)^name: mathorcup-modeling$", front):
            errors.append("Unexpected skill name")
        if not re.search(r"(?m)^description: \S.+", front):
            errors.append("Missing skill description")
    required = ["AGENTS.md", "使用说明.md", "Agent环境配置指南.md", "启动检查.ps1", "快速检查.py", "requirements.txt",
                ".vscode/settings.json", ".vscode/extensions.json",
                ".agents/skills/mathorcup-modeling/agents/openai.yaml",
                ".agents/skills/mathorcup-modeling/scripts/figure_tools.py",
                ".agents/skills/mathorcup-modeling/scripts/baseline_models.py",
                ".agents/skills/mathorcup-modeling/references/baselines.md", "THIRD_PARTY_NOTICES.txt"]
    errors.extend(f"Missing: {name}" for name in required if not (package / name).is_file())
    for name in ("settings.json", "extensions.json"):
        try:
            json.loads((package / ".vscode" / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            errors.append(f"Invalid VS Code configuration: {name}: {exc}")
    for doc in [entry, package / "Agent环境配置指南.md", *sorted((skill / "references").rglob("*.md"))]:
        data = doc.read_bytes()
        if doc != entry and not data.startswith(b"\xef\xbb\xbf"):
            errors.append(f"Chinese Markdown needs BOM: {doc.name}")
        for link in re.findall(r"\]\(([^)]+)\)", data.decode("utf-8-sig")):
            if "://" in link or link.startswith("#"):
                continue
            target = (doc.parent / link.split("#", 1)[0]).resolve()
            if not target.is_relative_to(package) or not target.exists():
                errors.append(f"Broken or external local link in {doc.name}: {link}")
    for source in skill.rglob("*.py"):
        try:
            ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except SyntaxError as exc:
            errors.append(str(exc))
    return {"ok": not errors, "errors": errors, "skill": "mathorcup-modeling",
            "entry_lines": len(text.splitlines()), "entry_utf8_bytes": len(raw),
            "scope": "Package structure, relative references and Python syntax; not model behavior."}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
