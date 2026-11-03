#!/usr/bin/env python3
"""ingredient-check 自测：判定规则与边界案例。

运行：python scripts/selftest.py
退出码 0 = 全部通过。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

CASES: list[tuple[str, str, str, str, str]] = [
    # (说明, 文本, 品类, 模式, 期望档位)
    ("常规饮料含注意成分", "水、白砂糖、柠檬酸、山梨酸钾、食用香精", "food", "general", "okay"),
    ("零命中但可信（单一原料）", "天然水", "food", "general", "recommend"),
    ("零命中且全是标签噪声", "配料表、类别、厂名厂址、净含量500ml", "food", "general", "moderate"),
    ("禁用成分一票否决", "水、苏丹红", "food", "general", "not_recommended"),
    ("非食品零命中不给正面结论", "神秘成分甲、神秘成分乙", "cosmetic", "general", "moderate"),
    # 回归：括号内顿号曾被误当顶层分隔符，把复合配料撕成两个半截项。
    # 期望 okay 而非 recommend：子配料"棕榈油"是注意级，计入后档位应下调。
    ("复合配料不被括号内顿号撕裂", "小麦粉、植物油（棕榈油、大豆油）、食用盐", "food", "general", "okay"),
]


def main() -> int:
    print("=" * 68)
    print("ingredient-check 自测")
    print("=" * 68)

    report = check.kb_report()
    print(f"知识库：食品 {report['food_entries']} 条 / 非食品 {report['nonfood_entries']} 条")
    if report["food_entries"] == 0:
        print("[FAIL] 知识库为空，无法判定")
        return 1
    print()

    failed = 0
    for desc, text, ptype, mode, expect in CASES:
        r = check.run(text, product_type=ptype, mode=mode)
        got = r["level"]
        ok = got == expect
        mark = "[ ok ]" if ok else "[FAIL]"
        print(f"{mark} {desc}")
        print(f"       输入: {text}")
        print(f"       品类={ptype} 模式={mode}")
        print(f"       期望={expect}({check.LEVEL_LABELS[expect]})  实际={got}({r['level_label']})")
        if not ok:
            failed += 1
            print(f"       未收录 {r['stats']['unmatched']}/{r['stats']['total']}")
            for it in check.flatten(r["ingredients"]):
                print(f"         - {it['name']} matched={it['matched']} lvl={it['safety_level']}")
        print()

    # 结构性断言：这些不是档位，而是"绝不能发生"的事
    print("=" * 68)
    print("不变量检查")
    print("=" * 68)

    inv_failed = 0

    def invariant(name: str, cond: bool, detail: str = "") -> None:
        nonlocal inv_failed
        if cond:
            print(f"[ ok ] {name}")
        else:
            print(f"[FAIL] {name} {detail}")
            inv_failed += 1

    # 1) 未命中的配料绝不能带 safety_level
    r = check.run("神秘成分XYZ", product_type="food")
    inv = [i for i in check.flatten(r["ingredients"]) if not i["matched"]]
    invariant(
        "未命中项不得有 safety_level（禁止杜撰）",
        all(i["safety_level"] is None for i in inv),
    )

    # 2) 已收录但等级为空 → 必须显示"已收录 · 等级待确认"，不能显示"暂未收录"
    idx = check.build_index()
    pending = [d for d in idx["entries"]
               if d.get("safety_level") is None and d.get("product_types") in (None, '["food"]')]
    if pending:
        name = pending[0]["name"]
        r = check.run(name, product_type="food")
        hit = [i for i in check.flatten(r["ingredients"]) if i["matched"]]
        invariant(
            f"已收录待确认态不被误报为未收录（样本：{name}）",
            bool(hit) and hit[0]["safety_label"] == check.PENDING_REVIEW_LABEL,
            f"实际={hit[0]['safety_label'] if hit else '未命中'}",
        )

    # 3) 品类隔离：化妆品条目不得套用 GB 2760 食品等级
    r = check.run("水", product_type="food")
    food_water = [i for i in check.flatten(r["ingredients"]) if i["matched"]]
    r2 = check.run("水", product_type="cosmetic")
    cos_water = [i for i in check.flatten(r2["ingredients"]) if i["matched"]]
    invariant(
        "跨品类不串用等级（食品/化妆品各自口径）",
        (food_water[0]["safety_basis"] if food_water else "") !=
        (cos_water[0]["safety_basis"] if cos_water else ""),
    )

    # 4) 确定性：同输入两次结果一致
    a = check.run("水、白砂糖、柠檬酸", product_type="food")
    b = check.run("水、白砂糖、柠檬酸", product_type="food")
    invariant("同输入结果稳定（无随机性）", a["level"] == b["level"])

    # 5) 空文本不崩
    r = check.run("", product_type="food")
    invariant("空输入不崩溃", r["level"] in check.LEVEL_LABELS)

    # 6) 复合配料：括号内顿号不切分，子配料递归匹配
    r = check.run("植物油（棕榈油、大豆油）", product_type="food")
    tops = [i["name"] for i in r["ingredients"]]
    invariant(
        "复合配料保持完整（括号内不切分）",
        len(tops) == 1 and tops[0] == "植物油",
        f"实际顶层={tops}",
    )
    sub = r["ingredients"][0]["sub_ingredients"] or []
    invariant(
        "复合配料子项被递归匹配",
        len(sub) == 2 and all(s["matched"] for s in sub),
        f"子项={[s['name'] for s in sub]}",
    )

    print()
    total_bad = failed + inv_failed
    if total_bad == 0:
        print(f"[selftest] OK：{len(CASES)} 个案例 + 5 条不变量全部通过")
        return 0
    print(f"[selftest] FAILED：{failed} 个案例、{inv_failed} 条不变量未通过")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
