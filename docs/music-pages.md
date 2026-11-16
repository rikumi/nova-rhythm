# 曲目分享页

`npm run build` 在 Vite 构建完成后调用 `scripts/build_music_pages.mjs`，为当前故事映射中的曲目和秘纹核心／凯旋旋律生成 `dist/music/<曲目 ID>/index.html`。不发布已从映射删除的曲目，也不将混音内部片段视为独立曲目。心危擂台保留各组合 ID 的分享页，音频元数据指向对应组合的游戏音源。

每页的静态 HTML 包含曲目主标题、`星塔旋律 · 专辑或故事集名称`、封面、canonical URL，以及 [Open Graph](https://ogp.me/) 的 `og:audio`、HTTPS 音频地址、MIME 类型和时长。同时提供 [AudioObject](https://schema.org/AudioObject) JSON-LD 与音频 alternate link，爬虫无需执行 JavaScript 即可发现资源。Opus 使用 `audio/ogg`，不为分享预览批量转码或重复发布音频。

秘纹页的描述使用 `activity.name`，不使用秘纹或曲目名作为专辑名；故事音乐继续使用可编辑映射里的分组名。比如“美好，尽在昨日”的描述为“星塔旋律 · 遥远的塔”。分享封面采用站内 `art/<code>/preview.jpg`，最长边 640 像素；构建时写入实际宽高和 `image/jpeg` 类型，避免读取 GitHub Release 中的大 PNG 原图。增加秘纹或更新封面后，可执行 `python scripts/export_share_previews.py --public-dir public` 重新生成预览。该脚本只读取已有导出图，不修改游戏输入。

`src/musicRoutes.ts` 统一生成路径、解析曲目 ID 和维护播放页元数据。秘纹一览旁的复制按钮复制当前核心或凯旋旋律的路径链接。旧的 `?disc=<秘纹 ID>` 和 `?track=<曲目 ID>` 链接继续定位，加载后规范化为新路径。普通静态托管无法按 query 参数输出不同 HTML，社交分享应使用新的路径链接。

Telegram 等平台能读取公开页面和音频信息，但是否生成原生音频播放器由平台决定。Telegram [Bot API 的 sendAudio](https://core.telegram.org/bots/api#sendaudio) 另有格式要求，不等同于网页链接预览；这里没有调用机器人、发送消息或上传文件。

生产域名默认读取 `public/CNAME`，可用 `SITE_ORIGIN` 覆盖；`NOVA_PUBLIC_DIR` 与 `NOVA_DIST_DIR` 可用于隔离重建。只提交生成脚本与源数据，`dist` 中的独立页面由部署流水线生成。
