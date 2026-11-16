# 秘纹补丁素材

游戏的 `client_config.ini` 可指定 `PatchResServerUrl`。本次核对的配置地址是 `http://na.jvav.net.cn/res`，游戏本地已经存在对应的 `Patch_Store/AssetBundles`。本项目直接只读这些已下载资源，不修改配置、不启动游戏，也不自动下载或执行服务器提供的程序。

`references/artwork-patches.json` 保存本次核对记录：秘纹编号与名称、补丁和常规资源包的相对路径与 SHA-256、发生变化的纹理及其解码 RGBA 指纹，以及导出资源的 SHA-256。源 Unity 包不提交仓库。

```powershell
# 先核对，不修改网页素材
.venv\Scripts\python.exe scripts/apply_artwork_patches.py --game-dir "D:\TapTap\PC Games\733498"

# 将已核对的变化应用到网页目录
.venv\Scripts\python.exe scripts/apply_artwork_patches.py --game-dir "D:\TapTap\PC Games\733498" --apply
```

默认报告和原尺寸 PNG 位于 `.build/patch-artwork/`，可用 `--work-dir` 修改。`--public-dir` 指向包含 `data/outfits.json` 的网页资源目录，`--report` 可另外指定报告位置。脚本不改写秘纹 JSON 或故事音乐映射。

脚本将 `Patch_Store/AssetBundles/disc_<编号>.unity3d` 与版本资源包比较；版本包不存在时，回退至安装资源包。只有网站实际使用且解码像素不同的纹理才会导出；同名纹理的原始尺寸不同或缺失时，记录错误，避免套用不匹配的差分坐标。同一图片的完整封面、现有展示封面、缩略图和分享预览同步更新。独立图层仍沿用已发布的渲染尺寸和坐标。

`scripts/rebuild.py` 在导出新增秘纹后也会执行这一步，并将报告写入工作目录的 `artwork-patches.json`。没有 `Patch_Store` 的游戏目录可正常重建，现有网站素材不会因此回退成常规版本。

当前网站的“保存秘纹静态图”使用 GitHub `artwork` Release 中的原尺寸 PNG；应用补丁后，还需同步上传变化的原图，否则网页封面和下载原图会不一致。只上传报告中具有 `download_original` 的文件，例如：

```powershell
gh release upload artwork .build/patch-artwork/originals/4038.png --clobber
```

这是替换该 Release 中同名原图的操作。网页构建只需要 `public/` 中的优化图片，不需要 Unity 原包、比较图或工作目录。
