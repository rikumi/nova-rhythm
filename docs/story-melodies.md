# 直接编辑故事旋律

唯一的展示映射文件是 [`public/data/story-melodies.json`](../public/data/story-melodies.json)。网页直接读取它；改名、增删曲目、移动曲目、填写日期和描述都只需修改这个文件，然后刷新本地页面。提交并推送后，GitHub Pages 自动更新。

```json
{
  "schema_version": 1,
  "groups": [
    {
      "id": "my-story",
      "name": "故事集名称",
      "date": "2026-11-16",
      "description": "可选的故事集说明",
      "outfit_references": [],
      "tracks": [
        {
          "name": "曲目名称",
          "file": "/audio/my-song.opus",
          "description": "可选的曲目说明"
        }
      ]
    }
  ]
}
```

| 字段 | 编辑方式 |
| --- | --- |
| `groups` | 每项是一个故事集、活动或常驻玩法分组。删除整项即可移除整个分组。 |
| `id` | 故事集的稳定编号，全文件唯一；已有编号通常不需要修改。新增分组可自行取不重复的英文编号。 |
| `name` | 故事集名称或曲目名称，直接显示在页面。 |
| `date` | `YYYY-MM-DD` 或完整 ISO 8601 时间；未知写 `""`。一般分组按日期从新到旧排列，无日期排在最后，同日期保持文件顺序；显式设置 `before_group` 可指定常驻分组位置。 |
| `description` | 可选描述，空字符串不显示。故事集描述在展开后显示，曲目描述在曲名下面显示，也参与搜索。换行使用 `\n`。 |
| `tracks` | 当前故事集里的曲目，页面按数组顺序显示。删除一项即下架，移动到另一个分组即可调整归属。 |
| `file` | 实际播放的素材路径：`/audio/my-song.opus` 对应仓库 `public/audio/my-song.opus`。也可以填写支持跨域读取的 HTTPS 音频地址。 |
| 曲目中的 `id` | 可选的已有音频编号，原有条目可以保留；新增或替换素材时不需要填写它。 |
| `outfit_references` | 该活动首次推出的秘纹入口，始终排在普通曲目前。保留现有记录即可；不需要秘纹入口时写 `[]`。 |
| `minimum_duration_seconds` | 可选的自动生成时长门槛，默认 60。甜心梦工坊设置为 `0`，保留开始、不同节拍和自由演奏等短曲。 |
| `before_group` | 可选的排序锚点。常驻玩法子分类使用 `"permanent-combat"`，固定在原“常驻玩法”之前；同一锚点下按 JSON 中的分组顺序排列，原日期不会被清空。 |

添加音乐时，先将文件放入 `public/audio/`，再添加包含 `name`、`file` 的条目即可，无需填写 PCM 哈希、采样率或循环点。新文件没有分析参数时，时长先显示 `--:--`，播放后由解码器获得实际时长，并按整曲循环。已有文件仍沿用审核过的原生循环点。替换 `file` 不会继承另一个素材的循环参数。

同一素材应只收录一次；重复的文件或曲目编号会显示明确错误。删除条目不会自动删除物理音频文件，避免影响秘纹页或其他引用。

`public/data/library.json` 是程序维护的播放参数与检索证据索引，不再决定展示哪些故事集、曲目或中文名称。通常不需要手动修改它。`scripts/rebuild.py` 会读取人工映射，保留已有改名、日期、描述、曲序和移除决定，在独立的输出目录生成新的 `story-melodies.json`；新发现且未标注的音乐仍先用原始名称。重建结果需审阅后再同步回 `public/`。

```powershell
npm test
python -m unittest discover -s scripts/tests -v
npm run build
```

流水线会检查映射格式、素材引用及增删/改名行为。JSON 使用双引号，不支持注释或尾随逗号。

## 活动配乐与主秘纹去重

