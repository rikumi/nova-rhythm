# 运行时客户端配置与补丁覆盖调查

核对日期：2026-11-17。结论来自当前 Windows 客户端和官网提供的 Android 官服 APK 的离线元数据解析、x86-64 / ARM64 反汇编；未启动游戏、注入进程或修改游戏文件。

## 结论

`client_config.ini` 的读取入口没有整体移除，内容仍然是 JSON。两端均存在并使用 `RuntimeClientConfig`、`Booter.LoadRuntimeClientConfig`、`RuntimeClientConfig.LoadFromFile` 与 `OverrideFromFile`。已确认的字段仍是：

```json
{
  "PatchResServerUrl": "http://na.jvav.net.cn/res"
}
```

此外还有 `ReplaceDownloadServerUrl`、`LocalResServerUrl`、`UseTestServer`，它们不是 `PatchResServerUrl` 的新名称，不需要为切换补丁服务器而一并设置。

**这个字段启用的是额外资源覆盖，不能据此判定图片是否去除了遮挡。** 补丁图片可能比常规资源更受遮挡。此前将有像素差异的补丁图片直接当成正确替换方向，判断不足；相关素材、自动应用逻辑及下载原图已经回退。

## 配置位置和覆盖规则

`Booter.LoadRuntimeClientConfig` 调用 `Directory.GetFiles(baseDataPath, "client_config*.ini", SearchOption.TopDirectoryOnly)`，不递归查找。第一个文件使用 `JsonUtility.FromJson<RuntimeClientConfig>(File.ReadAllText(path))`，后续文件使用 `FromJsonOverwrite` 覆盖同一个实例。这里没有排序操作，不应依赖文件名后缀推断优先级。

| 平台 | 反汇编确认的基目录 |
| --- | --- |
| Windows CN_Taptap 2.0.0 | `Directory.GetParent(Application.dataPath).FullName`，即含 `xtlr.exe` 的安装根目录 |
| Android 官服 2.0.0 / versionCode 26093015 | `Application.persistentDataPath` |

Android 官服包名为 `com.RoamingStar.StellaSora`。根据 [Unity 的 persistentDataPath 文档](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Application-persistentDataPath.html)，通常对应：

```text
/storage/emulated/0/Android/data/com.RoamingStar.StellaSora/files/client_config.ini
```

应与游戏的 `Persistent_Store`、`Temporary_Store`、`Patch_Store` 等目录同级。实际设备路径尚未读取；其他渠道、分身和工作资料可能对应不同包名或用户目录，不能直接套用官服路径。

排查时尤其注意：

- 扩展名是 `.ini`，正文是 JSON，不是 INI 的 `key=value` 或节标题格式。
- `client_config_backup.ini`、`client_config_old.ini` 也会匹配并参与覆盖。备份应放到其他目录。
- 配置在启动流程中读取，不会随着编辑自动刷新。必须完全退出游戏进程后再启动，重新登录不等同于冷启动。
- 已分析入口没有要求先开启 GM、开发者或 root 模式。root 不是这个解析器的前置条件。

## 补丁真正如何生效

以下为根据静态调用链整理的简化逻辑，不是完整反编译源码：

```text
启动 → ClientManager.Setup → LoadRuntimeClientConfig

RuntimeClientConfig.Instance 为空或 PatchResServerUrl 为空
    → 跳过这条额外补丁更新路径
否则
    → 下载清单 → 检查与客户端版本兼容性
    → 建立 ResourceBundleManifest.PatchResourceInstance
    → 判断版本并按需下载、登记补丁资源

加载资源包：
    补丁清单有同名条目 + 文件存在 + 已登记版本匹配
        → 优先读取 Patch_Store
    否则
        → 尝试常规版本资源，再回退安装资源
```

版本登记使用 `file_versions.dat` 派生的缓存字典。已分析的 `CheckFileVersion` 路径比较的是登记版本，并非每次加载都重新计算整个文件的摘要。仅把一个新名称的文件放进 `Patch_Store`，也不能让没有清单条目的资源自动成为覆盖项。

如果要排除“额外覆盖选中了另一版图片”，可将字段改为：

```json
{"PatchResServerUrl":""}
```

在**全新进程**中，已分析的补丁更新入口会跳过，不会由它初始化额外覆盖清单。这是静态代码推导，未在实际设备运行验证；也不代表常规资源一定没有遮挡。无需为这项对照测试删除整个资源目录或修改二进制。

