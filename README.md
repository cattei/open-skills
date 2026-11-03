# skillhub — Skill 分发目录

> 本目录存放**从 open-project 分割出来的 skill**。
> open-project 只放项目；能做成 skill 的能力迁到这里，两边都干净。

## 目录约定

```
skillhub/
└── <slug>/
    ├── <slug>-<version>/            解包后的内容，可直接用
    │   ├── SKILL.md                 入口（frontmatter 必须含 slug/name/version/description）
    │   ├── skill-card.md            技能卡（11 段，见下）
    │   ├── assets/icon.svg|png      1024×1024
    │   ├── references/              长文，按需读
    │   └── scripts/                 可执行脚本
    ├── <slug>-<version>.zip         分发用压缩包（zip 根为 <slug>/）
    └── backups/
        └── <slug>-<version>-<时间戳>/   历史版本（覆盖前自动备份）
```

**zip 根必须是 `<slug>/`**，不能是内容直接铺在根。现有 `universal-search` / `medbefore-after-case` 都遵循这条，安装器按此解包。

## 现有 skill

| slug | 版本 | 说明 | 状态 |
|---|---|---|---|
| `universal-search` | 2.0.0 | 全网真相调查 | 2026-11-03 收口为无凭证版本 |
| `kg-rag-plan` | 1.0.0 | 知识图谱 RAG 落地方案 | **本规范首个**，2026-10-29 |
| `spec-kit` | 1.2.0 | 规格驱动开发（13 阶段）+ AI+XP 结果验收 | 2026-11-02 重打包 |
| `ingredient-check` | 1.0.0 | 配料表判定（五档购买建议，离线规则引擎） | 2026-11-02 重打包 |
| `university-history-page` | 1.0.0 | 高校发展史图谱（渲染自包含 HTML） | 2026-11-02 重打包 |

**本库为公开仓库，只放可公开发布的 skill。** `medbefore-after-case`（医美案例集，含支付宝 AI 按量付费 Pay Skill 与真实素材）及含内嵌访问令牌的历史备份已移入 `payskills/`，该目录由 `.gitignore` 排除，不上传。

`temp/` 是临时目录，不属于任何 skill，已随 `payskills/` 一并隔离。

## 发布方式

**不要手工往这里复制文件。** 从技能库真源（`open-project/0项目集规划/.skills/`）发布：

```powershell
# 预览（-Target 指向你的 skillhub 分发目录，路径按本机实际填写）
powershell -ExecutionPolicy Bypass -File publish-to-skillhub.ps1 `
  -Skill kg-rag-plan -Target "<skillhub-dir>" -DryRun

# 正式发布
powershell -ExecutionPolicy Bypass -File publish-to-skillhub.ps1 `
  -Skill kg-rag-plan -Target "<skillhub-dir>"
```

脚本行为：

1. 只发布 `registry.json` 里 `visibility=public` 的 skill（**缺省 private**，宁可漏发不误发）
2. 先跑 `validate-skills.ps1 -Publish`，凭证门禁不过就拒绝发布
3. 目标目录不得等于或嵌套在真源内（防自吞）
4. 覆盖已有版本前自动备份到 `backups/`
5. 打包时排除 `backups/` `temp/` `.sync-manifest.json`

## 技能卡（skill-card.md）格式

沿用现有 skill 的 11 段，中英混排（标题英文、正文中文可）：

```markdown
## Description: <br>
<一句话能力描述> <br>
No bundled credential, external API key, or network access is used. <br>

## Publisher: <br>
酷乐猫 <br>

### License/Terms of Use: <br>
Proprietary. Commercial terms are defined by the publisher. <br>

## Use Case: <br>
<谁在什么场景下用，解决什么> <br>

### Deployment Geography for Use: <br>
<地域限制与说明> <br>

## Known Risks and Mitigations: <br>
Risk: <风险> <br>
Mitigation: <br>

## Reference(s): <br>
<依赖的上游项目/文献，运行时是否联网> <br>

## Skill Output: <br>
**Output Type(s):** [...] <br>
**Output Format:** [...] <br>
**Output Parameters:** [...] <br>

## Skill Version(s): <br>
<版本号> <br>

## Ethical Considerations: <br>
<误用后果与必须人工复核的环节> <br>
```

每行末尾的 `<br>` 不能省，渲染依赖它换行。

## 图标规范

- `icon.svg` + `icon.png` 同源
- PNG 尺寸 **1024×1024**
- 深色方形底 + 圆角，与现有两个 skill 视觉一致
- 本机无 ImageMagick/Inkscape，用 headless Edge 渲染：

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --disable-gpu `
  --hide-scrollbars --force-device-scale-factor=1 --window-size=1024,1024 `
  --screenshot="icon.png" "file:///<html-with-img>"
```

## 发布前自查

- [ ] 无绝对路径（`C:\code\...`、`0项目集规划` 等仓库内路径）
- [ ] 无凭证（`sk-`、`api_key`、`token=`、`password`）—— 注意「LLM token」这类词不算泄露
- [ ] 无 `[私密]` 内容（家庭 / 健康 / 财务）
- [ ] 无 🔴 公司经营数据（签约数、激活率等）
- [ ] 对外署名「酷乐猫」
- [ ] 脚本在**解包后的副本**里能独立跑通（不是只在真源能跑）
- [ ] zip 根为 `<slug>/`

最后一条最容易漏：真源里跑通不代表发布物能跑，相对路径和排除规则都可能出错。

## 版本与备份

- 版本号写在 `SKILL.md` frontmatter 的 `version`，同时登记在真源的 `registry.json`
- 同版本重复发布 → 自动备份到 `backups/<slug>-<version>-<时间戳>/` 再覆盖
- 回滚：把 `backups/` 里对应目录拷回 `<slug>-<version>/`，并重新打包
- `backups/` 不参与打包，也不会被装进分发物

## 与 open-project 的关系

| 位置 | 放什么 |
|---|---|
| `open-project/` | **只放项目**（`Project-*`、`Projects-AIChat` 等） |
| `open-project/99归档/` | 不再推进的项目（代码保留） |
| `open-project/0项目集规划/.skills/` | 技能库**真源**（维护用，含内部/私有 skill） |
| **本目录** | 分割出来的**可分发 skill**（只放 `public`） |

真源与分发物是单向关系：**只能从真源发布到这里，不能反过来改这里的副本**。要改，改真源再重新发布。
