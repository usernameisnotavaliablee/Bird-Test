# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

「喜鹊」是 **APK 逆向对比分析工作区**。三份 APK（版本序：改版 2.6.435 < 原版 2.6.452 < 最新版 2.6.454）：拆解 `改版.apk` 与 `原版.apk` 定位改版的实质改动；对官方 `最新版.apk` 评估「注入觅Ta 改动」的可行性。分析分两阶段：
- **静态分析**（主体已完成）：结论见下「已确认的总体结论」与 `analysis/` 下三份深度文档。
- **动态验证**（当前主线）：实机抓包实测 `baseInfoServlet?step=other`（查同学）与 `wapController.jsp?step=GetTeaResume`（教师简历）服务端下发**宽行还是窄行**，为漏洞报告定性。执行手册 = 根目录 `实操手册.md`。

所有分析产物在 `analysis/` 下，工具脚本在 `analysis/tools/`。

## 会话入口与工作流（续接先读）

- **断点续接第一入口 = `HANDOFF.md` 全文**：实时工作交接日志（按时间追加），含当前断点、已坐实证据、下一步与恢复核查清单。`AGENTS.md` 是给代理的速览入口。
- 用户指定工作流：① 每步操作**追加记录到 `HANDOFF.md`**（时间戳/操作/文件/结论/下一步）；② 每次更改**立即 `git commit`**（中文 message）；③ 并行深挖任务拆给 subagents，避免主会话上下文爆炸。
- 反编译产物被 `.gitignore` 排除（`/最新版/`、`analysis/original|modified|latest|captures/`），只入库文档/脚本/对比 JSON；产物路径记入 HANDOFF。`analysis/captures/` 抓包明文含 PII+token，**绝不能入库**。

## 已确认的总体结论（分析起点）

- **原版是加固包**：`AndroidManifest.xml` 的 application 入口为 `com.nesun.stub.ZAP`（典型加固壳桩），真实业务代码被抽取到 `analysis/original/payload_dex/` 的 5 个 dex 中，非壳代码需从 payload 反编译产物阅读。
- **改版是对原版的二次重打包**：注入 `libSignatureKiller.so`（arm64-v8a / armeabi-v7a / armeabi）与 `assets/SignatureKiller/origin.apk` 绕过签名校验，替换签名证书（`KINGOKEB` → `ANDROID`），移除内嵌的 `assets/origin.apk` 和原壳的 `classes4.dex`，新增百度地图 SDK（`libBaiduMapSDK_*.so`）。
- **最新版（2.6.454）是官方加固包**：壳桩 `com.nesun.stub.ZAP`，业务代码在内嵌 `assets/origin.apk` 的 5 个 dex，签名仍为 `KINGOKEB.RSA`（与原版同证书），未被篡改。**觅Ta 已重构**：旧 4 类（TeaInfoActivity/TdkbActivity/MitaNewActivity/MitaNewListActivity）被官方删除，新实现 = `Mita_edit`（ui/view/new_view/）+ `MitaListBean`（bean/jsjy/bean/）。

## 目录语义（命名即含义）

```
analysis/
  original/   原版.apk 的解包产物
    apktool/         apktool 反编译结果（AndroidManifest.xml + smali*）
    jadx/            jadx 反编译出的 Java 源码 + resources
    payload_dex/     从加固壳中脱壳提取的 dex（classes.dex ~ classes5.dex）
                      ⚠️ 数据区部分加密（壳解密完成前被 dump）：jadx 反编译 3496 java
                      全为空壳桩（JADX ERROR），静态不可恢复；重新动态脱壳或
                      提取壳密钥离线解密才有解。452 业务 Java 面改用
                      modified/jadx 或 embedded_origin_jadx* 树
    payload_dex_repaired/         修复校验和的 dex
    payload_dex_repaired_nomap/   修复 + 损坏 map-list 置零 的 dex
    payload_jadx*/                对应 payload dex 的 jadx 反编译产物（全部空壳桩，勿再跑）
  modified/  改版.apk 的解包产物（apktool/、jadx/、jadx_rawnames/）
    embedded_origin_*/  从改版内嵌文件（assets/SignatureKiller/origin.apk）中解出的
                        原始包，再分别经 apktool / jadx / 证书 处理
  comparison/ 对比结果 JSON（见下）
  latest/     最新版.apk 的解包产物（gitignore）
    origin_repaired_nomap/  ← jadx 唯一可用输入：校验和修复 + map-list 置零 的
                              内嵌底包 dex；用 origin_repaired 会
                              BufferUnderflowException 产出 0 文件
    origin_jadx*/ jadx/     各轮 jadx 产物（部分全空，见上）
  comparison/ 对比结果 JSON（见下）
  captures/   实机抓包产物（flows *.mitm、登录密文/明文）——gitignore，含 PII+token
  tools/      对比与修复脚本（见下）
  .runtime/   apktool 临时工作目录（可忽略）
```

