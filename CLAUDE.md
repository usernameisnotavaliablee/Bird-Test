# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

「喜鹊」是 **APK 逆向对比分析工作区**。任务是拆解 `改版.apk` 与 `原版.apk` 两份安卓包，定位改版的实质改动。所有分析产物在 `analysis/` 下，工具脚本在 `analysis/tools/`。

## 已确认的总体结论（分析起点）

- **原版是加固包**：`AndroidManifest.xml` 的 application 入口为 `com.nesun.stub.ZAP`（典型加固壳桩），真实业务代码被抽取到 `analysis/original/payload_dex/` 的 5 个 dex 中，非壳代码需从 payload 反编译产物阅读。
- **改版是对原版的二次重打包**：注入 `libSignatureKiller.so`（arm64-v8a / armeabi-v7a / armeabi）与 `assets/SignatureKiller/origin.apk` 绕过签名校验，替换签名证书（`KINGOKEB` → `ANDROID`），移除内嵌的 `assets/origin.apk` 和原壳的 `classes4.dex`，新增百度地图 SDK（`libBaiduMapSDK_*.so`）。

## 目录语义（命名即含义）

```
analysis/
  original/   原版.apk 的解包产物
    apktool/         apktool 反编译结果（AndroidManifest.xml + smali*）
    jadx/            jadx 反编译出的 Java 源码 + resources
    payload_dex/     从加固壳中脱壳提取的真实 dex（classes.dex ~ classes5.dex）
    payload_dex_repaired/         修复校验和的 dex
    payload_dex_repaired_nomap/   修复 + 损坏 map-list 置零 的 dex
    payload_jadx*/                对应 payload dex 的 jadx 反编译 Java
  modified/  改版.apk 的解包产物（apktool/、jadx/、jadx_rawnames/）
    embedded_origin_*/  从改版内嵌文件（assets/SignatureKiller/origin.apk）中解出的
                        原始包，再分别经 apktool / jadx / 证书 处理
  comparison/ 对比结果 JSON（见下）
  tools/      对比与修复脚本（见下）
  .runtime/   apktool 临时工作目录（可忽略）
```

`embedded_origin_*` 与 `modified/*_rawnames` 用于对比「改版内嵌的原包」vs「改版」，以确认内嵌包是改版改造前的真实底包。

## 对比方法论

`comparison/` 下两组 JSON，含义完全不同：

| 文件前缀 | 对比对象 | 用途 |
|---|---|---|
| `given_original_vs_modified` | 用户给的 `原版.apk` vs `改版.apk` | 宏观差异（签名、加固结构、SDK 全不同，条目大量增减） |
| `embedded_origin_vs_modified` | 改版内嵌的 origin.apk vs `改版.apk` | 精确定位改版相对其直接底包的真实改动（仅 6 added / 3 removed / 4 changed） |

`*.archive.json` 为 ZIP 条目清单 diff（见 `archive_diff.py`），`*.manifest.json` 为安全相关清单 diff（见 `manifest_diff.py`）。分析时应优先读 `embedded_origin_vs_modified` 定位真实改动，再用 `given_original_vs_modified` 补全加固层差异。

## 工具脚本（analysis/tools/）

- `archive_diff.py <left> <right> [--output f.json]` — 按文件名/大小/CRC32 对比两个 APK/ZIP，输出 added / removed / changed 清单与计数。
- `manifest_diff.py <left> <right> [--output f.json]` — 解析两个反编译后的 `AndroidManifest.xml`（**XML 明文**，非二进制 AXML），对比权限、组件、导出组件、launcher、meta-data、SDK 版本等安全相关结构。
- `repair_dex_header.py <src> <dst> [--zero-map-list]` — 重算 dex 头的 SHA-1（偏移 32 起）与 Adler-32（偏移 12 起），修复加固壳破坏的校验和。`--zero-map-list` 额外把损坏的 map-list 项数置零（对应 `payload_dex_repaired_nomap` 变体）。

## 改版 vs 内嵌原包的真实差异（已逐类确认）

改版 = **内嵌 origin.apk 的真实底包** + 签名绕过注入 + **"觅Ta"权限校验绕过**。判定标准：用 `diff -rq` 定位差异文件后，对每个文件做**归一化 diff**（把混淆字段 `f42801a→f42819a`、寄存器变量 `j0/k0/i10`、数字字面量归一化后再 diff，排除重新打包造成的反编译噪声）。结果：349 个真实差异文件中 317 个是纯反编译噪声（`JADX WARN` 注释、寄存器重命名、字符串拼接方式），真正有业务意义的集中在以下两类。

### 1. 签名绕过注入（改版独有，非业务改动）
- `BaseApplication` 超类 `Application` → `bin/mt/signature/KillerApplication`
- 注入包：`bin/mt/signature/KillerApplication`、`org/lsposed/hiddenapibypass`（HiddenApiBypass）、`mt/Log*.java`
- 机制：`killPM()` 反射替换 `PackageInfo.CREATOR` 伪造原版 `KINGOKEB` 证书；`killOpen()` 加载 native `libSignatureKiller.so` + 解压 `assets/SignatureKiller/origin.apk` 做路径 hook
- 来源：GitHub `L-JINBIN/ApkSignatureKillerEx`

