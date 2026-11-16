# PWA

`public/manifest.webmanifest` 配置安装名称、图标、入口与快捷入口，使用独立窗口 `standalone`，保留状态栏和导航栏，不请求全屏隐藏系统栏。`index.html` 的 `viewport-fit=cover` 和 iOS `black-translucent` 桌面应用设置配合 `src/pwa.css`，让背景延伸到系统栏下方，同时通过安全区给标题、播放栏、页脚及全屏按钮留出空间。平台最终采用的系统栏显示方式由浏览器决定。

Android 安装模式若未提供有效底部安全区，`src/pwa.ts` 会补充读取最大安全区、Visual Viewport 底部差值和屏幕可用区域。所有数据均为零时不额外预留空间，不使用固定高度回退。普通浏览器标签页和非 Android 平台保持原生 CSS 安全区。键盘弹出或页面缩放不会被当作系统栏高度，并在视口变化、横竖屏切换、焦点变化与回到应用时更新。

最大安全区的定义见 [CSS 环境变量规范](https://www.w3.org/TR/css-env-1/#safe-area-max-insets)，Chrome 的实现说明见 [edge-to-edge 文档](https://developer.chrome.com/docs/css-ui/edge-to-edge)。已有安装的显示模式由 Chrome 的安装清单更新机制刷新；修改清单不会主动关闭或重装用户应用。

图标背景来自原生旋律按钮 `btn_outfit_music.png` 的内部区域（裁切范围 x=11..165、y=11..127），去除边框及内阴影。前景采用首页秘纹旋律的 `home-btn_main_system_outfit_L.png`，在 512 像素画布中央显示为 307.2 像素，较此前放大 1.2 倍，并保留桌面裁切余量。提供 32、180、192、512 像素 PNG；实际桌面遮罩效果取决于系统。

`scripts/build_pwa_icons.mjs` 使用 SVG 组合原始游戏 UI 图片，再通过 Playwright/Chrome 渲染安装图标。日常构建直接使用已提交的 PNG，不需要 Playwright；重新生成图标时需准备 `@playwright/test` 和 Chrome，执行 `node scripts/build_pwa_icons.mjs`。图标素材未使用生成式重绘。

`src/pwa.ts` 只在生产构建注册 `public/sw.js`，开发服务器不注册。缓存包括首页外壳、有限数量的前端资源与已访问的 JSON；导航和 JSON 优先网络，避免编辑后的映射长期停留在旧缓存。音频、Range 请求和秘纹图片集合不缓存，避免自动下载数百 MB 资源。离线时可以打开已缓存的首页，音乐播放仍需网络。

检查包括 Chrome 安装条件、Service Worker 接管、离线首页、音频 206 范围响应及模拟安全区；真实 iOS/Android 的系统栏与桌面裁切仍应在设备上复核。改动静态图标或未带哈希的 UI 素材时，更新 `sw.js` 中缓存版本，确保已有安装获得新资源。
