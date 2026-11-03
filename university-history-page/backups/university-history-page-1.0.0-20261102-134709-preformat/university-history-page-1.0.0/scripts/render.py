#!/usr/bin/env python3
"""把一所高校的发展史渲染成自包含 HTML 页面。

纯标准库、离线、无外部依赖（不引 CDN、不引字体、不引 JS 框架）。
产出一个可直接双击打开、可发给别人、可归档的单文件。

用法：
    python scripts/render.py --uid ahu
    python scripts/render.py --name 安徽大学
    python scripts/render.py --uid ahu --out ./安徽大学.html
    python scripts/render.py --list 安徽          # 按省列出可查学校
    python scripts/render.py --search 安徽        # 按名字搜 uid
    python scripts/render.py --uid ahu --json     # 输出结构化摘要而非 HTML
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DIM_ORDER = ["name", "location", "affiliation", "president",
             "discipline", "evaluation", "policy", "college", "degree", "program"]
DIM_LABELS = {
    "name": "校名演变", "location": "校址变迁", "affiliation": "隶属变更",
    "discipline": "学科建设", "evaluation": "学科评估", "president": "校长更迭",
    "policy": "政策影响", "college": "学院设置", "degree": "学位点", "program": "专业设置",
}
DIM_ICONS = {
    "name": "名", "location": "址", "affiliation": "隶", "president": "长",
    "discipline": "科", "evaluation": "评", "policy": "策", "college": "院",
    "degree": "位", "program": "专",
}
ACTION_LABELS = {
    "establish": "创建", "rename": "更名", "upgrade": "升格", "merge": "合并",
    "split": "分出", "relocate": "迁址", "restore": "复校", "suspend": "停办",
    "major_adjust": "院系调整", "discipline_upgrade": "学科升格",
    "first_class_selected": "入选双一流", "discipline_added": "增设学科",
}
REL_LABELS = {"RENAMED_TO": "更名", "SPLIT_FROM": "分出", "MERGED_INTO": "并入"}
TITLE_LABELS = {"president": "校长", "party_secretary": "党委书记", "校长": "校长"}
LOC_LABELS = {"main": "主校区", "wartime": "战时", "branch": "分校", "relocated": "迁址"}


# ---------------------------------------------------------------- 数据加载

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_all(data_dir: Path) -> tuple[dict, dict, dict]:
    """返回 (索引, 精选全维度数据, 元信息)。"""
    idx_path = data_dir / "index.json"
    if not idx_path.exists():
        raise SystemExit(f"[error] 缺少 {idx_path}，先跑 scripts/build-data.py")
    index = load_json(idx_path)

    featured: dict[str, dict] = {}
    for p in sorted(data_dir.glob("featured-*.json")):
        featured.update(load_json(p))

    meta = {}
    mp = data_dir / "meta.json"
    if mp.exists():
        meta = load_json(mp)
    return index, featured, meta


def resolve_uid(index: dict, featured: dict, uid: str | None, name: str | None) -> str | None:
    """把用户输入（uid 或校名）解析成 uid。支持模糊包含匹配。"""
    if uid:
        if uid in index or uid in featured:
            return uid
        # 允许只给部分 uid
        hits = [k for k in {**index, **featured} if k.lower() == uid.lower()]
        if hits:
            return hits[0]
        return None
    if not name:
        return None
    q = name.strip()
    pool = {**index, **featured}
    # 1) 完全同名
    exact = [k for k, v in pool.items() if (v.get("n") or v.get("name")) == q]
    if exact:
        return exact[0]
    # 2) 同名含历史校名
    for k, v in featured.items():
        if q in (v.get("name_history") or []):
            return k
    # 3) 包含匹配，取最短的（"安徽大学" 优先于 "安徽大学（xx）"）
    hits = [k for k, v in pool.items() if q in (v.get("n") or v.get("name") or "")]
    if hits:
        hits.sort(key=lambda k: len((pool[k].get("n") or pool[k].get("name") or "")))
        return hits[0]
    return None


# ---------------------------------------------------------------- 渲染辅助

def esc(v: Any) -> str:
    return html.escape(str(v)) if v is not None else ""


def year_text(v: Any) -> str:
    if v is None or v == "":
        return "年份不详"
    return f"{v}"


def left_text(v: Any, dim: str) -> str:
    """左列文本：评估维度显示轮次而非年份，缺失时如实标注。"""
    if v is None or v == "":
        return "轮次不详" if dim == "evaluation" else "年份不详"
    return f"{v}"


def span_text(start: Any, end: Any) -> str:
    if start and end:
        return f"{start}–{end}"
    if start:
        return f"{start} 起"
    if end:
        return f"至 {end}"
    return "任期不详"


def fmt_count(n: int) -> str:
    return f"{n}"


# ---------------------------------------------------------------- 各维度渲染

def render_events(items: list[dict], dim: str) -> str:
    """通用事件列表：年份 + 标题 + 描述。"""
    if not items:
        return '<p class="empty">暂无数据</p>'
    rows = []
    for it in items:
        # 校长维度没有 year 字段，年份在 year_start / year_end 里；
        # 取 it["year"] 会一律得到 None，页面就会满屏"年份不详"。
        y = it.get("year_start") if dim == "president" else it.get("year")
        if dim == "evaluation":
            # 学科评估源数据只有"第 N 轮"，没有年份。不能编年份，
            # 左列改显示轮次；学科评估各轮次年份是公开常识但源数据未收录。
            y = it.get("round") or None
        if dim == "president":
            title = it.get("person_name") or "（姓名缺失）"
            sub = span_text(it.get("year_start"), it.get("year_end"))
            badge = TITLE_LABELS.get(str(it.get("title") or ""), it.get("title") or "")
            if it.get("is_acting"):
                badge = (badge + " · 代理").strip(" ·")
            desc = it.get("description") or ""
        elif dim == "name":
            old = it.get("name_old") or ""
            new = it.get("name_new") or ""
            if old and new and old != new:
                title = f"{old} → {new}"
            else:
                title = new or old or "（校名缺失）"
            badge = REL_LABELS.get(str(it.get("relType") or ""), it.get("relType") or "")
            desc = it.get("description") or ""
        elif dim == "location":
            title = it.get("location") or "（地点缺失）"
            badge = LOC_LABELS.get(str(it.get("location_type") or ""), it.get("location_type") or "")
            desc = it.get("description") or ""
        elif dim == "affiliation":
            old = it.get("affiliation_old") or ""
            new = it.get("affiliation_new") or ""
            title = f"{old} → {new}" if old and new and old != new else (new or old or "（缺失）")
            badge = ""
            desc = it.get("description") or ""
        elif dim == "discipline":
            title = it.get("discipline_name") or "（学科缺失）"
            badge = ACTION_LABELS.get(str(it.get("action") or ""), it.get("action") or "")
            desc = it.get("description") or ""
        elif dim == "policy":
            title = it.get("policy_name") or "（政策缺失）"
            badge = it.get("impact_type") or ""
            desc = it.get("impact_detail") or ""
        elif dim == "evaluation":
            title = it.get("discipline_name") or "（学科缺失）"
            badge = it.get("rating") or ""
            # 轮次已经显示在左列，描述里不再重复，改为说明评级口径
            desc = "教育部学科评估评级" if badge else ""

        elif dim == "college" or dim == "degree" or dim == "program":
            title = it.get("name") or "（缺失）"
            badge = ""
            desc = ""
        else:
            title = "（缺失）"
            badge = ""
            desc = ""
        rows.append(
            f'<li class="ev">'
            f'<span class="ev-year">{esc(left_text(y, dim))}</span>'
            f'<div class="ev-body"><div class="ev-head"><span class="ev-title">{esc(title)}</span>'
            + (f'<span class="badge">{esc(badge)}</span>' if badge else "")
            + f"</div>"
            + (f'<p class="ev-desc">{esc(desc)}</p>' if desc else "")
            + f"</div></li>"
        )
    return '<ul class="events">' + "".join(rows) + "</ul>"


def render_college(items: list[dict]) -> str:
    if not items:
        return '<p class="empty">暂无数据</p>'
    rows = []
    for it in items:
        name = it.get("name") or "（缺失）"
        pc = it.get("program_count") or 0
        pt = it.get("point_count") or 0
        rows.append(
            f'<tr><td>{esc(name)}</td>'
            f'<td class="num">{fmt_count(pt)}</td>'
            f'<td class="num">{fmt_count(pc)}</td></tr>'
        )
    return ('<table class="tbl"><thead><tr><th>学院</th>'
            '<th class="num">学位点</th><th class="num">专业</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def render_degree(items: list[dict]) -> str:
    if not items:
        return '<p class="empty">暂无数据</p>'
    rows = []
    for it in items:
        lv = it.get("level")
        # 真实数据问题：level 大量是 "待补充"，不能当成"硕士/博士"渲染
        lv_text = lv if lv and lv != "待补充" else "层次待补充"
        rows.append(
            f'<tr><td>{esc(it.get("name") or "（缺失）")}</td>'
            f'<td>{esc(lv_text)}</td>'
            f'<td>{esc(it.get("degree_type") or "—")}</td>'
            f'<td>{esc(it.get("college_name") or "—")}</td></tr>'
        )
    return ('<table class="tbl"><thead><tr><th>学位点</th><th>层次</th>'
            '<th>类型</th><th>所属学院</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def render_program(items: list[dict]) -> str:
    if not items:
        return '<p class="empty">暂无数据</p>'
    rows = []
    for it in items:
        rows.append(
            f'<tr><td>{esc(it.get("name") or "（缺失）")}</td>'
            f'<td>{esc(it.get("college_name") or "—")}</td>'
            f'<td>{esc(it.get("status") or "—")}</td></tr>'
        )
    return ('<table class="tbl"><thead><tr><th>专业</th><th>所属学院</th>'
            '<th>状态</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


# ---------------------------------------------------------------- 总览时间轴

def build_master_timeline(rec: dict) -> list[dict]:
    """把各维度事件合并成一条总览时间轴，按年份排序。"""
    dims = rec.get("dims") or {}
    out: list[dict] = []
    for dim in ("name", "location", "affiliation", "discipline", "policy"):
        for it in dims.get(dim) or []:
            y = it.get("year")
            if not y:
                continue
            if dim == "name":
                t = it.get("description") or it.get("name_new") or ""
            elif dim == "location":
                t = it.get("description") or it.get("location") or ""
            elif dim == "affiliation":
                t = it.get("description") or it.get("affiliation_new") or ""
            elif dim == "discipline":
                t = it.get("description") or it.get("discipline_name") or ""
            else:
                t = it.get("impact_detail") or it.get("policy_name") or ""
            if not t:
                continue
            out.append({"year": y, "dim": dim, "text": t})
    # 同一年同一维度只留一条，避免总览被淹没
    seen: set[tuple] = set()
    deduped = []
    for e in sorted(out, key=lambda x: x["year"]):
        k = (e["year"], e["dim"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(e)
    return deduped


def render_timeline(events: list[dict]) -> str:
    if not events:
        return '<p class="empty">暂无可排序的时间线事件</p>'
    rows = []
    for e in events:
        rows.append(
            f'<li class="tl-item" data-dim="{esc(e["dim"])}">'
            f'<span class="tl-year">{esc(e["year"])}</span>'
            f'<span class="tl-dim">{esc(DIM_LABELS.get(e["dim"], e["dim"]))}</span>'
            f'<span class="tl-text">{esc(e["text"])}</span></li>'
        )
    return '<ul class="timeline">' + "".join(rows) + "</ul>"


# ---------------------------------------------------------------- 页面骨架

CSS = """
:root{
  --ink:#1c2b3a; --muted:#6b7a8d; --line:#dfe5ec; --bg:#fbfaf7; --card:#ffffff;
  --gold:#b8892a; --navy:#1f3a5f;
  --c-name:#b8892a; --c-location:#2e8b6f; --c-affiliation:#3f6fa8;
  --c-president:#8a5fa8; --c-discipline:#c2572f; --c-evaluation:#2f7f9c;
  --c-policy:#a8443f; --c-college:#5f7a2f; --c-degree:#4a5fa8; --c-program:#8a7a2f;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC","Microsoft YaHei",
    "PingFang SC","Hiragino Sans GB",sans-serif;
  line-height:1.65; font-size:15px;
}
.wrap{max-width:960px; margin:0 auto; padding:0 20px 72px}
header.hero{
  background:linear-gradient(160deg,#1f3a5f 0%,#2c4f77 55%,#3a5f8a 100%);
  color:#fff; padding:44px 20px 38px; margin-bottom:28px;
}
header.hero .inner{max-width:960px;margin:0 auto}
.kicker{font-size:12px;letter-spacing:.22em;text-transform:uppercase;opacity:.72;margin:0 0 10px}
h1{margin:0; font-size:34px; line-height:1.25; font-weight:700; letter-spacing:.01em}
.hero-sub{margin:12px 0 0; font-size:14px; opacity:.9}
.hero-tags{margin:16px 0 0; display:flex; flex-wrap:wrap; gap:8px}
.tag{
  display:inline-block; padding:3px 11px; border-radius:999px; font-size:12px;
  background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.28);
}
.facts{
  display:flex; flex-wrap:wrap; gap:1px;
  background:var(--line); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; margin:0 0 30px;
}
.fact{background:var(--card); padding:14px 16px; flex:1 1 130px; min-width:0}
.fact dt{font-size:11px; color:var(--muted); letter-spacing:.06em; margin:0 0 4px}
.fact dd{margin:0; font-size:15px; font-weight:600; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis}
h2{
  font-size:20px; margin:40px 0 16px; padding-bottom:9px;
  border-bottom:2px solid var(--line); letter-spacing:.02em;
}
h2 .cnt{font-size:12px; color:var(--muted); font-weight:400; margin-left:8px}
.note{
  background:#fff9ec; border-left:3px solid var(--gold);
  padding:11px 15px; margin:0 0 22px; font-size:13px; color:#6a5626; border-radius:0 6px 6px 0;
}
.timeline{list-style:none; margin:0; padding:0}
.tl-item{
  display:grid; grid-template-columns:64px 96px 1fr; gap:12px;
  padding:10px 0; border-bottom:1px solid var(--line); font-size:14px;
}
.tl-item:last-child{border-bottom:none}
.tl-year{font-weight:700; color:var(--navy); font-variant-numeric:tabular-nums}
.tl-dim{font-size:12px; color:var(--muted)}
.tl-text{color:#33404f}
.dims{display:grid; gap:16px}
.dim{
  background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:18px 20px; break-inside:avoid;
}
.dim-head{display:flex; align-items:center; gap:10px; margin:0 0 14px}
.dim-icon{
  width:26px;height:26px;border-radius:7px;display:grid;place-items:center;
  font-size:12px;font-weight:700;color:#fff;flex:0 0 auto;
}
.dim-title{font-size:16px;font-weight:700;margin:0}
.dim-cnt{font-size:11px;color:var(--muted);margin-left:auto}
.events{list-style:none;margin:0;padding:0}
.ev{display:grid;grid-template-columns:70px 1fr;gap:12px;padding:8px 0;border-bottom:1px dashed var(--line)}
.ev:last-child{border-bottom:none}
.ev-year{font-size:13px;font-weight:700;color:var(--navy);font-variant-numeric:tabular-nums;padding-top:1px}
.ev-head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.ev-title{font-size:14px;font-weight:600}
.ev-desc{margin:4px 0 0;font-size:13px;color:#5a6675}
.badge{
  font-size:11px;padding:1px 7px;border-radius:4px;
  background:#eef2f7;color:#4a5a6d;border:1px solid #dde4ec;white-space:nowrap;
}
.empty{font-size:13px;color:var(--muted);margin:0}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{
  text-align:left;font-weight:600;color:var(--muted);font-size:11px;
  letter-spacing:.06em;padding:6px 8px;border-bottom:1px solid var(--line);
}
.tbl td{padding:7px 8px;border-bottom:1px solid #eef1f5}
.tbl tr:last-child td{border-bottom:none}
.tbl .num{text-align:right;font-variant-numeric:tabular-nums}
footer{
  margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
  font-size:12px;color:var(--muted);line-height:1.9;
}
.missing{
  background:#f4f6f9;border:1px dashed #cfd8e3;border-radius:10px;
  padding:26px;text-align:center;color:#5a6675;font-size:14px;
}
.cands{margin:10px 0 0;padding-left:20px;font-size:13px}
@media print{
  body{background:#fff}
  header.hero{background:#1f3a5f !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .dim{page-break-inside:avoid}
}
@media (max-width:640px){
  h1{font-size:26px}
  /* 移动端事实卡改为两列，否则 flex 的 130px 基准会横向溢出、把页面撑宽 */
  .facts{display:grid;grid-template-columns:1fr 1fr}
  .fact{padding:12px 14px}
  .fact dd{font-size:14px}
  /* 时间轴：年份与维度标签同一行，正文另起，避免维度名单独占一行 */
  .tl-item{
    grid-template-columns:56px 1fr;grid-template-areas:"y d" "t t";
    row-gap:2px;padding:11px 0;
  }
  .tl-year{grid-area:y}.tl-dim{grid-area:d;text-align:right}
  .tl-text{grid-area:t;padding-top:2px}
  .ev{grid-template-columns:58px 1fr;gap:8px}
  .wrap{padding:0 14px 48px}
  .dim{padding:15px 15px}
}
"""


def render_page(rec: dict, featured: bool, meta: dict) -> str:
    uid = rec.get("uid")
    name = rec.get("name") or uid
    dims = rec.get("dims") or {}

    # 事实卡
    facts = []
    if rec.get("established"):
        facts.append(("建校", f"{rec['established']} 年"))
    if rec.get("province"):
        facts.append(("省份", rec["province"]))
    if rec.get("city"):
        facts.append(("城市", rec["city"]))
    if rec.get("level"):
        facts.append(("层次", rec["level"]))
    if rec.get("nature"):
        facts.append(("性质", rec["nature"]))
    if rec.get("affiliation"):
        facts.append(("隶属", rec["affiliation"]))
    if rec.get("name_history"):
        facts.append(("历史校名", f"{len(rec['name_history'])} 个"))
    facts_html = ""
    if facts:
        cells = "".join(
            f'<div class="fact"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts
        )
        facts_html = f'<dl class="facts">{cells}</dl>'

    tags = rec.get("tags") or []
    tags_html = ""
    if tags:
        tags_html = '<div class="hero-tags">' + "".join(
            f'<span class="tag">{esc(t)}</span>' for t in tags
        ) + "</div>"

    # 名称沿革条
    nh = rec.get("name_history") or []
    nh_html = ""
    if nh:
        nh_html = (
            '<p class="note"><strong>校名沿革：</strong>'
            + " → ".join(esc(x) for x in nh) + "</p>"
        )

    if not featured:
        body_dims = (
            '<div class="missing">'
            f"<p><strong>{esc(name)}</strong> 已收录于全量索引，但本技能随包只带 "
            f"{meta.get('featuredCount', '部分')} 所重点高校的完整发展史数据。</p>"
            "<p>可渲染的字段：基本信息（省份 / 城市 / 层次 / 建校年 / 隶属 / 历史校名）。</p>"
            "<p>如需该校完整 7 维度时间线，请在服务端接入完整数据集，"
            "或改用 <code>--list</code> 查看随包覆盖范围。</p>"
            "</div>"
        )
        dims_heading = "维度数据"
    else:
        blocks = []
        for dim in DIM_ORDER:
            items = dims.get(dim) or []
            if not items:
                continue
            color = f"var(--c-{dim})"
            if dim in ("college", "degree", "program"):
                inner = {"college": render_college, "degree": render_degree,
                         "program": render_program}[dim](items)
            else:
                inner = render_events(items, dim)
            blocks.append(
                f'<section class="dim" id="dim-{dim}">'
                f'<div class="dim-head">'
                f'<span class="dim-icon" style="background:{color}">{DIM_ICONS[dim]}</span>'
                f'<h3 class="dim-title">{DIM_LABELS[dim]}</h3>'
                f'<span class="dim-cnt">{len(items)} 条</span>'
                f"</div>{inner}</section>"
            )
        body_dims = '<div class="dims">' + "".join(blocks) + "</div>"
        dims_heading = f"七个维度" if len(blocks) >= 7 else f"{len(blocks)} 个维度"

    # 总览时间轴
    tl = build_master_timeline(rec) if featured else []
    tl_html = ""
    if tl:
        tl_html = (
            f'<h2>总览时间轴<span class="cnt">{len(tl)} 个节点</span></h2>'
            + render_timeline(tl)
        )

    gen = meta.get("generatedAt") or "—"
    src_n = meta.get("indexCount") or len(dims)
    foot = (
        f'<footer><p><strong>数据说明</strong>：本页由 university-history-page 技能离线生成，'
        f"单文件自包含，不依赖任何外部资源。</p>"
        f"<p>全量索引 {src_n} 所高校；随包完整发展史 {meta.get('featuredCount', '—')} 所。"
        f"数据生成时间 {esc(gen)}。</p>"
        f"<p>页面中的年份、任期、学位层次均照原始数据渲染；"
        f"标为“待补充 / 任期不详”表示源数据缺失，未做推测填充。</p></footer>"
    )

    title = f"{name} · 发展史"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header class="hero">
  <div class="inner">
    <p class="kicker">中国高校发展史 · 单校图谱</p>
    <h1>{esc(name)}</h1>
    <p class="hero-sub">{esc(rec.get('province') or '')}{(' · ' + esc(rec['city'])) if rec.get('city') else ''}
      {(' · ' + esc(rec['level'])) if rec.get('level') else ''}</p>
    {tags_html}
  </div>
</header>
<div class="wrap">
  {facts_html}
  {nh_html}
  {tl_html}
  <h2>{dims_heading}</h2>
  {body_dims}
  {foot}
</div>
</body>
</html>
"""


def render_not_found(query: str, index: dict) -> str:
    q = query.strip()
    hits = [(k, v) for k, v in index.items() if q in (v.get("n") or "")]
    hits.sort(key=lambda kv: len(kv[1].get("n") or ""))
    if hits:
        lst = "".join(
            f'<li><code>{esc(k)}</code> — {esc(v.get("n"))}'
            + (f'（{esc(v.get("p"))}）' if v.get("p") else "")
            + "</li>"
            for k, v in hits[:20]
        )
        cands = f'<p>可能想找：</p><ul class="cands">{lst}</ul>'
    else:
        cands = "<p>全量索引中也没有匹配项，请确认校名或改用 uid。</p>"
    return (
        f'<div class="missing"><p><strong>未找到「{esc(q)}」</strong></p>'
        f"<p>请检查校名是否完整，或用 <code>--list</code> 按省份浏览。</p>{cands}</div>"
    )


# ---------------------------------------------------------------- CLI

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="渲染单所高校的发展史为自包含 HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--uid", help="学校 uid，如 ahu / pku")
    ap.add_argument("--name", help="学校名称，如 安徽大学")
    ap.add_argument("--out", help="输出 HTML 路径；缺省为 <uid>.html")
    ap.add_argument("--data", default=str(DATA_DIR), help="数据目录")
    ap.add_argument("--json", action="store_true", help="输出结构化摘要（JSON）而非 HTML")
    ap.add_argument("--list", metavar="省份", help="列出某省可查学校")
    ap.add_argument("--search", metavar="关键词", help="按校名搜索 uid")
    ap.add_argument("--stdout", action="store_true", help="把 HTML 打到标准输出，不写文件")
    args = ap.parse_args(argv)

    data_dir = Path(args.data)
    index, featured, meta = load_all(data_dir)

    if args.list:
        prov = args.list
        rows = [(k, v) for k, v in index.items() if prov in (v.get("p") or "")]
        if not rows:
            print(f"[error] 没有省份包含「{prov}」的学校", file=sys.stderr)
            return 1
        rows.sort(key=lambda kv: kv[1].get("n") or "")
        print(f"{prov} 共 {len(rows)} 所：")
        for k, v in rows:
            mark = "★" if k in featured else " "
            print(f"  {mark} {k:14} {v.get('n') or '':22} {v.get('l') or ''}")
        print("\n★ = 随包带完整发展史数据")
        return 0

    if args.search:
        q = args.search
        hits = [(k, v) for k, v in index.items() if q in (v.get("n") or "")]
        hits.sort(key=lambda kv: len(kv[1].get("n") or ""))
        if not hits:
            print(f"[error] 未找到包含「{q}」的学校", file=sys.stderr)
            return 1
        for k, v in hits[:30]:
            mark = "★" if k in featured else " "
            print(f"  {mark} {k:14} {v.get('n') or '':22} {v.get('p') or ''}")
        return 0

    if not args.uid and not args.name:
        ap.print_help()
        return 1

    query = args.uid or args.name or ""
    uid = resolve_uid(index, featured, args.uid, args.name)
    if not uid:
        page = render_not_found(query, index)
        if args.stdout:
            print(page)
        else:
            print(f"[error] 未找到「{query}」", file=sys.stderr)
            return 1
        return 0

    is_featured = uid in featured
    if is_featured:
        rec = featured[uid]
    else:
        v = index[uid]
        rec = {
            "uid": uid, "name": v.get("n"), "province": v.get("p"),
            "city": v.get("c"), "level": v.get("l"), "established": v.get("e"),
        }

    if args.json:
        summary = {
            "uid": uid,
            "name": rec.get("name"),
            "featured": is_featured,
            "dims": {d: len(v) for d, v in (rec.get("dims") or {}).items()},
            "timelineNodes": len(build_master_timeline(rec)) if is_featured else 0,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    page = render_page(rec, is_featured, meta)
    if args.stdout:
        print(page)
        return 0

    out = Path(args.out) if args.out else Path(f"{uid}.html")
    out.write_text(page, encoding="utf-8")
    print(f"[ok] {rec.get('name') or uid} -> {out}  ({out.stat().st_size/1024:.0f} KB)")
    if not is_featured:
        print("    注意：该校仅有基本信息，完整发展史数据未随包（见页面说明）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