### 2. "觅Ta"服务开关校验绕过（真实业务篡改）
5 个类用**同一手法**：把 `mita`（或 `state`）字段的 `if(xxx.equals("1")){...}else{弹窗}` 判断掏空为 `if(xxx.equals("1")){}`，无条件执行原 else 分支的列表刷新/页面跳转，**删除全部"未开启【觅Ta】服务"提示弹窗**：

| 类 | 原版被删除的弹窗/分支 |
|---|---|
| `ui/activity/new_wdjx/new_kebiao/TeaInfoActivity` | "未开启【觅Ta】服务，无法查看ta的信息" |
| `ui/activity/new_wdjx/new_kebiao/ClassmateInfoActivity` | "您的/对方的觅Ta开关未开启，不能查看他人课表" + "未开启【觅Ta】服务" |
| `ui/activity/new_wdjx/new_kebiao/TdkbActivity` | state!=1 时弹"未开启【觅Ta】服务" |
| `ui/activity/new_wdjx/new_kebiao/MitaNewActivity` | state!=1 时弹"未开启【觅Ta】服务" |
| `ui/activity/new_wdjx/new_kebiao/MitaNewListActivity` | state!=1 时弹"未开启【觅Ta】服务" |

**效果**：改版用户无需对方开启【觅Ta】开关，即可查看他人课表/信息/同学列表——服务端权限校验被客户端掏空绕过。**精确范围**：绕过的是"对方未开启觅Ta开关"这一层客户端拦截，黑名单拦截、自身/对方双开关校验、TEA 身份旁路、同校校验仍生效（详见深度探索文档 §1.5）。第 6 处在 `a2/a.java`（`state`+`msg` 隐私门禁"由于对方设置【觅TA】隐私开关，您无法查看其信息"被掏空）。

### 3. 数据窃取注入（重大发现）
改版者注入 `mt.Log22A16D` 日志组件，把敏感数据落盘：
- `y8/j0.java`：**4 处** `Log22A16D.a()` 记录**解密后的明文密码**（AES key `loginkeyapp93214`、IV `12fg45gpsdfz34ab`，`f9/a.java` 硬编码）+ 3 处密码密文
- `b8/b.java`：**3 处** `Log22A16D.a()` 记录他人姓名/性别/班级（每次点击同学即写）
- 落盘路径：`/sdcard/MT2/logs/com.kingosoft.activity_kb_common-<时间戳>.log`（外部存储，可被其他应用读取），无加密、无轮转、无回传
- Log 类审计：7 个 `mt/Log*` 中 **6 个改版注入**（仅 `Log22A16D` 激活，其余 5 个休眠/诱饵），`LogD78843` 为**底包自带**且休眠
- 无其它监控组件：未植入远程回传/截屏/剪贴板/键盘/无障碍/网络 hook（`b9/a.java` 截屏监听为底包自带）

### 4. 第三方 SDK 零改动
推送 appkey（JPUSH `fa5d848b146f9ac37e72b100` / XIAOMI / OPPO）、百度地图/语音 key、华为 HMS、assets/res 配置全部与底包 byte-identical。18 个 SDK 差异文件经 DEX 方法集比对全部是反编译噪声，改版者没有篡改任何 SDK 配置或数据回传。

### 5. 签名绕过完整机制
改版用 **ApkSignatureKillerEx**（GitHub `L-JINBIN/ApkSignatureKillerEx`）：三层注入。
- Java 层：反射替换 `PackageInfo.CREATOR` 代理，让 app 进程内查询到的目标包签名伪造为原版 KINGOKEB 证书（含 v2 `SigningInfo` 路径）
- Native 层：`libSignatureKiller.so`（xhook 1.2.0 静态链接）hook `openat/openat64/open64/open` 的 PLT/GOT，把 `open("/data/app/.../base.apk")` 重定向到解压出的 `assets/SignatureKiller/origin.apk`
- 隐藏 API：LSPosed `HiddenApiBypass`（Unsafe 遍历 ART 方法表 + 桩方法调用）解锁 `Parcel.mCreators`/`sPairedCreators`/`PackageManager.sPackageInfoCache` 并清缓存
- **骗的是运行时自检，不骗安装校验**：改版包以 ANDROID 证书自洽 v1 签名安装，无法覆盖安装原版，signature 级权限会拒绝

觅Ta 调用链、SDK 核查、签名绕过的完整细节见 `analysis/改版深度探索文档.md`。

## 环境与常用命令

- 工具链均在 PATH：`apktool`、`jadx`、`java`、`python3`（Homebrew）。
- 反编译一份 APK：`apktool d 某.apk -o <dir>`、`jadx -d <dir> 某.apk`。
- 典型分析管线：`apktool d` → `manifest_diff.py` 对比 manifest；`archive_diff.py` 对比条目；对损坏 dex 先 `repair_dex_header.py` 再 `jadx`。
- 工具脚本为纯标准库 Python3，无额外依赖，直接 `python3 tools/xxx.py` 运行。
