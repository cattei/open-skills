#!/usr/bin/env python3
"""kg-rag-plan: 按文档量分档，产出 KG-RAG 落地排期、存储建议与强制卡点。

用法：
    python plan.py --docs 3000 --scene "售后技术问答" --multi-level-security
    python plan.py --json --docs 800
    python plan.py            # 问答模式

只依赖标准库。
"""

import argparse
import json
import sys
from datetime import date, timedelta

# Windows 下 stdout 默认 GBK，¥ 等字符会触发 UnicodeEncodeError。
# 统一强制 UTF-8，避免管道/重定向时崩溃。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# --- 排期档位（周） ---------------------------------------------------------
# 源方案：<1000 份 8-10 周 ｜ 1000-5000 份 10-12 周 ｜ >5000 份 12-14 周
# 总周期 = 7 + 阶段2周数，故 p2 = 2/4/6 对应 9/11/13 周，均落在区间中位。
TIERS = [
    # (文档数上限（含）, 名称, 阶段2周数, 说明)
    (999, "小规模", 2, "阶段 2 不拆分"),
    (5000, "中规模", 4, "阶段 2 拆为 2a+2b 各 2 周"),
    (None, "大规模", 6, "阶段 2 拆为 2a+2b，另加容量预演与分批灰度"),
]

STORAGE = {
    "极简": {
        "trigger": "< 50 万 chunk",
        "spec_test": "2C / 4G / 50G SSD",
        "spec_prod": "4C / 8G / 200G SSD",
        "components": "PostgreSQL 三合一（pgvector + AGE），单容器",
        "cost_hint": "约 ¥200/月",
    },
    "标准": {
        "trigger": ">= 50 万 chunk",
        "spec_test": "4C / 16G / 100G SSD",
        "spec_prod": "8C / 16G / 500G SSD",
        "components": "Neo4j + Milvus + PostgreSQL 独立容器",
        "cost_hint": "按容器数扩容",
    },
}

# 验收线（阶段 0.6）。direction: max = 越大越好，min = 越小越好
ACCEPTANCE = [
    ("Faithfulness", 0.95, "max"),
    ("Answer Relevancy", 0.90, "max"),
    ("Context Recall", 0.85, "max"),
    ("拒答准确率", 0.90, "max"),
    ("P95 延迟(秒)", 8.0, "min"),
]

# 硬门禁
GATES = [
    "阶段 0：黄金评估集未通过评审 → 禁止进入阶段 1",
    "阶段 1：解析表格错乱率 > 5% → 先修解析管线",
    "阶段 1：实体重复率 > 8% → 调消歧管线或换更强抽取模型",
    "阶段 2：Context Recall < 0.80 → 按固定顺序排查，不要乱调参数",
    "阶段 2：成本未实测 → 禁止全量入图",
    "阶段 4：影子期出现 P0 错误答案 → 禁止灰度",
]

ARMY_RULES = [
    "抽取 LLM 不许省钱",
    "没有评估集不许开发",
    "检索不到就拒答，永不编造",
]


def pick_tier(docs):
    for limit, name, p2_weeks, note in TIERS:
        if limit is None or docs <= limit:
            return name, p2_weeks, note
    return TIERS[-1][1], TIERS[-1][2], TIERS[-1][3]


def build_schedule(docs, start=None):
    """六阶段起止周，按档位拉伸阶段 2。"""
    start = start or date.today()
    _, p2, _ = pick_tier(docs)

    # (阶段, 名称, 起始周偏移, 周数)
    phases = [
        (0, "场景定义与评估集建设", 0, 2),
        (1, "数据治理与解析管线", 2, 2),
        (2, "全量建图与检索调优", 4, p2),
        (3, "应用集成与可观测", 4 + p2, 1),
        (4, "影子运行与灰度上线", 5 + p2, 2),
        (5, "持续运营闭环（长期）", 7 + p2, None),
    ]
    out = []
    for num, name, off, weeks in phases:
        row = {
            "phase": num,
            "name": name,
            "start_week": off + 1,
            "weeks": weeks,
            "start_date": (start + timedelta(weeks=off)).isoformat(),
        }
        if weeks is not None:
            row["end_date"] = (start + timedelta(weeks=off + weeks)).isoformat()
        out.append(row)
    total = 7 + p2
    return out, total


