#!/usr/bin/env python3
"""university-history-page 自测：6 个案例 + 8 条不变量。

改 render.py / build-data.py 后必须跑这个，退出码 0 才算通过。

覆盖的真实数据缺陷（每一条都对应一次实际踩坑）：
  1. 校长维度没有 year 字段，取 year 会满屏"年份不详"
  2. 学科评估只有"第 N 轮"，没有年份，不能编造
  3. 校长同一任期在源数据里重复 2-3 条（整体重复率 41.5%）
  4. 现任者逐年补记录，同一人同职务出现多次（2023/2024/2025）
  5. year_end=9999 是"至今在任"哨兵，直接渲染会显示 9999 年
  6. 学位点 level 大量是"待补充"，不能当成硕士/博士
  7. 页面必须完全自包含，不能有任何外链
  8. 非精选学校必须明确降级说明，不能假装有数据
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
RENDER = HERE / "render.py"

CASES: list[tuple[str, bool]] = []
INVARIANTS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    (CASES if name.startswith("case:") else INVARIANTS).append((name, ok))
    mark = "[ ok ]" if ok else "[FAIL]"
    print(f"{mark} {name}{('  ' + detail) if detail else ''}")
    return ok


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RENDER), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def load_featured() -> dict:
    f: dict = {}
    for p in sorted(DATA.glob("featured-*.json")):
        f.update(json.loads(p.read_text(encoding="utf-8")))
    return f


def main() -> int:
    if not DATA.exists():
        print("[error] 数据目录不存在，先跑 scripts/build-data.py", file=sys.stderr)
        return 1
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    featured = load_featured()
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    # ---------------- 案例 ----------------
    # case 1：精选学校能渲染，且 HTML 非空
    r = run("--uid", "ahu", "--stdout")
    html = r.stdout
    check("case:精选学校渲染出 HTML", r.returncode == 0 and len(html) > 20000,
          f"{len(html)} 字节")

    # case 2：按中文名可解析（不是只认 uid）
    r2 = run("--name", "安徽大学", "--stdout")
    check("case:按中文校名解析", r2.returncode == 0 and "安徽大学" in r2.stdout)

    # case 3：非精选学校走降级分支，仍出页面
    r3 = run("--uid", "sch_37424", "--stdout")
    check("case:非精选学校出降级页",
          r3.returncode == 0 and "已收录于全量索引" in r3.stdout)

    # case 4：不存在的学校给出候选而不是崩
    r4 = run("--name", "不存在的大学", "--stdout")
    check("case:查无此校给候选", "未找到" in r4.stdout)

    # case 5：--json 摘要可解析
    r5 = run("--uid", "pku", "--json")
    try:
        summary = json.loads(r5.stdout)
        ok5 = summary["uid"] == "pku" and summary["featured"] is True and summary["dims"]
    except (json.JSONDecodeError, KeyError):
        ok5 = False
    check("case:--json 摘要合法", ok5)

    # case 6：--list 按省列出
    r6 = run("--list", "安徽")
    check("case:--list 按省列出", r6.returncode == 0 and "共" in r6.stdout and "★" in r6.stdout)

    # ---------------- 不变量 ----------------
    # inv 1：页面完全自包含，没有任何外链资源
    externals = re.findall(r'(?:src|href)\s*=\s*["\'](?!\#)([^"\']+)', html)
    check("inv:页面无外链资源", not externals, f"发现 {externals[:3]}" if externals else "0 个")
    check("inv:页面无 http 引用", html.count("http") == 0,
          f"出现 {html.count('http')} 次")
    check("inv:页面无外部字体", "@import" not in html and "font-face" not in html)

    # inv 2：校长维度不得整块"年份不详"（曾因取错字段全屏都是）
    pres = featured["ahu"]["dims"]["president"]
    with_year = [x for x in pres if x.get("year_start")]
    check("inv:校长维度年份可用",
          len(with_year) >= max(1, int(len(pres) * 0.8)),
          f"{len(with_year)}/{len(pres)} 有起始年")

    # inv 3：渲染出的校长区不能满屏"年份不详"
    seg = html.split('id="dim-president"')
    if len(seg) > 1:
        chunk = seg[1].split("</section>")[0]
        n_bad = chunk.count("年份不详")
        check("inv:校长区无满屏年份不详", n_bad <= 1, f"{n_bad} 处")
    else:
        check("inv:校长区无满屏年份不详", False, "未找到校长区块")

    # inv 4：学科评估左列显示轮次而非"年份不详"
    seg = html.split('id="dim-evaluation"')
    if len(seg) > 1:
        chunk = seg[1].split("</section>")[0]
        check("inv:学科评估显示轮次",
              "第四轮" in chunk and chunk.count("年份不详") == 0,
              f"年份不详 {chunk.count('年份不详')} 处")
    else:
        check("inv:学科评估显示轮次", False, "未找到评估区块")

    # inv 5：校长数据无重复（同人同任期只能一条）
    dup_total = 0
    for _uid, v in featured.items():
        rows = (v.get("dims") or {}).get("president") or []
        keys = {(x.get("person_name"), x.get("year_start"), x.get("year_end"), x.get("title"))
                for x in rows}
        dup_total += len(rows) - len(keys)
    check("inv:校长数据无重复", dup_total == 0, f"重复 {dup_total} 条")

    # inv 6：同人同职务不得有多段"在任"
    multi = 0
    for _uid, v in featured.items():
        rows = (v.get("dims") or {}).get("president") or []
        seen: dict = {}
        for x in rows:
            if not x.get("year_end"):
                k = (x.get("person_name"), x.get("title"))
                seen[k] = seen.get(k, 0) + 1
        multi += sum(1 for n in seen.values() if n > 1)
    check("inv:同人同职务无多段在任", multi == 0, f"{multi} 例")

    # inv 7：9999 哨兵不得出现在任何数据里
    raw = "".join(p.read_text(encoding="utf-8") for p in DATA.glob("*.json"))
    check("inv:无 9999 哨兵年份", "9999" not in raw)

    # inv 8：学位点"待补充"不得被渲染成硕士/博士
    seg = html.split('id="dim-degree"')
    if len(seg) > 1:
        chunk = seg[1].split("</section>")[0]
        check("inv:学位层次如实标注",
              "层次待补充" in chunk and "博士" not in chunk and "硕士" not in chunk)
    else:
        check("inv:学位层次如实标注", False, "未找到学位点区块")

    # 汇总
    print()
    bad = [n for n, ok in CASES + INVARIANTS if not ok]
    if bad:
        print(f"[selftest] FAIL：{len(bad)} 项未通过 -> {', '.join(bad)}")
        return 1
    print(f"[selftest] OK：{len(CASES)} 个案例 + {len(INVARIANTS)} 条不变量全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
