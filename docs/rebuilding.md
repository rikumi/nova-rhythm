# 从本地游戏资源重建与继续分析

## 两种构建

`npm ci && npm run build` 直接构建已收录的网站，不需要游戏。研究脚本和参考文件不进入网页构建产物。

`scripts/rebuild.py` 从自己的游戏目录重新解码音乐，生成独立的 `public` 暂存目录。它只依赖仓库中的参考记录、现有网页图片/布局，以及自己的游戏文件，不依赖作者机器上的 `data/`、`music/`、`.local/`、Telegram 下载目录或工作记忆。

参考包记录了 1,128 条原始/补充/随机分支记录（包含排除项）、533 个已分析的 PCM 内容身份及快照建立时选用的 446 个音频身份。它是版本快照，不是当前收录或新版本曲目数量的上限；当前展示以 `public/data/story-melodies.json` 和秘纹清单为准。

## 准备环境

推荐 Windows、Python 3.14、Node.js 24；纯网站构建和参考数据测试可在 Linux 运行。已验证使用 vgmstream r2168。游戏目录需保留：

```text
游戏目录/
  xtlr_Data/StreamingAssets/InstallResource/
    txtp/*.txtp
    txtp/wem/*.wem                 # 以配方实际引用为准
    disc_*.unity3d
  Persistent_Store/
    SoundBanks/
      txtp/*.txtp
      Media/*.wem
      *.bnk
    AssetBundles/
      audio.unity3d
      disc_*.unity3d
```

