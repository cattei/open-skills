#!/usr/bin/env python3
"""从 Project-UniversityHistory 原始数据生成技能随包数据。

产物（写入 ../data/）：
  index.json          全部 3016 所的轻索引（检索用，约 285 KB）
  featured-01..06.json 精选学校的全维度数据（渲染用，约 2.1 MB，6 分片）
  meta.json           生成元信息（来源标识、条数、生成时间、校验和）

真源位置不硬编码：用 --source 指定，或设 UH_SOURCE_DIR 环境变量。
发布到 skillhub 后本脚本只用于「重新生成」，日常渲染不需要它。

设计要点（为什么是两层）：
  - 索引层覆盖全部学校 → 用户查任何一所都能命中，不会"查无此校"；
  - 精选层只带头部学校全维度 → 包体可控，且真正的深度内容留在服务端，
    这是"渲染型 skill + 数据护城河"的形态验证。
  - 两层都用扁平短字段名，压掉 60% 体积。

用法：
    python scripts/build-data.py --source <项目 data 目录> [--out <输出目录>]
    python scripts/build-data.py --source ... --featured-top 300   # 扩到 Top300
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# 真源目录：不硬编码绝对路径。优先环境变量，其次在常见位置探测，都没有则由 --source 指定。
# 发布到 skillhub 后本脚本只用于「重新生成」，日常使用不需要它。
_CANDIDATES = [
    Path(os.environ.get("UH_SOURCE_DIR", "")) if os.environ.get("UH_SOURCE_DIR") else None,
    Path.cwd() / "Project-UniversityHistory" / "software" / "src" / "data",
    Path.cwd().parent / "Project-UniversityHistory" / "software" / "src" / "data",
    Path.home() / "open-project" / "Project-UniversityHistory" / "software" / "src" / "data",
]


def _detect_source() -> Path:
    for c in _CANDIDATES:
        if c and c.is_dir():
            return c
    return Path("Project-UniversityHistory/software/src/data")


DEFAULT_SOURCE = _detect_source()
OUT_DIR = Path(__file__).resolve().parent.parent / "data"

# 各维度保留字段（只留渲染要用的）
KEEP: dict[str, list[str]] = {
    "name": ["year", "relType", "name_old", "name_new", "description", "reason_type"],
    "location": ["year", "location", "location_type", "description"],
    "affiliation": ["year", "affiliation_old", "affiliation_new", "description"],
    "discipline": ["year", "action", "discipline_name", "description"],
    "evaluation": ["round", "rating", "discipline_name"],
    "president": ["person_name", "year_start", "year_end", "title", "is_acting", "description"],
    "policy": ["year", "policy_name", "impact_type", "impact_detail"],
    "college": ["name", "program_count", "point_count"],
    "degree": ["name", "level", "degree_type", "year_approved", "college_name"],
    "program": ["name", "college_name", "status"],
}
CAPS: dict[str, int] = {
    "name": 40, "location": 30, "affiliation": 30, "discipline": 40,
    "evaluation": 60, "president": 60, "policy": 60,
    "college": 60, "degree": 60, "program": 80,
}
# 维度 -> (源文件名, uid 字段候选)
# 注意：维度名与文件名不是一回事（name -> university-relations.json）。
DIM_SOURCES: dict[str, tuple[str, tuple[str, ...]]] = {
    "name": ("university-relations", ("from", "to")),
    "location": ("located-at", ("uid",)),
    "affiliation": ("affiliation-changed", ("uid",)),
    "discipline": ("discipline-event", ("uid",)),
    "evaluation": ("evaluated", ("uid",)),
    "president": ("presided-university", ("uni_uid",)),
    "policy": ("affected-by", ("uni_uid",)),
    "college": ("college-counts", ("uni_uid",)),
    "degree": ("degree-points", ("uni_uid",)),
    "program": ("programs", ("uni_uid",)),
}
# 索引层字段压缩：n=name p=province c=city l=level e=established
DIM_LABELS = {
    "name": "校名演变", "location": "校址变迁", "affiliation": "隶属变更",
    "discipline": "学科建设", "evaluation": "学科评估", "president": "校长更迭",
    "policy": "政策影响", "college": "学院设置", "degree": "学位点", "program": "专业",
}


def trim(v: Any, limit: int = 200) -> Any:
    if not isinstance(v, str):
        return v
    s = " ".join(v.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def as_year(v: Any) -> Optional[int]:
    """年份归一成 int。

    真实数据问题：presided-university.json 的 year_start 混着字符串
    （"1928"、"1928年4月"、空串），直接排序会抛 TypeError。
    """
    if v is None or v == "":
        return None
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip()[:4])
    except (ValueError, TypeError):
        return None


# 哨兵年份：源数据用 9999 表示"至今仍在任"，直接渲染会显示成 9999 年。
SENTINEL_YEAR = 9999


def clean_year(v: Any) -> Optional[int]:
    y = as_year(v)
    if y is None or y >= SENTINEL_YEAR:
        return None
    if y < 1000 or y > 2100:
        return None
    return y


def dedupe(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    """按给定字段去重，保留信息最全的一条。

    真实数据问题：presided-university.json 里同一任期有 2-3 条记录
    （title 写成 president / 校长，或描述有无差异），整体重复率 41.5%。
    不去重则校长列表会出现同一人同一任期重复多次。
    """
    best: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        if k in best:
            # 保留字段更多（信息更全）的那条
            if len(r) > len(best[k]):
                best[k] = r
        else:
            best[k] = r
    return list(best.values())


# 职务中英混写归一：源数据 title 同时出现 president / 校长 / party_secretary / 党委书记
TITLE_NORM = {
    "president": "校长",
    "party_secretary": "党委书记",
    "secretary": "党委书记",
    "vice_president": "副校长",
    "deputy": "副校长",
}


def norm_title(v: Any) -> str:
    if not v:
        return ""
    s = str(v).strip()
    return TITLE_NORM.get(s, s)


def merge_open_ended(rows: list[dict]) -> list[dict]:
    """合并同一人同一职务的"开放任期"记录。

    真实数据问题：源数据对现任者逐年补记录，孙长银作为"校长"留下
    2000 / 2023 / 2024 / 2025 四条，页面上会看到同一个人连刷四次。
    规则：
      1) 起始年相邻（<=3 年）的开放任期并成一条，取最早起始年；
      2) 同一人同一职务若仍有多个互不相邻的开放任期，只保留最新的那条
         —— 开放任期意味着"至今在任"，一个人不可能同时有两段在任任期，
         较早的那条是源数据的历史残留（如 2000 那条明显是错值）。
    有明确结束年的历史任期一律不受影响。
    """
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        by_key.setdefault((r.get("person_name"), r.get("title")), []).append(r)

    merged: list[dict] = []
    for _key, group in by_key.items():
        group = sorted(group, key=lambda x: as_year(x.get("year_start")) or 9999)
        # 先按相邻性把开放任期聚成若干簇
        clusters: list[list[dict]] = []
        cur: list[dict] = []
        for r in group:
            s = as_year(r.get("year_start"))
            e = as_year(r.get("year_end"))
            if e is not None:
                # 有结束年：独立成条，不参与合并
                if cur:
                    clusters.append(cur)
                    cur = []
                clusters.append([r])
                continue
            if cur:
                cs = as_year(cur[-1].get("year_start"))
                if cs is not None and s is not None and abs(s - cs) <= 3:
                    cur.append(r)
                    continue
                clusters.append(cur)
            cur = [r]
        if cur:
            clusters.append(cur)

        open_clusters = [c for c in clusters if c and as_year(c[0].get("year_end")) is None]
        # 只保留最新的开放任期簇，其余视为源数据残留
        keep_open = max(open_clusters, key=lambda c: as_year(c[-1].get("year_start")) or 0) \
            if open_clusters else None
        for c in clusters:
            if c is keep_open:
                rec = dict(c[0])
                rec["year_start"] = min(
                    (as_year(x.get("year_start")) for x in c
                     if as_year(x.get("year_start")) is not None), default=None)
                # 取信息最全的一条补充字段
                for x in c:
                    if len(x) > len(rec):
                        for k, v in x.items():
                            rec.setdefault(k, v)
                merged.append({k: v for k, v in rec.items() if v is not None})
            elif c and as_year(c[0].get("year_end")) is not None:
                merged.extend(c)
    return merged


def load_json(source: Path, name: str) -> list[dict]:
    p = source / f"{name}.json"
    if not p.exists():
        print(f"  [warn] 缺少 {name}.json，跳过", file=sys.stderr)
        return []
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else []


def parse_json_field(v: Any) -> list:
    """universities.json 里 name_history / tags 是 JSON 字符串而非数组。"""
    if isinstance(v, list):
        return v
    if not isinstance(v, str) or not v.strip():
        return []
    try:
        got = json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []
    return got if isinstance(got, list) else []


def collect_dims(source: Path) -> dict[str, dict[str, list]]:
    """按 uid 聚合各维度事件，裁剪字段与条数上限。"""
    by_uid: dict[str, dict[str, list]] = {}
    for dim, (fname, uid_keys) in DIM_SOURCES.items():
        rows = load_json(source, fname)
        if not rows:
            continue
        bucket: dict[str, list] = {}
        for r in rows:
            for k in uid_keys:
                v = r.get(k)
                if v:
                    bucket.setdefault(str(v), []).append(r)
                    break
        for uid, rs in bucket.items():
            out: list[dict] = []
            for r in rs:
                item = {}
                for kk in KEEP[dim]:
                    val = r.get(kk)
                    if val in (None, "", []):
                        continue
                    if kk in ("year", "year_start", "year_end", "year_approved"):
                        y = clean_year(val)
                        if y is not None:
                            item[kk] = y
                    else:
                        item[kk] = trim(val)
                if item:
                    out.append(item)
            # 去重：校长按 (姓名, 起始年, 结束年)；校名按 (年份, 新名)；其余按整条
            if dim == "president":
                # title 在源数据里混用 president / 校长 / party_secretary / 党委书记，
                # 先归一，否则同一人同一任期会被当成两条不同记录留下来。
                for r in out:
                    r["title"] = norm_title(r.get("title"))
                out = dedupe(out, ("person_name", "year_start", "year_end", "title"))
                # 源数据对"现任"会逐年补一条（2023/2024/2025 都是同一人同一职务），
                # 合并成一条：取最早起始年 + 最大结束年，避免现任者刷屏。
                out = merge_open_ended(out)
            elif dim == "name":
                out = dedupe(out, ("year", "name_new"))
            elif dim in ("location", "affiliation", "policy", "discipline"):
                out = dedupe(out, ("year", "description"))
            if out and any("year" in x for x in out):
                out.sort(key=lambda x: (as_year(x.get("year")) is None,
                                        as_year(x.get("year")) or 9999))
            elif dim == "president":
                out.sort(key=lambda x: (as_year(x.get("year_start")) is None,
                                        as_year(x.get("year_start")) or 9999))
            by_uid.setdefault(uid, {})[dim] = out[: CAPS[dim]]
        print(f"  {dim:12} 原始 {len(rows):6} 条 -> 覆盖 {len(bucket):5} 所")
    return by_uid


def build_record(u: dict, dims: Optional[dict]) -> dict:
    tags = parse_json_field(u.get("tags"))
    tag_names = []
    for t in tags:
        if isinstance(t, dict) and t.get("tag"):
            tag_names.append(t["tag"])
        elif isinstance(t, str):
            tag_names.append(t)
    rec: dict[str, Any] = {
        "uid": u.get("uid"),
        "name": u.get("name"),
        "province": u.get("province"),
        "city": u.get("city"),
        "level": u.get("level"),
        "nature": u.get("nature"),
        "type": u.get("type"),
        "established": as_year(u.get("established")),
        "affiliation": u.get("affiliation"),
        "current": u.get("current"),
        "name_history": parse_json_field(u.get("name_history")),
        "tags": tag_names[:12],
    }
    if u.get("motto"):
        rec["motto"] = trim(u["motto"], 80)
    if u.get("website"):
        rec["website"] = trim(u["website"], 120)
    if dims:
        rec["dims"] = dims
    return {k: v for k, v in rec.items() if v not in (None, "", [], {})}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="生成 university-history-page 随包数据")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE), help="项目 data 目录")
    ap.add_argument("--out", default=str(OUT_DIR), help="输出目录")
    ap.add_argument("--featured-top", type=int, default=0,
                    help="按事件丰度取 Top N 进精选层；0 表示用 985+211+双一流 规则")
    ap.add_argument("--shards", type=int, default=6, help="精选层分片数")
    args = ap.parse_args(argv)

    source = Path(args.source)
    out = Path(args.out)
    if not source.is_dir():
        print(f"[error] 源目录不存在：{source}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    print(f"源目录：{source}")
    uni = load_json(source, "universities")
    if not uni:
        print("[error] universities.json 为空或缺失", file=sys.stderr)
        return 1
    print(f"学校：{len(uni)} 所\n")

    print("聚合维度：")
    dims = collect_dims(source)

    # ---- 索引层（全部学校）----
    index: dict[str, dict] = {}
    for u in uni:
        uid = u.get("uid")
        if not uid:
            continue
        index[str(uid)] = {
            "n": u.get("name"),
            "p": u.get("province"),
            "c": u.get("city"),
            "l": u.get("level"),
            "e": as_year(u.get("established")),
        }

    # ---- 精选层 ----
    if args.featured_top > 0:
        ranked = sorted(
            uni,
            key=lambda u: -sum(len(v) for v in dims.get(str(u.get("uid")), {}).values()),
        )
        featured_unis = ranked[: args.featured_top]
        rule = f"丰度 Top {args.featured_top}"
    else:
        featured_unis = [
            u for u in uni
            if u.get("level") in ("985", "211")
            or "双一流" in [t.get("tag") if isinstance(t, dict) else t
                            for t in parse_json_field(u.get("tags"))]
        ]
        rule = "985 + 211 + 双一流"

    featured: dict[str, dict] = {}
    for u in featured_unis:
        uid = str(u.get("uid"))
        featured[uid] = build_record(u, dims.get(uid))

    # ---- 写盘：精选层分片 ----
    for old in out.glob("featured-*.json"):
        old.unlink()
    shards = max(1, args.shards)
    items = list(featured.items())
    per = (len(items) + shards - 1) // shards
    written = []
    for i in range(shards):
        part = dict(items[i * per: (i + 1) * per])
        if not part:
            continue
        p = out / f"featured-{i + 1:02d}.json"
        p.write_text(json.dumps(part, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                     encoding="utf-8")
        written.append(p)

    idx_path = out / "index.json"
    idx_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                        encoding="utf-8")

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    meta = {
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        # 只记录来源标识，不写绝对路径：发布到 skillhub 后本机路径不再成立，
        # 且绝对路径会泄露开发机目录结构。真源位置由 --source 或 UH_SOURCE_DIR 指定。
        "sourceRef": "Project-UniversityHistory/software/src/data",
        "sourceCounts": {
            "universities": len(uni),
            "dimensionRows": {d: sum(len(v.get(d, [])) for v in dims.values())
                              for d in DIM_LABELS},
        },
        "featuredRule": rule,
        "featuredCount": len(featured),
        "indexCount": len(index),
        "shards": [p.name for p in written],
        "dimensionLabels": DIM_LABELS,
        "checksums": {p.name: sha(p) for p in [idx_path, *written]},
    }
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    total = sum(p.stat().st_size for p in [idx_path, *written])
    featured_bytes = total - idx_path.stat().st_size
    print()
    print(f"索引层 : {len(index):5} 所  {idx_path.stat().st_size/1024:7.0f} KB")
    print(f"精选层 : {len(featured):5} 所  {featured_bytes/1024:7.0f} KB  "
          f"({len(written)} 分片, 规则: {rule})")
    print(f"合计   : {total/1024:7.0f} KB")
    print(f"输出   : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
