#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec-kit 上下文脚本（Spec Kit context resolver）.

替代上游 `.specify/scripts/{bash,powershell,python}/check-prerequisites.*`、
`create-new-feature.*`、`setup-plan.*`、`setup-tasks.*`、`resolve-template.*`。
只用标准库，Python 3.6+，Windows / macOS / Linux 同一份。

上游命令里出现 `{SCRIPT}` 的位置，已替换为（`<skill-dir>` 指本技能所在目录）：

    python "<skill-dir>/scripts/speckit_context.py" --json

输出：单个 JSON 对象（字段名与上游一致，大写键）。

常用调用
--------
    # 1) 只读上下文（plan/tasks/implement/analyze 等的第 1 步）
    python speckit_context.py --json

    # 2) 新建 feature 目录并一次铺全套文档骨架
    #    stories.md（用户故事）+ acceptance.md（验收卡）+ spec.md
    python speckit_context.py --json --create user-auth

    # 3) 单独补某个阶段的骨架
    python speckit_context.py --json --setup story     # stories.md
    python speckit_context.py --json --setup accept    # acceptance.md
    python speckit_context.py --json --setup plan      # plan.md
    python speckit_context.py --json --setup tasks     # tasks.md

    # 4) 附带某张模板全文（checklist、constitution 阶段）
    python speckit_context.py --json --template checklist-template

    # 5) 精简输出（不含文档列表与模板正文）
    python speckit_context.py --json --paths-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TEMPLATE_NAMES = (
    "spec-template",
    "plan-template",
    "tasks-template",
    "checklist-template",
    "constitution-template",
    "user-story-template",
    "acceptance-card-template",
    "impact-template",
)

# --setup <stage>  ->  (模板名, 目标文件名)
SETUP_MAP = {
    "plan": ("plan-template", "plan.md"),
    "tasks": ("tasks-template", "tasks.md"),
    "story": ("user-story-template", "stories.md"),
    "impact": ("impact-template", "impact.md"),
    "accept": ("acceptance-card-template", "acceptance.md"),
}

# 模板目录：<skill>/references/templates
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "references" / "templates"


