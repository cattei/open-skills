## Description: <br>
配料表判定：把一段配料表文本逐项对照随包知识库（食品 376 条 / 化妆品与日用品 270 条），给出五档购买建议（推荐购买 / 可以购买 / 适量购买 / 谨慎购买 / 不建议购买），并列出每项的安全等级、功能说明、常见误解与特殊人群提示。按品类分别套用本品类法规口径（食品 GB 2760 / 化妆品安全技术规范 / 日用品本品类法规），未收录成分只报「暂未收录」，绝不编造安全结论。纯规则引擎，离线运行，同一输入永远同一结论。 <br>

No bundled credential, external API key, or network access is used. The checker runs offline on the Python standard library only; the knowledge base ships inside the skill. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
Proprietary. Commercial terms are defined by the publisher. <br>

## Use Case: <br>
Consumers, reviewers and agent operators use this skill when they want a straight answer about a product's ingredient list: "can I buy this", "what are these additives", "is this cosmetic ingredient safe", "check this ingredient list for me". Instead of asking a language model to eyeball a list of chemicals — which invites plausible-sounding invention — it matches every item against a curated knowledge base and applies a fixed, auditable rule ladder. It is also used to batch-verify ingredient lists, or to look up one ingredient's safety level, legal basis and usage limit. The output separates "this ingredient is not in our database" from "this ingredient is listed but its toxicity grade is unconfirmed", so a gap in coverage is never mistaken for a safety verdict. <br>

### Deployment Geography for Use: <br>
Global. Regulatory bases are China-mainland (GB 2760 for food, 《化妆品安全技术规范》 for cosmetics); for other jurisdictions the knowledge base entries and their stated bases must be replaced, not reinterpreted. <br>

## Known Risks and Mitigations: <br>
Risk: A user treats the purchase advice as medical, nutritional or regulatory clearance. <br>
Mitigation: Every output ends with an explicit disclaimer that it is a rule-engine reading of ingredient data, not medical, nutritional or compliance advice; the advice is phrased as a purchase tier, never as a safety guarantee. <br>

Risk: Zero matches are misread as "safe to buy". <br>
Mitigation: Zero-match inputs never return the top tier for food unless the parsed names are credible and free of label residue, and never for non-food. The output states the blind spot and the unmatched count explicitly. <br>

Risk: A knowledge-base gap looks like a safety conclusion, or a listed-but-unconfirmed entry looks like a gap. <br>
Mitigation: The two unlisted states are distinct by contract — "暂未收录" (absent from the database) versus "已收录 · 等级待确认" (present, grade not yet confirmed because the standard is a permitted-use whitelist without toxicity grading). Unmatched items carry no safety level at all. <br>

Risk: Cross-category contamination — a GB 2760 food limit applied to a cosmetic ingredient, or the reverse. <br>
Mitigation: The product type is a required input; each category reads its own safety column and its own regulatory basis, and the skill refuses to fall back to the food column for non-food items. <br>

Risk: Fuzzy matching silently substitutes a different, riskier ingredient (e.g. 植物油 matched to 氢化植物油). <br>
Mitigation: Fuzzy matching requires both high similarity and comparable length, and every fuzzy hit is labelled "疑似：原名 → 标准名" so the substitution is visible rather than silent. <br>

Risk: English INCI lists match nothing because of case differences. <br>
Mitigation: ASCII aliases are upper-cased on both index and query sides; Chinese names are left untouched. <br>

## Reference(s): <br>
Regulatory bases cited per entry: GB 2760-2024《食品安全国家标准 食品添加剂使用标准》 for food; 《化妆品安全技术规范》 and the INCI/COSING ingredient dictionaries for cosmetics. The bundled knowledge base is a curated subset, not the full standard — its exact coverage is reported by `--kb-report`. Judgment rules mirror the open-source backend of the publisher's own ingredient-analysis project (matcher / recommender / label constants). No external service is called at runtime. <br>

## Skill Output: <br>
**Output Type(s):** [text, tables, structured data, guidance] <br>
**Output Format:** [Markdown report with a verdict header, reasons list and per-ingredient table; or the same structure as JSON for programmatic use] <br>
**Output Parameters:** [Driven by three inputs: the ingredient text, the product type (food / daily / cosmetic) and the population mode (general / child / allergy).] <br>

## Skill Version(s): <br>
1.0.0 <br>

## Ethical Considerations: <br>
Food and cosmetic choices affect health, so the failure mode to avoid is confident invention: an ingredient that is not in the database must be reported as unknown, never assigned a plausible-sounding grade. The two unlisted states exist precisely so that "we have no data" and "the standard permits it but does not grade it" are not conflated. Coverage is finite and must be stated as such — a clean verdict on a product whose ingredients are largely unmatched is a verdict about the database, not about the product. The advice is a purchase tier, not medical, nutritional or regulatory clearance, and the output says so every time. Where a verdict rests on a legal limit, the standard and its date are named so the reader can check the source. <br>
