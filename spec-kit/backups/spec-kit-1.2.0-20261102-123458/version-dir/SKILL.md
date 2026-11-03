---
name: spec-kit
description: 规格驱动开发（SDD）离线落地版 + AI+XP 结果验收。默认从「用户场景」起手：AI 先扫现有规划/页面/代码起草用户场景，交人审核改稿，再据场景产出说明文档（影响的页面、功能、数据、整体业务流程），然后才拆验收卡（四格）、写规格、计划、任务、实现、按卡验收回填。当用户说 spec-kit、/spec-kit（不带内容）、生成项目文档、用户故事/用户场景、影响面、业务流程、验收卡、验收、写规格、技术方案、拆任务、立项，或要求"按流程做一套需求文档"时使用。含 13 个阶段、8 张模板、验收纪律与上下文脚本，不依赖 specify CLI。
license: MIT
metadata:
  author: github-spec-kit (vendored) + 0项目集规划 XP 实践（本地扩展）
  source: https://github.com/github/spec-kit
  upstream_commit: 99e047e9b48c3ecbbc5c3e530fb45bed671960bc
  vendored_at: 2026-10-29
  local_stages: story, impact, accept, verify
  version: 1.2.0
  pack: 0项目集规划/.skills
---

# spec-kit · 用户场景 → 影响面 → 验收 → 规格

## 0. 默认动作（用户不带内容时）

用户只说 `/spec-kit` 或"给这个项目做一套需求文档"时，**不要反问"你要讲哪几个场景"**，直接按默认链走：

1. **扫材料**：`0项目集规划/总规划.md`、`总执行.md`、项目 `规划/`、`docs/`、README、代码里的页面/路由/文案、已有截图。
2. **起草用户场景**（3–6 条）写进 `stories.md`，每条标**依据**与 `⚠️ 我推断`。
3. **停下交审**：给一份"待审清单"，请用户直接改文件。**用户改完才继续**。
4. 用户改好 → `impact`：把每条场景翻成**影响的页面 / 功能 / 数据 / 整体业务流程**。
5. 再 `accept`（四格验收卡）→ `specify` → `plan` → `tasks` → `implement` → `verify` → `converge`。

用户要亲口讲场景也支持：口述 > 扫出来的材料。

## 1. 文档链（这套 skill 的核心）

```
stories.md        ① 用户场景（AI 起草 → 人工审核改稿）= 需求源头
   ↓  人审通过
impact.md         ② 说明文档：影响的页面 / 功能 / 数据 / 整体业务流程（每条 U 一条流程）
   ↓
acceptance.md     ③ 四格验收卡 RAC-001…（可逐项打勾）
   ↓
spec.md → plan.md → tasks.md → implement
   ↑                                       ↓
   └── verify：回填 stories.md 实现核对 + 卡片验收记录 ←──┘
                 = 用户场景同时是验收结果
```

- 没有用户审核过的 `stories.md` 不许写 `spec.md`；没有 `impact.md` 不许拆 `acceptance.md`；没有 `acceptance.md` 不许 `implement`。
- 每条 FR 回链 `U#`；每个功能点 `F#` 由 story→impact 定义；每个缺口编号 `G#`。

## 2. 阶段地图（13 个）

```
story → impact → accept → constitution(项目一次) → specify → clarify(可选) → plan → tasks
      → analyze(可选) → checklist(可选) → implement → verify → converge → (implement…)
```

| 阶段 | 前置 | 读什么 | 产出（`specs/<NNN>-<slug>/`） |
|---|---|---|---|
| `story` | feature 目录 | `commands/story.md` | `stories.md`（口述/起草 + 页面要素 + 待确认 + 能力清单） |
| `impact` | `stories.md` 已审 | `commands/impact.md` | `impact.md`（页面/功能/数据 + 端到端流程 + 追溯） |
| `accept` | `impact.md` | `commands/accept.md` | `acceptance.md`（RAC 四格 + 验收记录） |
| `constitution` | — | `commands/constitution.md` | `<repo>/.specify/memory/constitution.md` |
| `specify` | stories + impact | `commands/specify.md` | `spec.md`、`.specify/feature.json` |
| `clarify` | `spec.md` | `commands/clarify.md` | 就地改写 `spec.md`（≤5 问答） |
| `plan` | `spec.md` | `commands/plan.md` | `plan.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md` |
| `tasks` | `plan.md` | `commands/tasks.md` | `tasks.md` |
| `analyze` | spec+plan+tasks | `commands/analyze.md` | 只读报告 |
| `checklist` | `spec.md` | `commands/checklist.md` | `checklists/<domain>.md` |
| `implement` | `tasks.md` + RAC | `commands/implement.md` | 代码 + 勾 `tasks.md` |
| `verify` | 代码 + `acceptance.md` | `commands/verify.md` | 回填验收记录 + `stories.md` 实现核对 + `G#` |
| `converge` | 代码 + spec | `commands/converge.md` | 追加 tasks 直到 `Converged` |

## 3. 什么该用 / 不该用

| 场景 | 用 |
|---|---|
| 新功能/新项目，需求模糊 | ✅ 默认：起草场景 → 人审 → impact → accept → spec… |
| 老项目补需求文档 | ✅ 扫现有页面与规划 → 起草 → 人审 |
| 要做影响面评估（动几个页面/几张表） | ✅ `impact` |
| 实现完不知道漏没漏 | ✅ `verify` + `converge` |
| 改文案 / 修明确 bug / 一次性脚本 | ❌ 直接做 |
| 用户说「别写文档，直接改」 | ❌ 照办，但记一句跳过原因 |

