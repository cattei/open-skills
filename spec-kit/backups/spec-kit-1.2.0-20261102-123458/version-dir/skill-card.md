## Description: <br>
规格驱动开发（SDD）离线落地版 + AI+XP 结果验收。从「用户场景」起手：AI 扫现有材料起草场景 → 人审核改稿 → 影响面说明文档（页面/功能/数据/整体业务流程）→ 四格验收卡 → 规格 → 计划 → 任务 → 实现 → 按卡验收回填 → 收敛，共 13 个阶段、8 张模板。不依赖 specify CLI，不使用 `.specify/scripts`。 <br>

No bundled credential, external API key, or network access is used. The context script runs offline on Python standard library only. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
MIT (inherited from github/spec-kit at commit `99e047e9b48c3ecbbc5c3e530fb45bed671960bc`, vendored 2026-10-29). Local additions (story / impact / accept / verify stages and their templates) are published under the same MIT terms. Full upstream text is in `LICENSE`. <br>

## Use Case: <br>
Product managers, engineers and agent operators use this skill to turn a vague requirement into an implementation-ready document chain before writing code. Instead of jumping from a one-line request straight to code, it forces three things that usually get skipped: a human-approved user scenario, an explicit impact statement naming every affected page, feature and data model plus the end-to-end business flow, and a four-cell acceptance card that can be verified after the fact. This makes "done" checkable rather than a matter of opinion, and keeps an auditable trail from scenario to acceptance backfill. <br>

### Deployment Geography for Use: <br>
Global. The workflow is language- and stack-agnostic; templates ship in Chinese with English stage names. <br>

## Known Risks and Mitigations: <br>
Risk: The workflow can be run as pure ceremony, producing documents that nobody reads or verifies. <br>
Mitigation: The acceptance stage is mandatory and its four cells are verifiable statements, not adjectives; the verify stage requires backfilling evidence (test output, screenshots, logs), and a stage may not be marked done without it. <br>

Risk: Users may skip the human-review step on the user scenario and let the AI approve its own draft. <br>
Mitigation: The story stage explicitly hands the draft to a human for revision before downstream stages consume it; downstream stages refuse to proceed on an unreviewed draft. <br>

Risk: Vendored upstream content drifts from the recorded commit, or local edits get overwritten on refresh. <br>
Mitigation: `VENDOR.json` records every upstream file's sha256 plus the transform rules; `scripts/vendor-sync.ps1` regenerates only the vendored part, and the skill's own rule is "do not hand-edit generated files — change the script or the SKILL.md". <br>

Risk: Impact analysis is under-specified, so later work silently touches pages or data that were never declared. <br>
Mitigation: The impact stage requires enumerating affected pages, features and data models plus the business flow; scope added later must go back through the stage rather than be absorbed silently. <br>

## Reference(s): <br>
Upstream: [github/spec-kit](https://github.com/github/spec-kit) (MIT), commit `99e047e9b48c3ecbbc5c3e530fb45bed671960bc`, vendored 2026-10-29. Upstream methodology is reproduced in `references/methodology.md`; command and template provenance plus per-file sha256 are in `VENDOR.json`. Local extensions are the `story` / `impact` / `accept` / `verify` stages and their three templates, plus `references/xp-ai-acceptance.md`. No external service is called at runtime. <br>

## Skill Output: <br>
**Output Type(s):** [text, specification documents, plan documents, task lists, acceptance cards, guidance] <br>
**Output Format:** [Markdown document chain under `specs/<NNN>-<slug>/`, plus repo-level `.specify/feature.json` and `.specify/memory/constitution.md`] <br>
**Output Parameters:** [Driven by the stage argument (`/spec-kit <stage>`) and the reviewed user scenario; the context script emits a single JSON payload describing current stage and file chain.] <br>

## Skill Version(s): <br>
1.2.0 <br>

## Ethical Considerations: <br>
The workflow is designed to make a human accountable for the requirement, not to let an agent approve its own work — the scenario must be reviewed by a person before it drives specs, and self-review is treated as invalid. Acceptance evidence must be real: a stage is not "done" because the document exists, and fabricated test output or screenshots defeats the entire purpose of the acceptance card. When the workflow is used on someone else's product or data, the impact stage must name data that is read or written, so that privacy and access consequences are visible before implementation rather than discovered after. <br>