`embedded_origin_*` 与 `modified/*_rawnames` 用于对比「改版内嵌的原包」vs「改版」，以确认内嵌包是改版改造前的真实底包。

根目录文档：`HANDOFF.md`（交接日志，续接第一入口）、`AGENTS.md`（代理速览入口）、`实操手册.md`（实机抓包手册）、三份 APK（`原版.apk` / `改版.apk` / `最新版.apk`）。

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
- `decrypt_xqr.py <密文文件|->` — baseInfoServlet/登录响应一键解密 + 宽窄行判定（URLDecode→Base64→AES/CBC/PKCS5，key/IV 硬编码在脚本内）。`pbpaste | python3 tools/decrypt_xqr.py -`。唯一依赖 `cryptography`（其余脚本纯标准库）。

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
- `y8/j0.java`：**4 处** `Log22A16D.a()` 记录**解密后的明文密码**（AES key `loginkeyapp93214`、IV `12fg45gpsdfz34ab`，`f9/a.java` 硬编码）+ 3 处密码密文（等价明文）；`j0.g()` 被 13 处 Activity 启动调用 → 明文密码反复落盘。**仅记录密码，不记录 token/userid**
- `b8/b.java`：**3 处** `Log22A16D.a()` 记录他人姓名/性别/班级（每次点击同学即写；smali 另有 1 条在被掏空后不可达的死代码中）
- 落盘路径：`/sdcard/MT2/logs/com.kingosoft.activity_kb_common-<时间戳>.log`（外部存储），**裸字符串、无 `##GET##/##PUT##` 前缀**、无加密、无轮转、无回传
- Log 类审计：7 个 `mt/Log*` 中 **6 个改版注入**（仅 `Log22A16D` 激活，其余 5 个休眠/诱饵），`LogD78843` 为**底包自带**且休眠；`Log22A16D/LogE0E388` 走 MT2/logs，`Log25EB87/5A0B53/A704BA/BE294D` 走 sdcard 根路径
- 无其它监控组件：未植入远程回传/截屏/剪贴板/键盘/无障碍/网络 hook/埋点 SDK（`b9/a.java` 截屏监听为底包自带）

### 4. 数据面结论（查他人 vs 查自己）
- **服务端鉴权弱**：`baseInfoServlet?step=other` 仅凭 `otheruuid` 即可拉起他人信息（无签名令牌），但服务端**只在查他人接口下发教育学术信息**（姓名/性别/头像/学号/院系/班级/专业/年级/周课表），**不下发身份敏感字段**（身份证/电话/邮箱/地址/家长信息）。
- 敏感字段 getter 调用统计：`getSfzh`(身份证)/`getGkksh`(高考号)/`getCsd`(出生地)/`getJg`(籍贯)/`getZzmm`(政治面貌)/`getLxryj`(邮箱)/`getByzx`/`getSyd` 等 **0 处非 bean 调用** → 查他人不可见；出生日期/民族仅在**教师公开简历**（`oriHd_ggym&step=GetTeaResume`）展示；联系人电话/邮箱仅在**查自己**的就业意向场景。`UserInfoBean` 敏感字段多不代表查他人能拿到。
- 鉴权强度表 / 数据面全集见 `analysis/数据面与监控组件深挖.md`。

### 5. 第三方 SDK 零改动
推送 appkey（JPUSH `fa5d848b146f9ac37e72b100` / XIAOMI / OPPO）、百度地图/语音 key、华为 HMS、assets/res 配置全部与底包 byte-identical。18 个 SDK 差异文件经 DEX 方法集比对全部是反编译噪声，改版者没有篡改任何 SDK 配置或数据回传。

### 6. 签名绕过完整机制
改版用 **ApkSignatureKillerEx**（GitHub `L-JINBIN/ApkSignatureKillerEx`）：三层注入。
- Java 层：反射替换 `PackageInfo.CREATOR` 代理，让 app 进程内查询到的目标包签名伪造为原版 KINGOKEB 证书（含 v2 `SigningInfo` 路径）
- Native 层：`libSignatureKiller.so`（xhook 1.2.0 静态链接）hook `openat/openat64/open64/open` 的 PLT/GOT，把 `open("/data/app/.../base.apk")` 重定向到解压出的 `assets/SignatureKiller/origin.apk`
- 隐藏 API：LSPosed `HiddenApiBypass`（Unsafe 遍历 ART 方法表 + 桩方法调用）解锁 `Parcel.mCreators`/`sPairedCreators`/`PackageManager.sPackageInfoCache` 并清缓存
- **骗的是运行时自检，不骗安装校验**：改版包以 ANDROID 证书自洽 v1 签名安装，无法覆盖安装原版，signature 级权限会拒绝

