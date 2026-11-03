## Description: <br>
知识图谱 RAG 落地方案：面向企业级知识问答与多跳关系推理需求，按文档量自动分档，产出六阶段实施计划、里程碑验收表、六项关键工程设计、成本与容量预估、风险矩阵。强制「评估集先行」「检索不到就拒答」两条军规，并把解析质量、实体消歧、权限穿透、图谱腐化设为硬门禁。 <br>

No bundled credential, external API key, or network access is used. The plan generator runs offline on Python standard library only. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
Proprietary. Commercial terms are defined by the publisher. <br>

## Use Case: <br>
Enterprise teams and agent operators use this skill to scope, schedule and budget a knowledge-graph RAG deployment before writing code. It converts a raw requirement ("we want a knowledge base that answers questions") into a stage-by-stage plan with acceptance metrics, cost estimates and non-negotiable gates, so that projects avoid the four common failure modes: developing without an evaluation set, skipping entity resolution, letting document updates corrupt the graph, and permission leakage through multi-hop traversal. <br>

### Deployment Geography for Use: <br>
Global. Hardware and pricing figures are stated in CNY and assume China-mainland cloud pricing; adjust for other regions. <br>

## Known Risks and Mitigations: <br>
Risk: Cost figures are extrapolated from experience values, not measured. <br>
Mitigation: The plan always states that actual cost must be measured in stage 2.1 on a 100-document sample before full ingestion; the generator labels every figure as a range. <br>
Risk: Schedule tiers assume the team can staff the roles named in each stage. <br>
Mitigation: Stage 0 requires naming an owner per step; if roles cannot be staffed, the plan should be rescoped rather than compressed. <br>
Risk: Users may skip gates to save time. <br>
Mitigation: Gates are emitted as hard blockers in the output, and the three army rules are non-removable. <br>
Risk: Recommendation assumes LightRAG; other engines differ. <br>
Mitigation: Engineering notes describe which design is engine-agnostic (entity resolution, lifecycle, permissions, routing) and which is LightRAG-specific (cache, incremental insert). <br>

## Reference(s): <br>
Based on the LightRAG (HKUDS) open-source project and the published LightRAG / GraphRAG evaluation literature. Component list and version guidance are included in `references/engineering.md`. No external service is called at runtime. <br>

## Skill Output: <br>
**Output Type(s):** [text, plan documents, tables, guidance] <br>
**Output Format:** [Markdown plan with eight sections, or the same structure as JSON for project-management import] <br>
**Output Parameters:** [Driven by three inputs: document count, target scenario, and whether multi-level security applies.] <br>

## Skill Version(s): <br>
1.0.0 <br>

## Ethical Considerations: <br>
Plans involving access control must be validated with cross-permission multi-hop attack cases before launch; a plan alone does not prove an implementation is secure. Cost and schedule are estimates and must not be presented to stakeholders as commitments. Knowledge-graph answers should carry citations, and a refusal is a valid outcome — never fabricate an answer to appear helpful. <br>
