# 星塔旋律

《星塔旅人》的网页音乐播放器：秘纹差分、唱机、秘纹故事，以及按活动整理的故事旋律。移动端支持设备角度视差。网站：<https://xtxl.rkm.mx/>。

## 运行网站

需要 Node.js 24。

```powershell
npm ci
npm run dev
```

```powershell
npm run build
npm run preview
```

`public/` 已包含网站运行所需的图片、字体、音效、Opus 和 JSON；普通构建不需要游戏目录、Python 或分析缓存。推送到 `main` 后，GitHub Actions 将 `dist/` 部署到 GitHub Pages。原尺寸秘纹 PNG 与 Sharp 三维对象存放于本仓库的 `site-assets` 分支，通过引用分支名的 GitHub Raw 地址加载，不打包进 Pages。3D 支持情况仅由清单决定；未缓存的模型需点击秘纹右下角、下载按钮左侧的立方体按钮加载，括号内显示压缩文件大小。有对应本地模型缓存时，打开或切换到该秘纹会自动开启 3D。不接受参数或本地开关记录。加载时显示静态图和居中提示。详见 [Sharp 资源说明](docs/sharp-scenes.md)。

## 从自己的游戏目录增量生成

详细操作、依赖安装、标注格式与高级分析步骤见 [重建与分析指南](docs/rebuilding.md)。例如，在安装 Python 依赖并准备好 vgmstream-cli 后：

```powershell
python scripts/rebuild.py --game-dir "D:\TapTap\PC Games\733498" --scan-only
python scripts/rebuild.py --game-dir "D:\TapTap\PC Games\733498" --selected-only
```

默认输出目录实际为 `.build/site/public`，预览默认生成结果：

```powershell
$env:NOVA_PUBLIC_DIR = ".build/site/public"
npm run dev
```

工具只读游戏目录，在 `.build/` 内写入配方副本、无损导出、缓存、待标注清单和网站资源。已有曲目通过解码后的 PCM SHA-256 识别，复用现有标注；未知曲目使用原始 TXTP 文件名，未知秘纹使用 `outfit_编号`。不要求人工或 AI 先完成全部命名。

## 仓库内容

日常调整故事集、日期、曲名、描述和音频收录，只需编辑 [`public/data/story-melodies.json`](public/data/story-melodies.json)。详见[故事旋律编辑说明](docs/story-melodies.md)。

| 路径 | 用途 |
| --- | --- |
| `src/`、`public/` | 当前网站源码与运行资源 |
| `references/routes.json`、`references/txtp/` | 可迁移的 TXTP、原始名称、事件、字段及来源指纹 |
| `references/selection.json` | 音频内容身份、选用情况、对应播放路径及筛选规则 |
| `references/analysis/` | 活动/角色映射、剧情调用、首次出现候选、Unity/Wwise 与差分/UI 参数证据 |
| `references/name_hints.json` | 既有导出名称线索；不含个人下载路径，不用于有损音频比对 |
| `references/sources.json` | 社区配置与 Lua 镜像的来源和固定修订 |
| `scripts/rebuild.py` | 扫描、随机分支展开、解码、PCM 去重、增量缓存及网站生成 |
| `scripts/extract_*.py`、其他分析脚本 | 配置、音频、差分、原生 UI 的研究工具 |
| `docs/rebuilding.md` | 可复现操作与标注说明 |

剧情首次出现为配置与脚本推导的候选，跨故事线的绝对首次发布时间未完全核实；名称线索、配置镜像和本地资源证据分别保留。未确认的字段数值不推断为阶段或难度。

版权归属：上海悠星网络科技有限公司。本项目与悠星网络无关。