def milestones(docs, start=None):
    start = start or date.today()
    _, p2, _ = pick_tier(docs)
    m = [
        ("M1", "评估集就绪", 2, "200+ 标注 QA 对（含对抗用例），评审通过"),
        ("M2", "小样本质检通过", 4, "解析表格错乱率 < 5%，实体重复率 < 8%，优于 Naive RAG 基线"),
        ("M3", "检索达标", 4 + p2, "RAGAS 全指标达验收线，增/改/删管道跑通，图谱版本化就绪"),
        ("M4", "应用可用", 5 + p2, "API + 引用溯源 + 拒答 + Tracing + 权限防护全部就绪"),
        ("M5", "全量上线", 7 + p2, "灰度期间点踩率 < 10%，无 P0 错误"),
    ]
    return [
        {
            "id": i,
            "name": n,
            "week": w,
            "date": (start + timedelta(weeks=w)).isoformat(),
            "criteria": c,
        }
        for i, n, w, c in m
    ]


def estimate(docs):
    """成本区间。按每份文档约 1 万字、每 100 万字数百万 token 的经验值外推。"""
    words_per_doc = 10000
    total_words = docs * words_per_doc
    # 经验值：每 100 万字建图约 200-500 万 token（抽取 + 关系判断）
    tok_low = (total_words / 1_000_000) * 2_000_000
    tok_high = (total_words / 1_000_000) * 5_000_000
    # 按 ¥0.002/千 token 粗估（DeepSeek-V3 量级）
    cny_low = tok_low / 1000 * 0.002
    cny_high = tok_high / 1000 * 0.002
    return {
        "docs": docs,
        "total_words": total_words,
        "build_tokens_low": int(tok_low),
        "build_tokens_high": int(tok_high),
        "build_cost_cny_low": round(cny_low, 0),
        "build_cost_cny_high": round(cny_high, 0),
        "note": "区间按经验值外推，实际以阶段 2.1 小批量实测为准；Embedding/Rerank 另计",
    }


def storage_for(docs, words_per_doc=10000):
    chunks = int(docs * words_per_doc / 500)  # 约 500 字/chunk
    mode = "极简" if chunks < 500_000 else "标准"
    s = dict(STORAGE[mode])
    s["mode"] = mode
    s["est_chunks"] = chunks
    return s


def render(args):
    docs = args.docs
    tier, p2, tier_note = pick_tier(docs)
    sched, total = build_schedule(docs)
    ms = milestones(docs)
    st = storage_for(docs)
    est = estimate(docs)

    lines = []
    lines.append("# 知识图谱 RAG 落地方案\n")
    lines.append(f"> 文档量：{docs} 份 ｜ 场景：{args.scene} ｜ 排期档位：**{tier}**（{tier_note}）")
    lines.append(f"> 总周期：约 **{total} 周** ｜ 密级：{'多密级（必须做权限穿透防护）' if args.multi_level_security else '单一密级'}\n")

    lines.append("## 一、排期\n")
    lines.append("| 阶段 | 名称 | 起始周 | 周数 | 起始日期 |")
    lines.append("|---|---|---|---|---|")
    for p in sched:
        w = p["weeks"] if p["weeks"] is not None else "长期"
        lines.append(f"| {p['phase']} | {p['name']} | 第 {p['start_week']} 周 | {w} | {p['start_date']} |")

    lines.append("\n## 二、里程碑验收\n")
    lines.append("| 里程碑 | 名称 | 时间 | 验收标准 |")
    lines.append("|---|---|---|---|")
    for m in ms:
        lines.append(f"| {m['id']} | {m['name']} | 第 {m['week']} 周（{m['date']}） | {m['criteria']} |")

    lines.append("\n## 三、验收指标（阶段 0.6 定线）\n")
    lines.append("| 指标 | 目标 |")
    lines.append("|---|---|")
    for name, val, direction in ACCEPTANCE:
        sign = "≥" if direction == "max" else "≤"
        lines.append(f"| {name} | {sign} {val} |")

    lines.append("\n## 四、存储与硬件\n")
    lines.append(f"- 模式：**{st['mode']}**（{st['trigger']}，预估 {st['est_chunks']} chunk）")
    lines.append(f"- 组件：{st['components']}")
    lines.append(f"- 测试环境：{st['spec_test']} ｜ 生产环境：{st['spec_prod']}")
    lines.append(f"- 成本提示：{st['cost_hint']}")
    lines.append("- 模型全部走线上 API，**无 GPU 依赖**")

    lines.append("\n## 五、成本预估\n")
    lines.append(f"- 文档总量：约 {est['total_words']} 字")
    lines.append(f"- 建图 token：{est['build_tokens_low']:,} ~ {est['build_tokens_high']:,}")
    lines.append(f"- 建图成本：约 ¥{est['build_cost_cny_low']:,.0f} ~ ¥{est['build_cost_cny_high']:,.0f}")
    lines.append(f"- {est['note']}")

    lines.append("\n## 六、硬门禁（卡点是门禁，不是建议）\n")
    for g in GATES:
        lines.append(f"- {g}")

    lines.append("\n## 七、三条军规\n")
    for r in ARMY_RULES:
        lines.append(f"{ARMY_RULES.index(r) + 1}. **{r}**")

    if args.multi_level_security:
        lines.append("\n## 八、多密级附加要求\n")
        lines.append("- 检索层：对召回的每条图谱路径校验全部实体的来源文档权限，无权路径直接剪枝")
        lines.append("- 生成层：Prompt 注入用户权限范围")
        lines.append("- 测试：必须包含**跨权限多跳攻击用例**（低权限用户故意问高密级内容）")

    return "\n".join(lines)