重建入口读取两套现有解包 TXTP，并补充仓库中冻结的缺失状态配方；它不负责下载安装游戏或自动解密所有版本的配置表。原始 BNK 没有解包成 TXTP 时，需先用 [wwiser](https://github.com/bnnm/wwiser) 在游戏目录以外生成配方，或参考本仓库提供的配方。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

从 [vgmstream 官方 Release](https://github.com/vgmstream/vgmstream/releases) 下载适合平台的 CLI。Windows 解压到 `tools/vgmstream/`，保留配套 DLL，得到 `tools/vgmstream/vgmstream-cli.exe`。二进制工具不提交仓库。其他位置通过 `--vgmstream "路径"` 或 `VGMSTREAM_CLI` 指定。FFmpeg 默认使用 `imageio-ffmpeg` 自带版本，可通过 `--ffmpeg` 指定。

## 扫描与生成

以下所有 Python 命令均建议使用虚拟环境中的解释器。路径有空格时加引号。

```powershell
.venv\Scripts\python.exe scripts/rebuild.py --game-dir "D:\TapTap\PC Games\733498" --scan-only
.venv\Scripts\python.exe scripts/rebuild.py --game-dir "D:\TapTap\PC Games\733498" --selected-only
```

`--selected-only` 每个已选 PCM 身份优先解码一条已有路线，同时检查新路线及改动过的本地 TXTP。去掉此参数可解码全部有效路线，以检查别名、循环和字段变体。文件名和 Wwise 状态中的 transition 都会被排除；可选组合展开为明确分支，同时保留原配方的完整编排。注意 TXTP 的 `-R2>-` 表示顺序播放该组全部片段，并非运行时随机抽取，不能只导出单个分支而丢弃完整编排；语义见 [vgmstream 官方说明](https://github.com/vgmstream/vgmstream/blob/master/doc/TXTP.md#pseudo-random-groups)。单条配方组合超过 512 个时，会记录需要人工选用的错误。

每次运行重新计算依赖音频的 SHA-256；配方、源文件内容、解码器或编码参数变化都会使相关缓存失效。已完成的 FLAC 和 Opus 也会核对内容指纹。失败项保留在报告中并返回非零退出码；其余曲目仍可继续处理。默认并发数为 4，可用 `--jobs` 调整。

默认产物：

| 路径 | 内容 |
| --- | --- |
| `.build/import/inventory.json` | 扫描结果、字段、配方与排除/错误状态 |
| `.build/import/catalog.json` | 每条实际处理的路线、音频参数、PCM 身份与渲染键 |
| `.build/import/cache.json`、`lossless/` | 可恢复的解码缓存与 FLAC |
| `.build/import/pending_annotations.json` | 未知曲名、活动或新秘纹的待标注项 |
| `.build/import/report.json` | 数量、缓存命中及错误 |
| `.build/site/public/` | 可供 Vite 使用的网站资源与 JSON |

自定义位置：

```powershell
.venv\Scripts\python.exe scripts/rebuild.py `
  --game-dir "E:\Games\星塔旅人" `
  --work-dir .build/update-cache `
  --output .build/update-site/public `
  --selected-only

$env:NOVA_PUBLIC_DIR = ".build/update-site/public"
$env:NOVA_DIST_DIR = ".build/update-site/dist"
npm run build
npm run preview
```

`NOVA_PUBLIC_DIR` 用于开发与构建；`NOVA_DIST_DIR` 控制构建和预览目录。移除这两个环境变量即可恢复普通构建。重建脚本拒绝直接写入仓库的 `public/`，也拒绝输出目录与游戏目录包含彼此。检查生成结果后，再自行将需要发布的资源同步到 `public/`、提交并部署；不会自动提交新的音乐。

重建时复用仓库现有的游戏 UI、字体、已知秘纹差分布局和图片。新秘纹若能从本地 Wwise `outfit_编号` 状态识别，会直接从对应 `disc_编号.unity3d` 提取封面、分层图片及原生预制体变换；缺少故事/名称/活动时保持空值或原始标识，记录待标注，不猜活动日期。新版本若修改已知秘纹的布局或 UI，可使用下文的高级脚本重新提取；普通增量入口不会擅自覆盖已审核的布局参数。

## 命名、活动和选用

现有网站 JSON 是已审核的展示元数据，`references/analysis/` 保留其推导依据。自动导入只有在 PCM 身份一致时复用已有曲名和活动，不因文件名相似就认定内容相同。未匹配曲目默认显示原始 TXTP 文件名，按原始 Bank 分组；`--raw-names` 可关闭已知音频的中文曲名和活动复用，便于检查原始字段。

复制 `references/annotations.example.json` 到 `references/annotations.json`，按实际需要删除示例条目并填写。后者默认忽略，可自行选择提交哪些标注。也可用 `--annotations 路径` 指定一个可提交的 JSON。键为 `audio-完整PCM哈希`，例如：

```json
{
  "tracks": {
    "audio-这里填写64位PCM哈希": {
      "title": "已确认的曲名",
      "group": {
        "id": "activity-12345",
        "name": "已确认的活动名称",
        "date": "2027-01-01T12:00:00+08:00"
      }
    }
  },
  "outfits": {}
}
```

`exclude: true` 可排除一个内容身份。`outfits` 以秘纹资源编号为键，允许补充名称、故事、收录语、人物、属性标签及 `activity`。只有明确填写的新秘纹首次推出活动会增加置顶引用；不会因在某活动复用了相同音乐就关联所有旧秘纹。日期采用 ISO 8601，未知留空，置于最后。

故事旋律默认不自动收录小于 60 秒的音频；甜心梦工坊通过核心映射的 `minimum_duration_seconds: 0` 保留短曲，秘纹核心/凯旋旋律也保留短曲。相同 PCM 在故事旋律中合并为一首，别名保留供搜索；属于秘纹的内容优先出现在秘纹页。`references/selection.json` 保存原始选用规则、每个 PCM 身份的 `selected` 和对应路线。`--selected-only` 同时遵循该快照和当前核心映射明确收录的曲目；要重新审视所有未选路线，应去掉此参数。

诊断某一条路线可重复传入 `--route 路线ID`。例如：

```powershell
.venv\Scripts\python.exe scripts/rebuild.py --game-dir "D:\TapTap\PC Games\733498" `
  --route install-6ee3de95624f --raw-names `
  --work-dir .build/smoke --output .build/smoke-site/public
```

这会生成部分曲目的测试网站，不应覆盖整站数据。

## 参考记录的含义

`references/txtp/` 内的 `{{GAME}}` 是路径占位符。它由重建器替换为自己的游戏路径后，写入工作目录的配方副本，再交给 vgmstream；不能直接把这些模板当作已解析 TXTP。`routes.json` 记录模板指纹、原文件名、原来源指纹、WEM/事件/状态和随机分支信息。参考包不包含游戏 WEM/BNK、解码缓存或个人绝对路径。

主要证据表：

- `analysis/catalog.json`、`content_groups.json`：播放路线、PCM 身份、用途、循环及归属依据。
- `analysis/fields.json`、`wwise_objects.json`、`wwise_event_states.json`：状态字段与事件设置链。
- `analysis/music_localization.json`、`library_catalog.json`：状态中文、角色与活动映射及不确定项。
- `analysis/story_music_calls.json`、`config_music_usages.json`：故事集/章节候选和调用位置。
- `analysis/outfit_activity_order.json`：秘纹首次已知推出活动与日期依据。
- `analysis/artwork.json`、`card_motion.json`：秘纹资源来源、分层及原生视差参数。
- `analysis/native_*`、`phonograph_hardware.json`、`home_native_icons.json`：原生按钮、粒子、唱机固定元素和首页图标参数。
- `name_hints.json`：用户提供的既有导出文件名，仅作为命名线索，不作音频内容身份依据。

社区配置和 Lua 镜像来自 `AutumnVN/StellaSoraData`、`MakoStar/ss-lua`，原下载修订分别为 `8ed2aaf`、`19a437e`。固定来源见 `references/sources.json`。镜像不保证与自己本地版本完全同步；故事首次出现为启发式候选，跨故事线的绝对首次发布时间未完全证实。

## 高级：重新运行原始研究脚本

这些脚本暴露原始分析过程，依赖具体版本的 Unity 字段和镜像表结构；版本变化时可能需要调整。基础增量导入无需运行本节。请先创建隔离目录，再设置路径，避免将研究中间文件写回当前网站。

```powershell
.venv\Scripts\python.exe scripts/bootstrap_analysis.py --game-dir "D:\TapTap\PC Games\733498"
.venv\Scripts\python.exe scripts/fetch_sources.py
$env:NOVA_GAME_DIR = "D:\TapTap\PC Games\733498"
$env:NOVA_WORK_DIR = "$PWD\.build\analysis"
$env:VGMSTREAM_CLI = "$PWD\tools\vgmstream\vgmstream-cli.exe"
```

`fetch_sources.py` 按记录的修订下载配置与 Lua 到隔离目录；`--only tables` 或 `--only lua` 可分别获取。切换新镜像修订前，应明确更新 `references/sources.json` 并记录版本依据，而非默默追踪最新分支。

按依赖顺序运行：

```powershell
.venv\Scripts\python.exe scripts/inventory.py
.venv\Scripts\python.exe scripts/extract_wwise.py
.venv\Scripts\python.exe scripts/extract_event_states.py
.venv\Scripts\python.exe scripts/extract_ui_audio.py
.venv\Scripts\python.exe scripts/extract_artwork.py
.venv\Scripts\python.exe scripts/expand_variants.py
.venv\Scripts\python.exe scripts/export_audio.py
.venv\Scripts\python.exe scripts/analyze.py
.venv\Scripts\python.exe scripts/prepare_web.py
.venv\Scripts\python.exe scripts/prepare_library.py
```

`bootstrap_analysis.py` 提供已记录的补充状态 TXTP 与必要参数。若在隔离目录的 `data/generated/version*` 中重新生成了版本配方，可运行 `supplement_outfit.py` 更新补充路线，再重新展开、解码和分析。`analyze.py` 的表名和中文规则保留原始研究逻辑，未知状态保留原值供后续标注；不把未知活动随意映射到某角色。

原生 UI 与字体可以继续提取：

```powershell
.venv\Scripts\python.exe scripts/extract_web_ui.py
.venv\Scripts\python.exe scripts/extract_phonograph_hardware.py
.venv\Scripts\python.exe scripts/extract_note_texture.py
.venv\Scripts\python.exe scripts/extract_card_motion.py
.venv\Scripts\python.exe scripts/prepare_home.py
.venv\Scripts\python.exe scripts/subset_fonts.py
.venv\Scripts\python.exe scripts/validate_catalog.py
```

提取 UI 音效使用 `extract_ui_sounds.py`，需要 wwiser；`WWISER_PYZ` 可指定其路径，默认读取版本资源 `txtp/wwiser.pyz`。生成的配方和声音仍写到隔离目录。`repair_ui_sounds.py` 用于修复旧导出记录。

高级脚本输出的 `public/` JSON 含研究阶段的 FLAC 路径，不能直接代替正式网站资源。请将核实的命名/活动写入增量入口的标注文件，或审阅后更新正式展示 JSON；再运行基础重建入口完成 Opus 与网站清单生成。更新原生 UI 时需一并审阅相关图片及 `nativePhonograph.ts` 的改动。

重新整理参考快照可使用 `snapshot_references.py`，输入是完整的原始研究工作区，输出为仓库 `references/`；它不会由普通增量导入自动调用。应在确认分析、选用结果和来源版本后手动运行并审阅 diff。

## 核对与恢复原生秘纹图层

原生图层按游戏的 `_G` 预制体引用提取。部分版本资源省略了组件类型描述，`native_typetrees.py` 会从常驻及版本资源中寻找脚本标识、序列化结构哈希完全一致的描述，并验证读取长度。图片名称可能只有 `bg`、`01`、`title` 等，不能按编号前缀过滤；`ImageWarp` 等特殊 Image 组件也必须保留。

已有 `assets/outfit/<编号>/manifest.json` 后可运行：

```powershell
python scripts/recover_native_layers.py
```

此脚本核对全部秘纹，保留其它文本与音乐字段，仅修复原生图层布局和缺失图片。导出的 WebP 保留原始分辨率并使用无损编码；布局、源文件哈希和图片哈希记录在 `references/native-layer-recovery.json`。若有无法解析的组件，停止更新清单，避免将缺失图层误判为静态秘纹。游戏目录始终只读。

## 验证

```powershell
python -m unittest discover -s scripts/tests -v
npm run build
```

测试覆盖路径保护、TXTP 迁移、transition 状态过滤、明确随机分支、PCM 合并、短曲规则、已知秘纹及首次活动引用、原始名称回退和参考配方指纹。发布流水线也会运行参考数据测试。大型解码缓存、游戏文件、工具二进制、下载目录、上游全量镜像、截图和个人工作记录继续被忽略。