## 当前服务器与本地状态

实际可访问的清单包括：

- [Windows：win/ss_win.mani](http://na.jvav.net.cn/res/win/ss_win.mani)
- [Android：and/ss_and.mani](http://na.jvav.net.cn/res/and/ss_and.mani)
- [iOS：ios/ss_ios.mani](http://na.jvav.net.cn/res/ios/ss_ios.mani)

本次快照均有 124 项，标记客户端版本 `2.0.0`、游戏版本 `2.1.0`。Windows 清单版本为 `2611122204`；本地 `prefs.dat` 的 `LOCAL_PATCH_RESOURCE_VERSION` 同样为 `2611122204`，124 项资源的实际大小和 MD5 均与清单一致。这说明该服务器资源已经下载并登记过，不能据此宣称新版完全删除了配置入口；是否正在具体设备中渲染这些文件，仍须运行时观察。

三份清单均没有 `4061`。当前“睡前童话”的人物纹理 `4061_actor` 和完整封面 `4061_B` 本身包含遮挡，网页未额外添加该遮挡。换到同一服务器、修改版本标记或取得 root，都不会令这份清单生成缺失的替代图片。

## 不需要 root 和需要 root 时分别怎么处理

这里列出供设备所有者手动执行的方法，本次调查没有执行这些写入命令。先完全退出游戏，并将原配置备份到游戏扫描目录以外。应先确认实际包名和上述基目录。

若 ADB 有权写入目标目录，可以直接使用 `adb push` 放置同一个 JSON 配置，不需要 root，也不需要改 `libil2cpp.so`。

若系统只阻止第三方或 ADB 写入应用外部目录，而设备已经有 root，可将配置暂存到 `/data/local/tmp`，再通过 root shell 写入**同一个配置位置**：

```sh
# 在电脑终端执行；client_config.ini 是自行准备、核对过的 JSON 文件
adb push client_config.ini /data/local/tmp/xtlr-client-config.json
adb shell am force-stop com.RoamingStar.StellaSora
adb shell

# 以下在设备 shell 中执行，并同意设备上的 root 授权
su
base=/sdcard/Android/data/com.RoamingStar.StellaSora/files
test -d "$base/Persistent_Store" || exit 1
cfg="$base/client_config.ini"
if [ -f "$cfg" ]; then cp "$cfg" /data/local/tmp/xtlr-client-config.before.ini; fi
cp /data/local/tmp/xtlr-client-config.json "$cfg"
cat "$cfg"
exit
exit
```

随后从桌面重新打开游戏。该方法利用的是 root 文件访问权限，配置格式、扫描位置和读取代码均不改变；它不是已实机验证的通用绕过方案。没有证据支持必须通过 root 去改游戏二进制或把该配置改放到一个任意的内部目录。

可用于观察读取结果的日志字符串有 `Load runtime client config:`、`Override runtime client config:`、`Load runtime client config error:`、`BEGIN Update Patch Resource:`、`CLIENT INIT [PatchVer:`。发布版可能限制日志输出，看不到日志不能单独证明没有读取。

## 可复核证据

[references/runtime-client-config.json](../references/runtime-client-config.json) 保存了输入文件 SHA-256、Android APK 来源和版本、关键方法 RVA、服务器快照及结论边界。地址只适用于匹配哈希的二进制，不能跨版本直接使用。

关键方法示例：

| 方法 | Windows RVA | Android ARM64 RVA |
| --- | --- | --- |
| `Booter.LoadRuntimeClientConfig` | `0x1142970` | `0x449F8C4` |
| `RuntimeClientConfig.LoadFromFile` | `0x114F760` | `0x449FF18` |
| `DownloadStore.get_baseDataPath` | `0x10AD530` | `0x44209A8` |
| 补丁更新协程 `MoveNext` | `0x1155EE0` | `0x44A9A70` |

元数据解析参考 [StellaSoraMetadataDecryptor](https://github.com/patchminormajor/StellaSoraMetadataDecryptor)，方法和类型定位使用 [Il2CppDumper](https://github.com/Perfare/Il2CppDumper)，再对相应原生代码做静态反汇编。游戏二进制、解密元数据和完整反编译输出保留在被忽略的 `.build/code-analysis/`，没有提交仓库。