def ask(prompt, default=None):
    hint = f" [{default}]" if default else ""
    sys.stderr.write(f"{prompt}{hint}: ")
    sys.stderr.flush()
    v = sys.stdin.readline().strip()
    return v or default


def main():
    ap = argparse.ArgumentParser(description="KG-RAG 落地方案生成器")
    ap.add_argument("--docs", type=int, help="文档份数")
    ap.add_argument("--scene", help="场景名（一个高频痛点，不要写「通用知识库」）")
    ap.add_argument("--multi-level-security", dest="mls", action="store_true", default=None,
                    help="多密级（必须做权限穿透防护）")
    ap.add_argument("--single-level-security", dest="mls", action="store_false",
                    help="单一密级")
    ap.add_argument("--no-ask", action="store_true",
                    help="禁止交互提问；缺参数直接报错退出（脚本化调用必加）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    # 脚本化/管道场景不允许挂起等输入
    interactive = sys.stdin.isatty() and not args.no_ask

    def need(value, prompt, default, err):
        if value is not None:
            return value
        if not interactive:
            sys.stderr.write(f"{err}（非交互环境，请显式传参或加 --no-ask）\n")
            sys.exit(2)
        return ask(prompt, default)

    if args.docs is None:
        d = need(None, "文档份数", "1000", "缺少 --docs")
        try:
            args.docs = int(d)
        except (TypeError, ValueError):
            sys.stderr.write("文档份数必须是整数\n")
            return 2
    if not args.scene:
        args.scene = need(None, "场景（如：售后技术问答 / 合同条款审查 / 设备故障诊断）",
                          "售后技术问答", "缺少 --scene")
        if not args.scene:
            sys.stderr.write("场景不能为空\n")
            return 2
    if args.mls is None:
        # 密级有明确默认值（单一密级）。非交互时取默认值，不阻塞脚本化调用；
        # 交互时仍会问，避免误以为单一密级而漏做权限防护。
        if interactive:
            a = need(None, "是否多密级？(y/N)", "N", "缺少密级参数")
            args.mls = str(a).lower().startswith("y")
        else:
            args.mls = False

    if args.docs <= 0:
        sys.stderr.write("文档份数必须 > 0\n")
        return 2

    args.multi_level_security = args.mls

    if args.json:
        tier, p2, tier_note = pick_tier(args.docs)
        sched, total = build_schedule(args.docs)
        print(json.dumps({
            "docs": args.docs,
            "scene": args.scene,
            "tier": tier,
            "tier_note": tier_note,
            "total_weeks": total,
            "multi_level_security": args.multi_level_security,
            "schedule": sched,
            "milestones": milestones(args.docs),
            "acceptance": ACCEPTANCE,
            "storage": storage_for(args.docs),
            "estimate": estimate(args.docs),
            "gates": GATES,
            "army_rules": ARMY_RULES,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
