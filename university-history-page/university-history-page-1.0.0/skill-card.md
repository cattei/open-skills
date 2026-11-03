## Description: <br>
高校发展史图谱：把一所中国高校的百年变迁，渲染成一个能双击打开的自包含 HTML 单文件。输出一条按年排序的总览时间轴，外加校名演变、校址变迁、隶属变更、校长更迭、学科建设、学科评估、政策影响七个分层维度，以及学院设置、学位点、专业设置三张表。页面不联网、不引 CDN、不加载外部字体，断网可看、可发给别人、可直接归档或打印。全量索引收录 3016 所高校，随包带 142 所重点高校（985 / 211 / 双一流）的完整发展史数据。 <br>

No bundled credential, external API key, or network access is used. The renderer runs offline on the Python standard library only; the data ships inside the skill. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
Proprietary. Commercial terms are defined by the publisher. <br>

## Use Case: <br>
Used by candidates and parents, education researchers, university staff and content producers when they want to see how a Chinese university actually came to be: "what was this school called before", "when did it move", "who were its presidents", "how did the 1952 department reshuffle affect it", "is it the product of a merger or independent growth". The output is a single deliverable page rather than a lookup answer — it can be emailed, embedded, printed or archived without any runtime. It is also used to observe one dimension in isolation (presidential turnover cadence, the reach of a national policy) instead of hunting through a mixed timeline. <br>

### Deployment Geography for Use: <br>
Global. Data covers all 3016 mainland-China higher-education institutions at index level; full development history ships for 142 of them (985 / 211 / Double First-Class). Rendering happens locally with no regional service dependency. <br>

## Known Risks and Mitigations: <br>
Risk: Missing data is read as fact. <br>
Mitigation: The source data has real gaps (year unknown / degree level to be confirmed / tenure unknown). Every gap is labelled as a gap; nothing is inferred or filled in. `selftest.py` carries invariants that fail the build if a placeholder is silently replaced by a guess. <br>

Risk: Years invented for discipline evaluations. <br>
Mitigation: The source only records an evaluation round ("第 N 轮"), never a year. The left column renders the round, not a year — public knowledge is never written into the page as if it were source data. <br>

Risk: Duplicate presidents flood the timeline. <br>
Mitigation: The source carries 2–3 duplicate records per tenure (41.5% overall duplication) and incumbents are re-appended year by year. Records are de-duplicated at build time on (name, start year, end year, normalized office) and open tenures are merged; `selftest.py` asserts zero duplicates and zero multi-tenure conflicts. <br>

Risk: A school-name match resolves to the wrong institution. <br>
Mitigation: Chinese university names contain many containment relations ("安徽大学" vs "安徽大学（xx）"). Resolution order is exact name → historical name → shortest containment match, and `--search` lets the user verify the uid first. <br>

Risk: Users assume full coverage for every school. <br>
Mitigation: The index holds 3016 schools but only 142 have full data. Non-featured schools render an explicit degraded page stating that the full dataset is not bundled — never a page that pretends to have data. `--list` marks coverage with ★. <br>

Risk: The single file is mistaken for live data. <br>
Mitigation: The footer states the generation time and the data source, and says how to regenerate. <br>

## Reference(s): <br>
Data source: the publisher's own university-history project (`software/src/data/`, 24 JSON files structured from Ministry of Education institution records and institutional histories). Generator `scripts/build-data.py` builds the compact two-tier dataset; renderer `scripts/render.py` produces the self-contained page; `scripts/selftest.py` runs 6 cases plus 10 invariants. The online counterpart (a Neo4j + Next.js multi-school relationship graph) shares the same data source. No external service is called at runtime. <br>

## Skill Output: <br>
**Output Type(s):** [html page, tables, structured data] <br>
**Output Format:** [A single UTF-8 `.html` file, typically 40–65 KB, containing a navy gradient header, a fact card, a name-evolution chain, a master timeline and seven dimension blocks; or a `--json` summary with uid, coverage flag, per-dimension counts and timeline node count] <br>
**Output Parameters:** [Driven by the institution (uid or name) and output path; `--list` browses the index, `--search` resolves a name to a uid, `--json` emits the machine-readable summary] <br>

## Skill Version(s): <br>
1.0.0 <br>

## Ethical Considerations: <br>
University history touches real people and political movements, so the failure mode to avoid is invention dressed as scholarship. Where the record is silent the page stays silent and says so — a blank field is honest, a plausible guess is not. The skill presents historical facts only: it does not rank institutions, predict admission odds, or advise on applications. Wording follows the source material rather than editorializing. The bundled data is public Ministry of Education institution information and institutional histories, with no personal, family or health data. Attribution is to the publisher (酷乐猫), and the page always states its generation date so readers can judge currency for themselves. <br>