觅Ta 调用链、SDK 核查、签名绕过的完整细节见 `analysis/改版深度探索文档.md`。

## 动态验证阶段关键事实（抓包/加密/端点）

### 网络栈与加密（静态坐实 + 部分实测）
- HTTP 栈 = okhttp3 3.10.0（squareup 2.x 仅图片），**trust-all**：`BaseApplication.x()` 空 checkServerTrusted + hostnameVerifier 恒 true；无 pinning、业务请求无 Cookie/自定义头、0 处代理/VPN 对抗（唯一模拟器检测是死代码）→ mitmproxy 无需装 CA。
- serviceUrl 登录动态下发，默认兜底 `http://api.xiqueer.com/manager/`（明文 HTTP，实测该校即此值）。
- **响应加密**：baseInfoServlet / 登录响应 = URLDecode → Base64 → AES/CBC/PKCS5，key=`loginkeyapp93214`、iv=`12fg45gpsdfz34ab`（`f9/a.java` 硬编码）；wapController.jsp（GetTeaResume）响应是**明文 JSON**。
- **请求加密在 native 层**：`f9/b.java:u()` 拼明文串 → `NDKTools.getStringFromNDKZDY(明文, key, "zdy")` 一次产出六元组（`param/param2/timestamp/echo/encrptSecretKey/xqerSign`），线上有 POST 表单与 GET query 两种形态。`f9.b.k()/j()` 那对 Java base36 流密码是全树无人调用的**死代码**，移植无效。

### 关键端点
- 查同学：`{serviceUrl}/wap/baseInfoServlet`，参数仅 `userId/usertype/step=other/otheruuid`，**无令牌无签名**；客户端只消费 5 路由字段（学生 xm/xxdm/xh/ssbj/xb；教师 xm/xxdm+jsdm|userid）。
- 教师简历：`{serviceUrl}/wap/wapController.jsp`，`action=oriHd_ggym&step=GetTeaResume&jsid=教师号`；Bean JsxqBean 16 字段（含 sfzh/dh/yx/jg），弹窗只展示 7 项。
- **step=other 的前置闸门**：发请求前客户端先查**自己**的觅Ta开关（`y8/s0.java`→getMITA），state!=1 只弹窗不发请求——实测抓包必须先开自己开关。入口区分：搜同学/学友圈/同学情 → 信息页（发 step=other）；觅Ta列表点人 → 课表页（不发）。

### 三层口径（方法论，Gson 场景必用）
**展示面 / 解析面 / 下发面**分开论证：解析面（Bean 字段集）由 Gson 反射直写，**不走 getter**——「getSfzh 等 0 处调用 → 不可见」的旧结论只在展示面成立。下发面（服务端实际返回）静态不可定，只能实测（当前主线）。

### 合规边界（务必遵守）
- 回放/构造请求 `otheruuid` **只填自己的 uuid**，绝不枚举他人；抓到他人数据只记键名不存值。
- 结论向校方/青果（kingosoft）负责任披露，不公开密钥与 exploit 细节。

## 环境与常用命令

- 工具链均在 PATH：`apktool`、`jadx`、`java`、`python3`（Homebrew）。`adb`/`mitmproxy` 需自行安装：`brew install --cask android-platform-tools mitmproxy`（先用 `command -v` 验证）；沙箱内 adb 起不了 daemon（tcp:5037 被拦），本机执行需提权。
- 反编译一份 APK：`apktool d 某.apk -o <dir>`、`jadx -d <dir> 某.apk`。
- **反编译最新版内嵌底包 dex**：`jadx -d <out> --show-bad-code --no-res analysis/latest/origin_repaired_nomap/classesN.dex`（必须 nomap 变体，理由见目录语义）。
- 解密抓包响应：`pbpaste | python3 analysis/tools/decrypt_xqr.py -`；或手册 §3.4 的 openssl 一行流（免装 pycryptodome，brew python 有 PEP 668 限制）。
- 典型分析管线：`apktool d` → `manifest_diff.py` 对比 manifest；`archive_diff.py` 对比条目；对损坏 dex 先 `repair_dex_header.py` 再 `jadx`。