`references/activity-main-outfits.json` 保存通过“活动入口 → 兑换商店 → 商品 → 秘纹”链确定的主秘纹。当前 23 个活动中有 19 个商店可唯一确定主秘纹，其余没有秘纹商品，不强行指定。

`references/activity-theme-dedup.json` 保存本次扫描和筛除证据：使用本地无损 FLAC，统一为双声道 44100 Hz PCM16 后核对前 60 秒 SHA-256；完整 PCM 身份相同也可筛除。不使用网站 Opus 作内容比较，也不因旋律相似自动剔除。仅检查来源记录中属于系统配乐的条目，不将同活动的其他战斗编曲一并清除。

本次移除了“枪林弹雨覆黄沙”与“晴风碧海 · 悠哉盛夏依然打卡~”的重复活动配乐，分别保留对应主秘纹“欢聚时刻”“斑驳夏影”的核心旋律入口。若需要重新检查：

```powershell
# 先运行 rebuild.py 获得 .build/import/catalog.json 及对应 lossless/。
python scripts/deduplicate_event_themes.py
# 检查 .build/activity-theme-dedup.json 后，应用新发现的匹配：
python scripts/deduplicate_event_themes.py --apply
```

也可用 `--render-catalog` 指定其他重建缓存，或用 `--audio-root` 指定包含原始 `music/` 导出的研究目录。`--tables-dir 镜像/CN/bin` 可更新主秘纹依据，`--report` 可另存报告。缺少无损文件时报告错误，不会改写映射。默认仅生成报告；`--apply` 只修改故事旋律清单，不修改游戏或音频文件。

## 剧情顺序和名称

每个分组里的剧情曲目按章节配置顺序、同一章节脚本的 `SetBGM` 调用位置正序排列。活动分支沿用游戏 `ActivityStoryDataBase.SortStoryList` 的广度优先遍历，根节点与同级分支按配置编号排列；主线沿用配置节点顺序。不同分支没有唯一的实际游玩先后，因此这里使用固定的配置顺序。同一个分组中，其他玩法/系统音乐的位置以及置顶的秘纹入口不受影响。

标题不再使用“剧情配乐 x”前缀，也不包含对白片段。已定位场景的自动名称采用“章节 · 场景”，例如“第九章 · 引线”。去除对白后的同名曲目保留，按剧情出现顺序重新编为“第九章 · 引线 · 第1音轨”“第九章 · 引线 · 第2音轨”等；唯一名称不添加音轨序号。尚未定位章节的条目保留原始音乐状态以便区分。

`references/story-chapter-order.json` 保存章节顺序及配置来源指纹，`references/story-music-order.json` 保存每首曲目的首次出现候选、脚本行号、对白原文和排序依据。跨故事线的绝对首次出现仍以候选记录为准；在同一分组内优先采用该故事集自己的调用位置。

重新检查可运行：

```powershell
python scripts/order_story_music.py
# 核对 .build/story-music-order.json 后应用：
python scripts/order_story_music.py --apply
```

默认使用仓库中的章节顺序。需要更新镜像分析时，可加 `--tables-dir 镜像/CN/bin`，以及用于补充复核证据的 `--lua-dir 镜像/Lua/Game/UI/Avg/_cn/Config`；对白只留在分析记录，不放入展示名称。它只修改曲名及剧情项的相对顺序，保留人工填写的日期、描述和收录决定。平时直接编辑核心 JSON 即可，不需要反复运行这些分析脚本。

## 播放链接和切歌

播放普通故事曲目时，地址更新为 `/?track=音频编号#/library`。直接打开该链接会进入故事旋律、展开对应分组并选中曲目；浏览器允许时自动播放，否则点击播放按钮即可。浏览器前进/后退也可恢复相应选曲。

上一曲、下一曲按页面分组及组内曲序循环切换，仅使用 `tracks` 中的普通音乐，始终跳过 `outfit_references`，不会跳去秘纹页。单曲循环按钮控制当前曲目的循环；已有素材仍按原始循环点播放。

