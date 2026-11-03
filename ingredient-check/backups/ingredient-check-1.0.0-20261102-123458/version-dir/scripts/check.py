#!/usr/bin/env python3
"""配料表判定：把一段配料表文本，按知识库逐项匹配并给出购买档位。

纯标准库、离线运行。判定规则与 open-project 的 Project-IngredientAnalyzer
后端保持一致（matcher.py / recommender.py / models.py），差异仅在数据源：
本脚本读技能自带的 data/ 目录，不连数据库、不调 LLM。

用法：
    python scripts/check.py --text "水、白砂糖、柠檬酸、山梨酸钾"
    python scripts/check.py --text "..." --type cosmetic
    python scripts/check.py --text "..." --mode child
    python scripts/check.py --text "..." --json
    python scripts/check.py --kb-report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

# Windows 控制台默认 GBK，中文与符号会炸；强制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---- 与后端一致的常量 ------------------------------------------------
FUZZY_THRESHOLD = 0.82
FUZZY_MIN_LEN_RATIO = 0.6
CAUTION_RATIO_THRESHOLD = 0.40
RESTRICTED_HARD_LIMIT = 2

LEVEL_LABELS = {
    "recommend": "推荐购买",
    "okay": "可以购买",
    "moderate": "适量购买",
    "caution": "谨慎购买",
    "not_recommended": "不建议购买",
}
SAFETY_LABELS = {
    "safe": "安全",
    "caution": "注意",
    "restricted": "限量",
    "banned": "禁用",
}
UNMATCHED_LABEL = "暂未收录"
PENDING_REVIEW_LABEL = "已收录 · 等级待确认"
PRODUCT_TYPE_LABELS = {"food": "食品", "daily": "日用品", "cosmetic": "化妆品"}
ESCALATION = ["recommend", "okay", "moderate", "caution", "not_recommended"]
VALID_TYPES = frozenset({"food", "daily", "cosmetic"})

# 配料分隔符：中英文顿号、逗号、分号、斜杠、换行、括号外顿号
_SPLIT_RE = re.compile(r"[、,，;；\n\r|]+")
# 需要从配料名里剥掉的包装/标签噪声
_NOISE_RE = re.compile(
    r"(配料表|配料|成分表|成分|原料|食品添加剂|添加剂|类别|品名|净含量|规格|"
    r"生产日期|保质期|贮存条件|执行标准|产品标准号|生产许可证|SC\d+|GB\s?\d+)"
)

# 整项即标签残渣的特征（不是"含噪声"，而是"整项就是噪声"）。
# 农夫山泉线上案例的根因就在这里：`厂名厂址`/`500ml` 被当成有效配料，
# 导致零命中时被误判为"可信 → 推荐购买"。
_RESIDUE_WHOLE_RE = re.compile(
    r"^(厂名|厂址|地址|厂家|制造商|委托方|受托方|经销商|联系方式|电话|"
    r"网址|邮箱|邮编|产地|原产国|进口商|"
    r"见包装|见瓶身|见标签|另见|详见)"
)
# 纯数量/容量/重量项：500ml、净重 1.5kg、250 克
_RESIDUE_QTY_RE = re.compile(r"^\s*[\d.]+\s*(ml|mL|ML|L|l|g|G|kg|KG|克|千克|毫升|升|%|％)?\s*$")
# 纯 ASCII 品牌型号残渣：全大写字母+数字且无中文，如 "SC1234"、"GB7718"
_RESIDUE_CODE_RE = re.compile(r"^[A-Za-z]{1,6}[\s\-]?\d{2,}[A-Za-z0-9\s\-]*$")


# ---- 数据加载 --------------------------------------------------------
def _load_json(name: str) -> list[dict[str, Any]]:
    p = DATA_DIR / name
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        raw = raw.get("ingredients") or raw.get("data") or []
    return [x for x in raw if isinstance(x, dict) and (x.get("name") or "").strip()]


def _scope_types(raw: object) -> set[str]:
    """条目适用品类。存量食品条目无 product_types 时按 food 处理（安全缺省）。"""
    if isinstance(raw, (list, tuple)):
        vals = list(raw)
    elif isinstance(raw, str) and raw.strip():
        try:
            vals = json.loads(raw)
        except json.JSONDecodeError:
            vals = []
    else:
        vals = []
    if not isinstance(vals, list):
        return {"food"}
    got = {t for t in vals if isinstance(t, str) and t in VALID_TYPES}
    return got or {"food"}


def _is_ascii_token(s: str) -> bool:
    return bool(s) and all(ord(ch) < 128 for ch in s)


def alias_key(s: str) -> str:
    """英文别名必须大写归一：库里存 `Aqua`，标签印 `AQUA`。中文原样。"""
    t = (s or "").strip()
    if not t:
        return ""
    return t.upper() if _is_ascii_token(t) else t


def build_index() -> dict[str, Any]:
    entries = _load_json("knowledge_base.json") + _load_json("knowledge_base_nonfood.json")
    by_name: dict[str, dict] = {}
    by_alias: dict[str, dict] = {}
    for d in entries:
        name = (d.get("name") or "").strip()
        if not name:
            continue
        by_name.setdefault(name, d)
        by_name.setdefault(alias_key(name), d)
        for alias in d.get("aliases") or []:
            key = alias_key(str(alias))
            if key and key not in by_name:
                by_alias.setdefault(key, d)
    return {"by_name": by_name, "by_alias": by_alias, "entries": entries}


# ---- 解析 ------------------------------------------------------------
def _split_top_level(text: str) -> list[str]:
    """按分隔符切分配料表，但**不切括号内部**。

    真实缺陷（本次自测发现）：`植物油（棕榈油、大豆油）` 曾被切成
    `植物油（棕榈油` + `植物油`，导致复合配料被撕裂成两个半截项。
    括号内的顿号是子配料分隔符，必须在括号闭合后才允许切分。
    """
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    pairs = {"（": "）", "(": ")"}
    for ch in text:
        if ch in pairs:
            depth += 1
            buf.append(ch)
        elif ch in pairs.values():
            depth = max(0, depth - 1)
            buf.append(ch)
        elif depth == 0 and ch in "、,，;；\n\r|":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def parse_text(text: str) -> list[dict[str, Any]]:
    """把配料表文本切成配料项。保留原始名，剥掉标签噪声。

    注意：这里的 strip 字符集**不含括号**。曾经的缺陷是 strip 把复合配料末尾的
    `）` 一起剥掉，于是 `植物油（棕榈油、大豆油）` 变成
    `植物油（棕榈油、大豆油`，括号正则匹配失败，子配料整棵丢失。
    """
    cleaned = _NOISE_RE.sub("", text or "")
    out: list[dict[str, Any]] = []
    for raw in _split_top_level(cleaned):
        name = raw.strip().strip("。.：:，,、;；\"'“”【】[]")
        if not name:
            continue
        # 括号内的复合配料：主料 + 子配料（子配料按顶层规则切分）
        m = re.match(r"^(.+?)[（(](.+?)[)）]$", name)
        if m:
            main = m.group(1).strip()
            subs = [s.strip() for s in _split_top_level(m.group(2)) if s.strip()]
            out.append({"name": main, "sub_ingredients": [{"name": s} for s in subs]})
        else:
            out.append({"name": name})
    return out


def _level_for_type(hit: dict, product_type: str) -> tuple[Optional[str], Optional[str]]:
    """按品类取本品类口径下的等级与依据，绝不跨品类套用。"""
    if product_type == "cosmetic":
        return hit.get("cosmetic_safety_level"), hit.get("cosmetic_safety_basis")
    if product_type == "daily":
        return hit.get("daily_safety_level"), hit.get("daily_safety_basis")
    return hit.get("safety_level"), hit.get("safety_basis")


def _match_one(name: str, index: dict, allow_fuzzy: bool) -> tuple[Optional[dict], str]:
    key = alias_key(name)
    if not key:
        return None, "none"
    hit = index["by_name"].get(key)
    if hit:
        return hit, "exact"
    hit = index["by_alias"].get(key)
    if hit:
        return hit, "alias"
    if not allow_fuzzy:
        return None, "none"

    best_score, best = 0.0, None
    for d in index["entries"]:
        candidates = [d.get("name") or ""]
        for alias in d.get("aliases") or []:
            if len(str(alias)) >= len(key) * FUZZY_MIN_LEN_RATIO:
                candidates.append(str(alias))
        for cand in candidates:
            cand = alias_key(cand)
            if not cand:
                continue
            score = SequenceMatcher(None, key, cand).ratio()
            if score < FUZZY_THRESHOLD:
                continue
            ratio = min(len(key), len(cand)) / max(len(key), len(cand))
            if ratio < FUZZY_MIN_LEN_RATIO:
                continue
            if score > best_score:
                best_score, best = score, d
    return (best, "fuzzy") if best is not None else (None, "none")


def match_tree(item: dict, index: dict, allow_fuzzy: bool, product_type: str) -> dict:
    original = (item.get("name") or "").strip()
    hit, match_type = _match_one(original, index, allow_fuzzy)
    subs_src = list(item.get("sub_ingredients") or [])
    if not subs_src and hit:
        builtin = hit.get("sub_ingredients")
        if isinstance(builtin, list):
            subs_src = [{"name": str(s)} for s in builtin if str(s).strip()]
        elif isinstance(builtin, str) and builtin.strip():
            try:
                parsed = json.loads(builtin)
                if isinstance(parsed, list):
                    subs_src = [{"name": str(s)} for s in parsed if str(s).strip()]
            except (json.JSONDecodeError, TypeError):
                subs_src = []
    subs = (
        [match_tree(s, index, allow_fuzzy, product_type) for s in subs_src] if subs_src else None
    )

    in_scope = hit is not None and product_type in _scope_types(hit.get("product_types"))
    if hit is None or not in_scope:
        return {
            "name": original,
            "original_name": original,
            "matched": False,
            "match_type": "none",
            "safety_level": None,
            "safety_label": UNMATCHED_LABEL,
            "is_compound": bool(subs),
            "sub_ingredients": subs,
        }

    level, basis = _level_for_type(hit, product_type)
    return {
        "name": (hit.get("name") or original).strip(),
        "original_name": original,
        "matched": True,
        "match_type": match_type,
        "aliases": list(hit.get("aliases") or []),
        "category": hit.get("category"),
        "function_desc": hit.get("function_desc"),
        "safety_level": level,
        "safety_basis": basis or "",
        "safety_label": SAFETY_LABELS.get(level, PENDING_REVIEW_LABEL) if level else PENDING_REVIEW_LABEL,
        "misconception": hit.get("misconception"),
        "special_population": hit.get("special_population"),
        "is_compound": bool(subs) or bool(hit.get("is_compound")),
        "sub_ingredients": subs,
    }


def flatten(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for it in items:
        out.append(it)
        if it.get("sub_ingredients"):
            out.extend(flatten(it["sub_ingredients"]))
    return out


# ---- 判定 ------------------------------------------------------------
def _is_credible_name(name: str) -> bool:
    """有效配料名：≥2 个字符，且不是纯数字/纯标点/标签残渣。"""
    t = (name or "").strip()
    if len(t) < 2:
        return False
    if re.fullmatch(r"[0-9\s.,%]+", t):
        return False
    if _RESIDUE_QTY_RE.match(t):
        return False
    if _RESIDUE_WHOLE_RE.match(t):
        return False
    if _RESIDUE_CODE_RE.match(t):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", t))


def _has_label_residue(name: str) -> bool:
    """整项是否为标签残渣（而非"含噪声的有效配料"）。"""
    t = (name or "").strip()
    if not t:
        return True
    if _NOISE_RE.search(t):
        return True
    if _RESIDUE_WHOLE_RE.match(t) or _RESIDUE_QTY_RE.match(t) or _RESIDUE_CODE_RE.match(t):
        return True
    return False


def escalate(level: str, min_level: str) -> str:
    try:
        return ESCALATION[max(ESCALATION.index(level), ESCALATION.index(min_level))]
    except ValueError:
        return level


def _has_infant_warning(matched: list[dict]) -> bool:
    return any("婴幼儿" in (i.get("special_population") or "") for i in matched)


def determine_level(
    ingredients: list[dict], mode: str = "general", product_type: str = "food"
) -> str:
    """纯规则、可复现的购买档位判定。同一输入永远同一输出。"""
    flat = flatten(ingredients)
    matched = [i for i in flat if i.get("matched") and i.get("safety_level")]
    banned = [i for i in matched if i["safety_level"] == "banned"]
    restricted = [i for i in matched if i["safety_level"] == "restricted"]
    caution = [i for i in matched if i["safety_level"] == "caution"]

    if banned:
        return "not_recommended"
    if len(restricted) >= RESTRICTED_HARD_LIMIT:
        return "not_recommended"
    if len(restricted) == 1:
        return "caution"

    if not matched:
        # 非食品零命中 = 无安全数据，绝不给"放心"结论。
        if product_type != "food":
            return "moderate"
        # 食品零命中要分两种：真没添加剂 vs 解析全是标签噪声。
        credible = [i for i in flat if _is_credible_name(i.get("name") or "")]
        if not credible:
            return "moderate"
        if len(credible) < len(flat) / 2:
            return "moderate"
        if any(_has_label_residue(i.get("name") or "") for i in credible):
            return "moderate"
        return "recommend"

    ratio = len(caution) / len(matched)
    if len(caution) == 0:
        level = "recommend"
    elif ratio >= CAUTION_RATIO_THRESHOLD:
        level = "moderate"
    else:
        level = "okay"

    if mode == "child" and _has_infant_warning(matched):
        level = escalate(level, "caution")
    return level


def build_reasons(ingredients: list[dict], level: str, product_type: str) -> list[str]:
    flat = flatten(ingredients)
    matched = [i for i in flat if i.get("matched") and i.get("safety_level")]
    reasons: list[str] = []
    banned = [i for i in matched if i["safety_level"] == "banned"]
    restricted = [i for i in matched if i["safety_level"] == "restricted"]
    caution = [i for i in matched if i["safety_level"] == "caution"]
    unmatched = [i for i in flat if not i.get("matched")]

    if banned:
        reasons.append("含禁用成分：" + "、".join(i["name"] for i in banned))
    if restricted:
        reasons.append("含限量成分：" + "、".join(i["name"] for i in restricted))
    if caution:
        reasons.append("含需注意成分：" + "、".join(i["name"] for i in caution))
    if unmatched:
        reasons.append(
            f"有 {len(unmatched)} 项未收录于知识库（{UNMATCHED_LABEL}），结论存在盲区"
        )
    if not matched:
        if product_type != "food":
            reasons.append("非食品知识库零命中，无本品类安全数据，不给正面结论")
        else:
            reasons.append("未检出已收录成分；若配料本身单一可信则结论偏正面，否则按噪声保守处理")
    return reasons


# ---- 报告 ------------------------------------------------------------
def kb_report() -> dict:
    food = _load_json("knowledge_base.json")
    nonfood = _load_json("knowledge_base_nonfood.json")
    def count_level(arr: list[dict], col: str) -> dict[str, int]:
        c: dict[str, int] = {}
        for d in arr:
            v = d.get(col) or "（空/待确认）"
            c[v] = c.get(v, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))
    return {
        "food_entries": len(food),
        "nonfood_entries": len(nonfood),
        "food_safety_levels": count_level(food, "safety_level"),
        "nonfood_cosmetic_levels": count_level(nonfood, "cosmetic_safety_level"),
        "data_dir": str(DATA_DIR),
    }


def run(text: str, product_type: str = "food", mode: str = "general") -> dict:
    index = build_index()
    parsed = parse_text(text)
    allow_fuzzy = product_type == "food"
    results = [match_tree(p, index, allow_fuzzy, product_type) for p in parsed]
    level = determine_level(results, mode=mode, product_type=product_type)
    flat = flatten(results)
    return {
        "input": text,
        "product_type": product_type,
        "product_type_label": PRODUCT_TYPE_LABELS.get(product_type, product_type),
        "mode": mode,
        "level": level,
        "level_label": LEVEL_LABELS.get(level, level),
        "reasons": build_reasons(results, level, product_type),
        "stats": {
            "total": len(flat),
            "matched": sum(1 for i in flat if i.get("matched")),
            "unmatched": sum(1 for i in flat if not i.get("matched")),
        },
        "ingredients": results,
    }


def render_markdown(r: dict) -> str:
    lines: list[str] = []
    lines.append(f"# 配料表判定：{r['level_label']}")
    lines.append("")
    lines.append(f"- 品类：**{r['product_type_label']}**　人群模式：`{r['mode']}`")
    lines.append(
        f"- 共 {r['stats']['total']} 项，命中 {r['stats']['matched']} 项，"
        f"未收录 {r['stats']['unmatched']} 项"
    )
    lines.append("")
    if r["reasons"]:
        lines.append("## 判定依据")
        for x in r["reasons"]:
            lines.append(f"- {x}")
        lines.append("")
    lines.append("## 逐项结果")
    lines.append("")
    lines.append("| 配料 | 命中 | 等级 | 类别 | 说明 |")
    lines.append("|---|---|---|---|---|")
    for it in flatten(r["ingredients"]):
        name = it["name"]
        if it.get("match_type") == "fuzzy":
            name = f"{it['original_name']} → {it['name']}（疑似）"
        hit = "是" if it.get("matched") else "否"
        lvl = it.get("safety_label") or UNMATCHED_LABEL
        cat = it.get("category") or "—"
        desc = (it.get("function_desc") or it.get("misconception") or "").replace("|", "\\|")
        if len(desc) > 60:
            desc = desc[:60] + "…"
        lines.append(f"| {name} | {hit} | {lvl} | {cat} | {desc or '—'} |")
    lines.append("")
    lines.append(
        "> 判定为规则引擎结果，基于随包知识库，非医疗或营养建议；"
        "未收录成分不做任何安全推断。"
    )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="按知识库逐项判定配料表，给出购买档位（离线、纯规则）"
    )
    ap.add_argument("--text", help="配料表原文，如 '水、白砂糖、柠檬酸'")
    ap.add_argument("--file", help="从文件读取配料表文本（UTF-8）")
    ap.add_argument("--type", default="food", choices=sorted(VALID_TYPES), help="品类")
    ap.add_argument("--mode", default="general", choices=["general", "child", "allergy"],
                    help="人群模式")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    ap.add_argument("--kb-report", action="store_true", help="打印知识库统计")
    args = ap.parse_args(argv)

    if args.kb_report:
        print(json.dumps(kb_report(), ensure_ascii=False, indent=2))
        return 0

    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    if not text:
        ap.error("必须提供 --text 或 --file（或使用 --kb-report）")

    result = run(text, product_type=args.type, mode=args.mode)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