def out(payload: dict) -> None:
    """写 UTF-8 JSON 到 stdout。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
    except Exception:
        pass
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.write(text + "\n")


def find_repo_root(start: Path | None = None) -> Path:
    """git 根；不是 git 仓库时退回当前目录。"""
    start = Path(start or Path.cwd()).resolve()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if proc.returncode == 0:
            root = proc.stdout.decode("utf-8", "replace").strip()
            if root:
                return Path(root).resolve()
    except Exception:
        pass
    # 退化：向上找 .git
    cur = start
    for _ in range(8):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start


def git_branch(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if proc.returncode == 0:
            name = proc.stdout.decode("utf-8", "replace").strip()
            return name or None
    except Exception:
        pass
    return None


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "feature"


def next_number(specs_dir: Path) -> int:
    highest = 0
    if specs_dir.is_dir():
        for entry in specs_dir.iterdir():
            if not entry.is_dir():
                continue
            m = re.match(r"^(\d{3})", entry.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def latest_feature(specs_dir: Path) -> Path | None:
    if not specs_dir.is_dir():
        return None
    candidates = []
    for entry in specs_dir.iterdir():
        if entry.is_dir() and re.match(r"^\d{3}", entry.name):
            candidates.append(entry)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.name)[-1].resolve()


def read_feature_json(root: Path) -> Path | None:
    f = root / ".specify" / "feature.json"
    if not f.is_file():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    raw = data.get("feature_directory")
    if not raw:
        return None
    p = Path(raw)
    return (p if p.is_absolute() else (root / p)).resolve()


def write_feature_json(root: Path, feature_dir: Path) -> None:
    target = root / ".specify" / "feature.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(str(feature_dir), str(root)).replace("\\", "/")
    target.write_text(
        json.dumps({"feature_directory": rel}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def template_path(name: str) -> Path | None:
    if not name:
        return None
    stem = name[:-3] if name.endswith(".md") else name
    if stem not in TEMPLATE_NAMES:
        return None
    p = TEMPLATES_DIR / (stem + ".md")
    return p if p.is_file() else None


def copy_template(name: str, dest: Path) -> bool:
    src = template_path(name)
    if src is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def available_docs(feature_dir: Path | None) -> list:
    if feature_dir is None or not feature_dir.is_dir():
        return []
    docs = []
    for entry in sorted(feature_dir.iterdir(), key=lambda p: p.name):
        if entry.is_dir():
            docs.append(entry.name + "/")
        elif entry.suffix in (".md", ".json", ".yaml", ".yml", ".txt"):
            docs.append(entry.name)
    return docs


def checklist_status(feature_dir: Path | None) -> list:
    if feature_dir is None:
        return []
    cl_dir = feature_dir / "checklists"
    if not cl_dir.is_dir():
        return []
    result = []
    for f in sorted(cl_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        total = len(re.findall(r"^\s*-\s*\[[ xX]\]", text, flags=re.M))
        done = len(re.findall(r"^\s*-\s*\[[xX]\]", text, flags=re.M))
        result.append(
            {
                "file": f.name,
                "total": total,
                "checked": done,
                "unchecked": total - done,
                "status": "PASS" if total - done == 0 else "FAIL",
            }
        )
    return result


def doc_status(feature_dir: Path | None, filename: str, heading: str) -> dict | None:
    """统计某个文档的条目/勾选情况。heading 为 'RAC' 或 'U'。"""
    if feature_dir is None:
        return None
    f = feature_dir / filename
    if not f.is_file():
        return None
    text = f.read_text(encoding="utf-8", errors="replace")
    items = len(re.findall(r"(?m)^\s*-\s*\[[ xX]\]", text))
    done = len(re.findall(r"(?m)^\s*-\s*\[[xX]\]", text))
    return {
        "file": filename,
        "entries": len(re.findall(r"(?m)^#{2,4}\s*" + heading + r"-?\d+", text)),
        "items": items,
        "checked": done,
        "unchecked": items - done,
    }


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--repo", default=None, help="项目根（默认 git 根或当前目录）")
    ap.add_argument("--json", "-Json", action="store_true", help="输出 JSON（默认行为）")
    ap.add_argument("--paths-only", "--paths_only", "-PathsOnly", action="store_true")
    ap.add_argument("--feature", default=None, help="显式指定 feature 目录")
    ap.add_argument("--create", default=None, metavar="SLUG", help="新建 specs/NNN-<slug>")
    ap.add_argument(
        "--setup",
        default=None,
        choices=["story", "accept", "plan", "tasks"],
        help="铺对应阶段的文档骨架（stories/acceptance/plan/tasks）",
    )
    ap.add_argument("--template", "-Template", default=None, help="附带模板全文")
    ap.add_argument("--checklists", action="store_true", help="附带 checklist 状态")
    args = ap.parse_args(argv)

    root = find_repo_root(Path(args.repo) if args.repo else None)
    specs_dir = root / "specs"

    feature_dir = None
    if args.create:
        num = next_number(specs_dir)
        feature_dir = (specs_dir / ("%03d-%s" % (num, slugify(args.create)))).resolve()
        feature_dir.mkdir(parents=True, exist_ok=True)
        # 全套文档骨架：场景 → 影响面 → 验收卡 → 规格（plan/tasks 由各自阶段铺）
        for tpl, dest in (
            ("user-story-template", "stories.md"),
            ("impact-template", "impact.md"),
            ("acceptance-card-template", "acceptance.md"),
            ("spec-template", "spec.md"),
        ):
            copy_template(tpl, feature_dir / dest)
        write_feature_json(root, feature_dir)
    if feature_dir is None and args.feature:
        p = Path(args.feature)
        feature_dir = (p if p.is_absolute() else (root / p)).resolve()
    if feature_dir is None:
        feature_dir = read_feature_json(root)
    if feature_dir is None:
        feature_dir = latest_feature(specs_dir)

    if args.setup in SETUP_MAP and feature_dir is not None:
        tpl, dest = SETUP_MAP[args.setup]
        copy_template(tpl, feature_dir / dest)
        write_feature_json(root, feature_dir)

    payload = {
        "REPO_ROOT": str(root),
        "BRANCH": git_branch(root),
        "SPECS_DIR": str(specs_dir),
        "FEATURE_DIR": str(feature_dir) if feature_dir else None,
        "STORIES": str(feature_dir / "stories.md") if feature_dir else None,
        "IMPACT": str(feature_dir / "impact.md") if feature_dir else None,
        "ACCEPTANCE": str(feature_dir / "acceptance.md") if feature_dir else None,
        "FEATURE_SPEC": str(feature_dir / "spec.md") if feature_dir else None,
        "IMPL_PLAN": str(feature_dir / "plan.md") if feature_dir else None,
        "TASKS": str(feature_dir / "tasks.md") if feature_dir else None,
        "CONSTITUTION": str(root / ".specify" / "memory" / "constitution.md"),
        "CONSTITUTION_EXISTS": (root / ".specify" / "memory" / "constitution.md").is_file(),
        "TEMPLATES_DIR": str(TEMPLATES_DIR),
        "EXTENSIONS_FILE": str(root / ".specify" / "extensions.yml"),
        "EXTENSIONS_EXISTS": (root / ".specify" / "extensions.yml").is_file(),
        "CREATED_DIR": bool(args.create),
    }
    if not args.paths_only:
        payload["AVAILABLE_DOCS"] = available_docs(feature_dir)
        payload["STORIES_STATUS"] = doc_status(feature_dir, "stories.md", "U")
        payload["ACCEPTANCE_STATUS"] = doc_status(feature_dir, "acceptance.md", "RAC")
        if args.checklists:
            payload["CHECKLISTS"] = checklist_status(feature_dir)
    if args.template:
        tp = template_path(args.template)
        payload["TEMPLATE"] = str(tp) if tp else None
        if tp and not args.paths_only:
            payload["TEMPLATE_PATH"] = str(tp)
            payload["TEMPLATE_CONTENT"] = tp.read_text(encoding="utf-8")
            if tp.stem == "tasks-template":
                payload["TASKS_TEMPLATE"] = str(tp)
                payload["TASKS_TEMPLATE_CONTENT"] = payload["TEMPLATE_CONTENT"]
            if tp.stem == "plan-template":
                payload["IMPL_PLAN_TEMPLATE"] = str(tp)

    out(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