## 4. 上下文脚本（替代上游 `.specify/scripts/*`）

在**项目根**执行：

```bash
python .agents/skills/spec-kit/scripts/speckit_context.py --json
```

| 用途 | 命令 |
|---|---|
| 只读上下文 | `... --json` |
| 新建 feature + 一次铺全套骨架（stories / impact / acceptance / spec） | `... --json --create <short-name>` |
| 只补某张骨架 | `... --setup story` / `--setup impact` / `--setup accept` / `--setup plan` / `--setup tasks` |
| 取模板全文 | `... --template impact-template` 等 |
| 精简输出 | `... --json --paths-only` |

关键字段：`REPO_ROOT` `FEATURE_DIR` `STORIES` `IMPACT` `ACCEPTANCE` `STORIES_STATUS` `ACCEPTANCE_STATUS` `FEATURE_SPEC` `IMPL_PLAN` `TASKS` `AVAILABLE_DOCS` `CONSTITUTION_EXISTS` `TEMPLATES_DIR` `TEMPLATE_CONTENT`。

- `.agents/skills` 是投影；找不到就用真身 `0项目集规划/.skills/spec-kit/scripts/speckit_context.py`，或跑 `0项目集规划/.skills/scripts/link-skills.ps1` 重建。
- 只依赖 Python 3 标准库；`--repo <path>` 指定项目根。

## 5. 执行规矩（硬约束）

1. **默认先起草场景，不反问"你要讲几个"**：扫材料 → 起草 → 交审。用户没审完不许往下走。
2. **用户改的文件是唯一真源**：不覆盖用户改过的段落；发现与代码矛盾就指出来，别偷偷改回去。
3. **一次只推进一步**：跑完一个阶段停下汇报路径，等确认。
4. **场景用原话/标依据**：不改写成需求术语，不写技术名，不编用户；起草的猜测必须标 `⚠️`。
5. **impact 只写"要什么"**：页面/功能/数据/流程，不写技术选型（留给 `plan`）；每条 U 必须有端到端流程含失败路径。
6. **验收标准人确认**：AI 可起草卡片，人必须确认；`verify` 时 AI 只报"我看到什么"，**不得自己把 `☐` 改成 `☑`**，人不在场写 `⏳ 待人工确认`。
7. **没证据不算验过**：跑不起来/没截图/没日志 → 先补证据再说结论。
8. **验收不过回卡片**：先判断卡片漏写还是实现错了；差距写到"哪一格/哪一条/实际看到什么"。
9. **规格不写技术选型**：`spec.md` 只写 What/Why；`[NEEDS CLARIFICATION]` ≤3。
10. **`analyze` 只读**；收尾必须报：改了哪些文件、哪些卡通过、剩哪些差距。

## 6. 模板与参考

| 文件 | 用途 |
|---|---|
| `references/templates/user-story-template.md` | 用户场景骨架（`story`） |
| `references/templates/impact-template.md` | 影响面 + 业务流程骨架（`impact`） |
| `references/templates/acceptance-card-template.md` | 验收卡四格（`accept` / `verify`） |
| `references/templates/spec-template.md` | 规格（`specify`） |
| `references/templates/plan-template.md` | 技术计划（`plan`） |
| `references/templates/tasks-template.md` | 任务清单（`tasks`） |
| `references/templates/checklist-template.md` | 需求质量清单（`checklist`） |
| `references/templates/constitution-template.md` | 项目宪法（`constitution`） |
| `references/commands/*.md` | 13 个阶段执行指令（9 上游 + 4 本地：story/impact/accept/verify） |
| `references/xp-ai-acceptance.md` | AI+XP 结果验收摘要（四格、验收动作、反模式、粒度） |
| `references/methodology.md` | 上游方法论全文 |

## 7. 与上游的差异

| 上游 | 这里 |
|---|---|
| `specify init` 生成 `.specify/` + agent skill 目录 | 只留方法论与模板；脚本用 `speckit_context.py` |
| `{SCRIPT}` → `.specify/scripts/*` | 已替换为 `speckit_context.py --json` |
| `/speckit-specify` 等 10 个独立命令 | 统一 `/spec-kit <阶段>` |
| 依赖 git 分支推编号 | 用 `.specify/feature.json` + `specs/` 序号 |
| extension hooks | 不存在即跳过 |
| `taskstoissues` | 上游已弃用，未收录 |
| 无用户场景 / 影响面 / 验收卡 | **本地新增 `story` `impact` `accept` `verify` 四阶段** |
| TDD 红绿 | **结果验收**：按四格跑页面跑业务流，不打勾不算完 |

## 8. 阶段自检

- [ ] 我读完了对应 `references/commands/<阶段>.md`
- [ ] `stories.md` 是原话/标了依据，且用户已审
- [ ] `impact.md` 四块齐全，每条 U 有端到端流程（含失败路径）
- [ ] 每张卡四格填满，②有边界/空/异常，④有失败路径
- [ ] 我没有自己给自己判"通过"
- [ ] 停下来等确认了，没有一口气跑完 5 个阶段