## QQ 音乐正式曲名

已通过 QQ 音乐接口核对“星塔唱片”（歌手 MID `001Rt7AK0ImjcV`）的 126 首曲目、20 张专辑，比较用音源保存在忽略目录 `.build/qqmusic/audio/`，不加入网页或仓库。网站继续使用游戏导出的音频。

候选由 Chromaprint 指纹检索，再通过多段独立波形验证：至少两段相关系数不低于 0.90，中位数不低于 0.92，时间偏移差不超过 80 毫秒。只有唯一、通过验证的正式曲名才会采用；名称相似或时长相同不足以改名。当前 540 段本地音频（含补充路线）中核实了 137 段，不代表每首发行曲都存在于当前游戏资源。

名称不同时使用“正式曲名（原曲目名）”，保留用户原有上下文；名称一致或已使用此格式时不重复追加。秘纹名称仍是道具本名，“核心旋律/凯旋旋律”仍是游戏按钮的功能标签；存在不同的正式录音名称时，通过 `music.display_title` 显示在播放控制中。

- `references/qqmusic-catalog.json`：完整目录、曲目/专辑 ID、发行日期和 QQ 音乐链接。
- `references/qqmusic-matches.json`：匹配候选、相似度、波形验证位置及未匹配结果。
- `references/qqmusic-name-changes.json`：本次 98 处名称更新及恢复的 27 段甜心梦工坊短曲。

重新核对需要安装 `requirements.txt`，并从 [Chromaprint 官方 Release](https://github.com/acoustid/chromaprint/releases/tag/v1.6.2) 准备 `fpcalc`。示例：

```powershell
python scripts/qqmusic_catalog.py --download
# 先使用本地游戏完成无损重建；去掉 --selected-only 可检查全部状态路线。
python scripts/match_qqmusic.py --fpcalc tools/chromaprint/你的解压目录/fpcalc.exe --render-catalog .build/import/catalog.json
# 审阅报告后保存需要保留的匹配记录，再预览改名：
python scripts/apply_qqmusic_names.py
```

匹配器默认输出 `.build/qqmusic/matches.json`；名称应用器默认读取已审阅的 `references/qqmusic-matches.json`，也可以用 `--matches` 指定报告。只有显式加 `--apply` 才会写入，原文件会备份到 `.build/qqmusic/backups/`。`--restore-cookie` 可以在同一批写入中恢复被时长筛选移除的甜心梦工坊短曲，并从无损导出生成相应 Opus。应用前应通知其他编辑者保存当前修改，应用后重新载入核心 JSON，避免旧编辑缓冲覆盖新内容；应用器也会拒绝覆盖计算期间发生的磁盘改动。

## 常驻玩法分类

星塔探索、心危擂台、真格挑战、灾变防线、猎影合围、尖兵陷阵、联合讨伐分别归类。已核实的巅峰秀场与晋升试炼也独立归类；这些分组通过 `before_group` 放在原“常驻玩法”上方。玩法音乐的判断依据包括 Wwise 状态以及关卡表 BGM 的完整字段匹配，不能仅凭旧中文标题或拼音猜测。

例如 `WeekBossFloor` 对应真格挑战、`ScoreBossFloor` 对应联合讨伐、`TravelerDuel` 对应巅峰秀场。`references/permanent-library-classification.json` 保留每次移动的来源与字段依据。

```powershell
python scripts/permanent_library.py
# 先检查 .build/permanent-preview/ 中的候选 JSON 与报告，再通知编辑者后应用：
python scripts/permanent_library.py --apply
```

这里的分类不会把内容不同的游戏片段仅因同名就强行合并。完整发行版替换需要可用于本站的完整音频；QQ 音乐下载缓存保留作比对，不作为网页发布资源。游戏原始素材与发行录音存在版本差异时，应保留来源和区别。
