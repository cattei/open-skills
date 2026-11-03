## Description: <br>
全网真相调查：使用 WorkBuddy 原生网页搜索与正文读取能力，面向争议新闻、传闻和复杂说法执行多轮检索、原始出处追溯、来源独立性审计、反证检查、矛盾分析与动机假设比较，输出带证据链、置信度、证据缺口和证伪条件的当前最佳结论。 <br>

No external search API, bundled credential, local search script or Python dependency is used. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
Proprietary. Commercial terms are defined by the publisher. <br>

## Use Case: <br>
WorkBuddy users and agent operators use this skill to investigate conflicting narratives, verify news and rumors, reconstruct timelines, identify syndicated or non-independent sources, and compare evidence-based explanations of public actions and possible motives through WorkBuddy's native search and page-reading capabilities. <br>

### Deployment Geography for Use: <br>
Global; source coverage and legal/public-record availability vary by region and by the native search tools available in the current WorkBuddy environment. <br>

## Known Risks and Mitigations: <br>
Risk: Native web search sends queries to search and content providers. <br>
Mitigation: Do not submit secrets, private business data or personal data in search queries. <br>
Risk: Search rankings, AI summaries and automatic scores may be wrong or unsupported. <br>
Mitigation: Treat them as leads only; open original sources with native page-reading tools, preserve context, deduplicate source groups and perform counterevidence searches. <br>
Risk: Native search or page-reading tools may be unavailable or unable to access an original. <br>
Mitigation: State the limitation, downgrade affected conclusions and never claim searches that were not performed. <br>
Risk: Motive analysis can overinfer or damage reputation. <br>
Mitigation: Keep competing hypotheses, allow a no-ranking outcome, separate allegations from facts and inference, state gaps and falsifiers, and require human review before public distribution of reputation-sensitive claims. <br>

## Reference(s): <br>
Uses only the native search and page-reading tools exposed by the current WorkBuddy runtime. No separate search service is referenced. <br>

## Skill Output: <br>
**Output Type(s):** [text, investigation reports, evidence tables, source links, guidance] <br>
**Output Format:** [Claim-level reports with evidence IDs, independent source groups, counterevidence, contradictions, gaps and falsification conditions; native-search query logs.] <br>
**Output Parameters:** [Not applicable; investigation depth and stop conditions are controlled by the agent workflow.] <br>

## Skill Version(s): <br>
2.0.0 (WorkBuddy native-search edition; local release candidate) <br>

## Ethical Considerations: <br>
No investigation can guarantee absolute truth. Users should assess evidence in context, avoid treating unverified allegations as established facts, protect privacy, and obtain appropriate legal, editorial or professional review before high-impact publication or action. <br>
