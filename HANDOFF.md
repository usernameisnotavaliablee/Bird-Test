# HANDOFF — 喜鹊逆向工作区工作交接日志

> 本文件由 CLAUDE Code 按用户要求实时维护。**每做一步操作都追加记录**，每次更改都 commit。
> 目的：任何中断/续接时，凭本文件即可还原全部上下文与下一步。
> 时间基准：2026-09-02（环境日期），日志按追加顺序排，新条目在上方或按时间。

---

## 2026-09-02 · 任务启动：为「最新版.apk」注入觅Ta 改动

### 背景（本次任务）
用户给出官方最新发布版 `最新版.apk`（2.6.454，versionCode 181），要求**在新版中加入类似改版的觅Ta 改动，使新版也能使用新旧版觅Ta 服务**（即绕过"对方未开启觅Ta"的客户端拦截）。用户选择「**先彻底分析再决定**」→ 计划分两阶段：
- **第一阶段（当前）**：攻克内嵌底包反编译 → 彻底分析最新版觅Ta 新实现与改造可行性。
- **第二阶段**：改造 + 重打包 + 签名（待分析确认后由用户决定）。
计划文件：`/Users/mac/.claude/plans/hazy-fluttering-whistle.md`

### 已确认的关键事实（侦察 + 双代理核实）
1. **最新版 = 官方加固包**：`com.nesun.stub.ZAP` 壳桩，业务代码在内嵌 `assets/origin.apk`（5 dex，classes.dex 8.88M/classes2 7.85M/classes3 4.48M/classes4+5 损坏残留），签名 `KINGOKEB.RSA`（与原版同证书），**未被改版式篡改**。minSdk=23。
2. **觅Ta 已重构**：旧 4 类（TeaInfoActivity/TdkbActivity/MitaNewActivity/MitaNewListActivity）在最新版 payload 三层（class_defs/type_ids/字符串）**全部 0 命中，官方已删除**；`new_kebiao` 包无类定义。新实现 = `Mita_edit`（EditText 视图，ui/view/new_view/）+ `MitaListBean`（bean，bean/jsjy/bean/）。`MiTaUtil` 仅源文件名字符串。弹窗文案在资源层不在 dex。
3. **版本序**：最新版 2.6.454(181) > 原版 2.6.452(178) > 改版 2.6.435(164)。最新版与改版前底包高度同源（dex 大小几乎一致）。
4. **工具链**：apktool 3.0.3 / jadx 1.5.6 / JDK 21 / keytool / openssl / python3 3.14 ✅；**缺 apksigner/zipalign/SDK**（签名环节需补）。
5. **卡点**：`analysis/latest/origin_jadx*` 三次 jadx 反编译全空（sources 0 文件）——内嵌底包 dex 反编译尚未成功。
6. **git**：仓库仅 1 次初始提交 `d43e035`；`analysis/latest/` 等被 gitignore。

### 分析产物位置（部分被 gitignore，仅记录路径）
- `analysis/latest/`：最新版解包/反编译产物目录（apktool_nores=外层壳解包成功、jadx=外层 675 java、origin_repaired=修复后 payload dex 等）
- `analysis/modified/embedded_origin_jadx/`：改版内嵌底包（2.6.452 改造前基线）可读源码——含旧 4 类
- `analysis/original/`：原版解包产物

## 2026-09-02 · 第一阶段进展：反编译卡点突破

### 突破（重要）
**jadx 反编译失败根因已定位**：`origin_repaired`（只修校验和）的 dex 头 `map_list` 仍损坏 → jadx 读 map_list 时 `BufferUnderflowException` → 0 文件。
**解法**：用 **`origin_repaired_nomap`（map-list 置零）变体** → jadx 能正常加载（跳过损坏项）。实测：
```
jadx -d <out> --show-bad-code --no-res origin_repaired_nomap/classes3.dex
→ 产出 1550 个 java（classes3 最小业务 dex 试跑成功）
```
之前 `origin_jadx*` 三次全空 = 用了 `origin_repaired` 而非 `origin_repaired_nomap`。

### 下一步
1. 用同样参数反编译 `classes.dex`（8.88M）和 `classes2.dex`（7.85M）——可能较慢/内存高。
2. 验证反编译产物含 `Mita_edit`/`MitaListBean` 等目标类。
3. 继续 task #6（产出到 `analysis/latest/origin_jadx_fixed/`）。

---

## 2026-09-06 · 查他人接口「响应解析面」深挖（进行中，会话中断交接）

### 任务上下文
- 由 `/code-1.0.4` skill 触发，线索：GetTeaResume（教师简历）响应 Bean **JsxqBean 含 sfzh/dh/yx/jg 敏感字段，弹窗只展示 7 字段但 Bean 全量反序列化** → 要求深挖各查他人页面实际解析面、他人标识接口响应解析字段。
- 会话中途用户粘贴另一分析的「**VMP 到头论**」（libkdvmp.so = "fasten" 商业 VMP，觅Ta 模块 u2/y2 native 化，"静态路线到头、只能靠 Frida"）→ 需裁决。

### 已完成（硬证据，已直接读源全文）
1. **JsxqBean（162 行）**：`ResultSetBean` 共 **16 字段**：csrq(出生日期)/dh(电话)/gw(岗位)/img(头像)/jg(籍贯)/mz(民族)/nl(年龄)/rxnf(入校年份)/sfzg/sfzh(身份证号)/xb(性别)/xl(学历)/xm(姓名)/xw(学位)/yx(邮箱)/zc(职称)。
   - 位置：`analysis/modified/embedded_origin_jadx_rawnames/sources/com/kingosoft/activity_kb_common/bean/HYDX/bean/JsxqBean.java`
   - 同文件存在于 4 棵树（modified/jadx、jadx_rawnames、embedded_origin_jadx、embedded_origin_jadx_rawnames）→ 底包自带非改版注入（是否逐字节未动 → 清单 #6 待 diff）
2. **f3/b.java（176 行）**：教师简历弹窗（Dialog，`R.layout.jsxq_dialog_style`）
   - 调用链：`q(activity, jsid, 姓名)` → `n()` 先调 `baseInfoServlet`（仅 userId+usertype，**无 step=other**）解析成 UserInfoBean **但结果从未被消费**（残留调用，f3/b.java:42-44）→ `m()` 发起 `GET {serviceUrl}/wap/wapController.jsp`，参数 `action=oriHd_ggym&step=GetTeaResume&userId=<自己>&userid=<去"_"前缀>&jsid=<目标教师>`（**无令牌/签名**，与 step=other 同款弱鉴权）
   - **f3/b.java:72 `new GsonBuilder().setLenient()...fromJson(str, JsxqBean.class)` —— 纯 Java 明文 Gson 反序列化，全程无 native/VMP**
   - 展示面（`c.run()` f3/b.java:98-106）：标题(姓名由调用方传入) + xb/csrq/xl/xw/rxnf/mz = **7 项**，与线索"弹窗只展示 7 个字段"吻合
   - **反序列化但不展示：sfzh/dh/yx/jg/zc/gw/nl/sfzg/img/xm（10 字段）**；`R.id.jl`（简历栏）绑定但从未赋值 = 死槽位

### 对「VMP 到头论」的裁决（待写入分析文档）
- **属实侧（仍待抽查坐实）**：觅Ta 信息页 u2/y2 native 化 + registerJni 解释器（与原版 nesun 加固一致）；z7/n 渲染 key 面 tag/content/image/dh/jsdm；u0/q0 日志空方法
- **错误/过度推广**：
  1. "字段解析被 VMP 加密、静态到头"**不适用于 GetTeaResume** —— f3/b.java 纯 Java Gson 明文解析，16 字段解析面静态已完全确定（VMP 化方法在 dex 里只会是 native 桩，jadx 不可能还原完整方法体）
  2. "只能靠 Frida"对重打包威胁模型**不成立** —— 引用自己的 hook 点 #1（`h9.b$f.callback(String)`）恰证明原始 JSON 在 Java 层明文过境；改版者 smali 插桩 callback 层（或复用已注入的 Log22A16D 管道）即可全量收割，**无需破 VMP**。VMP 防静态读者，不妨碍重打包者。
- **方法论修正（重要）**：旧《数据面与监控组件深挖.md》§4 "getSfzh 等 getter 0 处调用 → 查他人不可见"在 Gson 场景失效 —— fromJson 反射直写字段不经过 getter。**三层口径必须分开**：
  1. **展示面**（UI getter / z7-n key）—— 旧证据只证明这层干净
  2. **解析面**（Bean 字段集）—— JsxqBean 16 字段 / UserInfoBean 全量 PII，远宽于展示面
  3. **下发面**（服务端实际返回）—— 静态不可定；但 Bean 形状 = 教师人事档案宽行（resultSet 16 键），"服务端按宽行下发"先验较强 → 若属实则任意学生端凭可枚举 jsid 可拖全校教师档案（含身份证）= 水平越权 + 批量拖库面

### 会话事故记录
- 会话中途（用户本地切 `/model k3[1M]` + `/effort max` 后）macOS 沙箱收回项目目录访问：Bash+Read 对 `/Users/mac/Documents/喜鹊` 全部 EPERM → **重启终端恢复**
- 早期 Bash 参数序列化连续 5 次 InputValidationError（截断/嵌套引号）→ 教训：短命令、单引号、专用工具优先、报错即换写法

### 恢复后核查清单（按序）
1. `grep -n native .../new_kebiao/TeaInfoActivity.java`（embedded_origin_jadx_rawnames 树）→ 坐实/证伪 u2/y2 native 化（VMP 适用范围）
2. `z7/n.java` 查 `tel:` 与 `get("dh")` → 坐实"信息页电话渲染能力面"
3. f3.b 实例化点：`grep -rn 'new b(' sources/f3/` + `grep -rln jsxq_dialog_style sources/` → 查他人入口、jsid 来源（教师列表？KcbCxActivity？）
4. `original/payload_jadx*` 树找 JsxqBean/f3.b（此前全树 grep 'class JsxqBean' 只命中 modified 四树，original 0 命中——查明是命名差异还是缺失）
5. **原始任务主线**：`baseInfoServlet?step=other` 及 MitaNew* 列表接口响应 Bean 字段集普查（他人标识接口解析面）——每个 Bean 列全字段 vs 实际消费字段
6. `diff` 两树 JsxqBean.java → 确认改版未动此 Bean
7. 三层口径框架 + JsxqBean 16 字段表 + VMP 裁决写入《数据面与监控组件深挖.md》，修正 §4 措辞
8. libkdvmp.so 抽查（strings 查 fasten / 无明文 JSON 键）——可选坐实

### 环境
- 模型 k3[1M]，effort max；/code-1.0.4 skill 流（规划→执行→验证→交付）

---

## 2026-09-06 · 终端重启前最终快照（断点封存）

### 当前断点（一句话）
本会话主线已从「最新版觅Ta 改造」转入「**查他人接口响应解析面深挖**」。**恢复入口 = 上方「恢复后核查清单」8 项，从第 1 项按序执行**。

### 任务清单快照（TaskCreate 状态）
- #11 ✅ 建立 HANDOFF+git 工作流
- #6 🔄 攻克 origin dex 反编译——**nomap 方案已突破**（`origin_repaired_nomap` + `jadx --show-bad-code --no-res`，classes3 已出 1550 java）；classes.dex(8.88M)/classes2.dex(7.85M) 尚待全量反编译到 `analysis/latest/origin_jadx_fixed/`
- #7 ⏳ 彻底分析最新版觅Ta 新实现与改造可行性
- #8/#9/#10 ⏳ 第二阶段（改造/打包签名/验证），需用户确认后启动

### 已提交的 git 状态
- `d43e035` 初始备份；`fb0d3e6` HANDOFF.md 建立。后续深挖的中间结论可能未全部 commit——重启后第一件事：`git status` 看未提交项，先补 commit 再续作。

### 续接指南
新会话：① 读本文件全文（重点两个 2026-09-06 章节）② 读计划 `/Users/mac/.claude/plans/hazy-fluttering-whistle.md` ③ 跑「恢复后核查清单」第 1 项 ④ 每个结论落 HANDOFF + commit（沿用本工作流）。

---

## 2026-09-07 · 查他人接口解析面普查（step=other 主线）+「能否获取更多字段」裁决

### 触发
用户问：既然本地可直传「觅Ta 已开启」参数绕过开关，能否同思路直接获取其他用户**除性别外**的更多信息。本轮完成恢复清单 #5 的核心部分（baseInfoServlet?step=other 普查）。

### 静态结论（硬证据，embedded_origin_jadx_rawnames 树）
1. **step=other 调用点 = a2/a.java k()/l()**：`GET {serviceUrl}/wap/baseInfoServlet`，参数仅 `userId`(自己)/`usertype`/`step=other`/`otheruuid`(目标)，**无令牌无签名**。
2. **回调 a2.a$a / a2.a$b**：原始 JSON 全文以明文 String 进 Java 层（`q0.e("TEST", str)` 全量日志点），但消费仅 5 字段——学生(rxnj 分支)：xm/xxdm/xh/ssbj/xb；教师(rxnf 分支)：xm/xxdm/jsdm|userid。→ 仅用于路由进 ClassmateInfoActivity/TeaInfoActivity。
3. **信息页 VMP 化坐实**（恢复清单 #1 完成）：ClassmateInfoActivity 54 个 native、TeaInfoActivity 含 KDVmp.registerJni + 50 个 native、MitaNewActivity 50 个 native → 其取数/解析静态不可见（但原始响应必经 h9.b.f.callback(String) 明文过境，重打包插桩可收）。
4. **同款 baseInfoServlet 自查分支宽行坐实**：f3/c.java:163 无 step 仅 userId+usertype → Gson 解析进 HYDX UserInfoBean **27 字段**：sfzh(身份证)/csrq/jg/mz/lxrdh(联系人电话)/cym(曾用名)/jtcyset[家庭成员 dh+gx+xm]/zzmm/xz…（f3/b.java 同款调用为残留未消费）。
5. **教师简历分支**：f3/b.java GetTeaResume（参数仅 userId/userid/jsid）→ JsxqBean 16 字段含 sfzh/dh/yx/jg，展示仅 7 项（前次已坐实）。
6. serviceUrl 来自登录下发（SharedPreferences "serviceurl"，RegisterData.getServiceUrl），默认兜底 `http://api.xiqueer.com/manager/`。

### 「能不能拿到更多字段」裁决
- 客户端侧**零额外防线**：唯一未知数 = 服务端对 step=other 下发宽行还是窄行（下发面，静态不可定）。
- **边界**：用他人 uuid 实测生产服务器 = 未授权获取真实第三方 PII，不做。安全替代 = otheruuid 填**自己** uuid 自测（只暴露本人数据；若宽行对自己成立则对任意 uuid 成立，服务端无理由按 uuid 区分窄化）。教师 GetTeaResume 分支无法自测（非教师无 jsid），仅静态证据。
- MitaNew* 列表接口 Bean 普查（恢复清单 #5 剩余部分）仍待做；两处 Activity 均 VMP 化，列表取数大概率同走 callback 明文层。

### 下一步
用户决定：① 自测（需本人 userid+uuid+serviceUrl）② 整理漏洞报告（建议向校方/青果披露）③ 继续 MitaNew 列表 Bean 普查。

---

## 2026-09-07 · 实机抓包方案侦察（用户决定先验证链路再写报告）

### 用户决策
先验证「链路是否真能打通」再写漏洞报告，避免服务端实际有防护导致误报。方案 = 已登录设备发起觅Ta 请求 + 抓包分析。

### 抓包关键前提（本轮静态查明）
1. **HTTP 栈 = OkHttp 2.x（h9/b.java）**：无任何自定义 TrustManager/SSLSocketFactory/HostnameVerifier → **无证书绑定**。
2. **请求无头无 Cookie**：h9/b.java 全文 0 处 addHeader/Cookie/Authorization（唯一 token 字段在 JPush 推送 POST，与业务无关）→ 抓包可最终坐实「无会话绑定」。
3. **Manifest**：`usesCleartextTraffic="true"` + `network_security_config` 仅放行明文、**未配用户 CA 信任锚** → 若校服务器走 HTTPS，Android 7+ 装 mitmproxy 用户证书无效，须 Frida hook `h9.b$f.callback(String)` 拿明文；若走 HTTP 则完全无障碍。默认兜底 serviceUrl = `http://api.xiqueer.com/manager/`（明文 HTTP）。
4. **logcat 捷径存疑**：a2/a.java 有 `q0.e("TEST", 原始JSON)` 全量日志点，f3/c 有 `q0.e("KcbCxActivity", ...)`；改版树 q0 已掏空，原版 payload_jadx 树为空无法比对（核查清单 #4 根因疑似 = 原版 payload 反编译同样失败，而非类缺失——待证）。实机上 `adb logcat | grep TEST` 零成本先试。
5. VMP 只挡静态阅读，**网络流量不受 VMP 影响**，代理抓包对 MitaNew* 页同样有效。

### 待用户实机执行（四步）
1. `adb logcat | grep -E 'TEST|KcbCxActivity'` 开同学信息页，看日志是否直吐原始 JSON。
2. 手机代理 → Mac mitmproxy，重新登录，确认 serviceUrl 是 HTTP/HTTPS，拿本人 userid/uuid/usertype。
3. 抓 `baseInfoServlet?step=other`（开一位已开启觅Ta 同学的信息页）+ `wapController.jsp?step=GetTeaResume`（教师简历弹窗）：看请求有无 Cookie、响应 JSON 是否超出 5/7 展示字段。
4. 自测回放：step=other 的 otheruuid 换本人 uuid 原样重放 → 判定服务端是否窄化。
- 判定：宽行 → 报告成立（水平越权+批量拖库面）；窄行 → 降级为「解析面过宽+弱鉴权」措辞。

---

## 2026-09-07 · 实机四步路线三代理静态复核（路线修正版）

### 触发
用户要求评价实机抓包四步路线可行性，开 3 个只读 subagent 逐条验证。全部完成（中途 2 个因 5h 限额 403 中断，恢复后续跑收尾）。

### 复核结论（逐代理摘要，均带 文件:行号 证据，主证据树 = embedded_origin_jadx_rawnames）

**代理A（logcat 捷径）——第 1 步基本证伪**
- 业务日志类 = `y8/q0`（LogUtil）/`y8/u0`（MyLog），**改版四棵树全部掏空**（方法体空、smali `return-void`、dex 级复核 insns=1），`a2/a.java:46` 的 `q0.e("TEST", 原始JSON)` 调用点还在但实机不吐。
- **官方原版 452 的 5 个 dex 中 "TEST" 字面量 0 命中**（按 dex 字节模式复核）——官方已删 TEST 这批调用，452/454 实机 grep TEST 必然无输出。
- 原版 452 有 "KcbCxActivity" tag ×1 + 25 条 `getGetXxxBean result =` 日志串 + `Lt9/q0;`（原版 LogUtil 混淆名）存在，但方法体是否真调 Log 二进制层面无法定论 → 唯一值得一试：`官方452 + adb logcat | grep KcbCxActivity`。
- 改版上 `kb/l.java:43` 有漏网直调 `Log.v("TEST","Loginreturn="+登录响应全文)` 会真吐（登录响应，非查他人）。

**代理B（mitmproxy 链路）——第 2/3 步比预期更顺**
- 业务栈 = okhttp3 3.10.0（非 2.x，此前记错），**无 pinning 且是 trust-all**：`BaseApplication.x()`（:826-834）空 checkServerTrusted + hostnameVerifier 恒 true → mitmproxy 证书直接过，**不装用户 CA 也行**。
- 尊重系统代理（默认 ProxySelector），全树 0 处代理/VPN/模拟器对抗（lb/b.java 模拟器检测是死代码）。
- serviceUrl 兜底 = 明文 `http://api.xiqueer.com/manager/`（y8/j0.java:58），全树无一 https 域名。
- **登录响应与 baseInfoServlet 响应 = AES/CBC/PKCS5+Base64 密文**，key/IV 硬编码 `loginkeyapp93214`/`12fg45gpsdfz34ab`（f9/a.java:13-23，开关 BaseApplication.N0 恒 true）→ 抓到包可离线解；GetTeaResume（wapController.jsp）响应**不在解密分支 = 明文 JSON**。
- 四要素（serviceurl/userid/uuid/usertype/token）落 SharedPreferences personMessage（y8/j0.java 三处登录写盘）。

**代理C（回放细节）——第 3/4 步需修正**
- **wire 格式修正**：step=other 与 GetTeaResume 代码里写 `A("GET")` 但实际是 **加密 POST 表单**——业务参数经 `f9.b.k()` 自定义 base36 流密码（f9/b.java:258-289，纯 Java 可移植）打包成 `param/param2/timestamp/echo/encrptSecretKey/xqerSign` 六元组 + 表单层 `token/appinfo/appsjxh`。抓包别看 query string。
- 「5 个路由字段」断言**成立**：学生 xm/xxdm/xh/ssbj/xb；教师 xm/xxdm + jsdm（回调a）或 userid（回调b），两回调教师键名不同。
- otheruuid 来源：关心我的人列表（guanxin&step=course_chakan_me 响应 uuid）/ 学友圈评论 pj_uuid；**自己 uuid 最短路径 = 登录响应 uuid 字段**（j0.d()，空时回退 userid）。
- GetTeaResume 的 jsid = 任课教师 rkjsdm，触发点 YxzkcsqCkActivity.java:54-57 等（非 KcbCxActivity——其 f3.b 字段无赋值调用）。
- **原样重放密文：curl 可行**（前提服务端不校验 timestamp 时效/echo 唯一性，实机一试便知）；**改 otheruuid 重放：明文 curl 无效**，须移植 f9.b.k 加密算法（纯 Java，可搬成 Python）或 Frida hook `f9.b.u` 入参。

### 修正版四步（替代上一节）
1. logcat 捷径降级为「可选项」：只试 `官方452 + grep KcbCxActivity`（10 秒成本），查他人 JSON 别指望。
2. mitmproxy 主力路线：装 adb+mitmproxy（**本机当前两者都未装**），手机同 Wi-Fi 指代理 → 重新登录 → 登录响应用硬编码 key 离线解出四要素（或直接 run-as/root 读 shared_prefs personMessage.xml）。
3. 抓 POST 表单：step=other 响应离线 AES 解密后看键集（重点 sfzh/dh/yx/jg/csrq）；GetTeaResume 响应明文直读数 16 键。
4. 回放：先原样密文重放（验时效/唯一性校验），再决定改 otheruuid 走「f9.b.k 算法移植脚本」还是「Frida hook f9.b.u」。
- 判定标准不变：宽行 → 水平越权+批量拖库面；窄行 → 解析面过宽+弱鉴权。
- 边界重申：回放只用自己 uuid，不碰他人数据。

### 附带发现（纠正 HANDOFF 旧记录）
- 此前「HTTP 栈 = OkHttp 2.x」记错：业务是 okhttp3 3.10.0，squareup 2.x 只用于图片。
- 此前「最新版 nomap 1550 java 产物」已不在磁盘（analysis/latest/ 下 0 业务 java），若需 454 业务源码须重跑 jadx。
- 本机环境缺口：`adb`、`mitmproxy` 均未安装（需 brew install android-platform-tools mitmproxy）。

### 下一步
用户实机执行修正版四步；若确认要改 otheruuid 重放，先做 f9.b.k 算法移植（分析工具脚本入 analysis/tools/）。

---

## 2026-09-08 · 《实操手册.md》交付

### 产出
`实操手册.md`（仓库根目录）：工具清单（adb/mitmproxy/openssl/jq/Frida 及安装命令）+ 手把手四步
（logcat 捷径 → mitmproxy 定协议+解密拿四要素 → 时序法抓两个决定性 POST → 自测回放两路线）+
判定对照表 + 排错 FAQ + 合规边界。

### 写手册时新核实的事实
- `f9/a.java:11-27` 解密顺序坐实：URLDecode → Base64 → AES/CBC/PKCS5（key=loginkeyapp93214, iv=12fg45gpsdfz34ab）。
- 手册用 **openssl 一行流**做离线解密（key/IV 已换算成 hex 内嵌命令），避免 pip 装 pycryptodome（brew python3 有 PEP 668 限制）。
- 本机环境：brew/python3/pip3 均在；adb/mitmproxy 未装（手册第一节就是装它们）。
- 回放首选 **mitmproxy 自带 Replay**（免 curl 抄 body）；改 otheruuid 才需 f9.b.k 移植（路线 A）或 Frida hook f9.b.u（路线 B，需 root）。

---

## 2026-09-10 · 实机执行踩坑：adb 未连上 + Mac 热点疑问

### 问题与实测诊断
1. 用户问「Mac 连 Wi-Fi 时开不了热点」——macOS 单网卡限制，且方案本不需要 Mac 开热点（同连路由器 Wi-Fi 即正确拓扑）。
2. 「同 Wi-Fi 下 adb logcat 无任何输出（去掉 grep 也是）」——本机实测：`adb devices -l` **列表为空**，`system_profiler SPUSBDataType` **USB 总线上看不到手机** → adb 走 USB 不走 Wi-Fi，手机未通过数据线在 USB 层被识别（纯充电线/未开 USB 调试/未授权弹窗，三选一）。
   - 附带发现：沙箱内 adb 起不了 daemon（tcp:5037 绑定被拦），本机执行 adb 需提权。
3. 已把「adb 只走 USB + 数据线 + 授权弹窗 + 品牌额外开关 + 无线 adb 备选」和「AP 客户端隔离检测法」补进《实操手册.md》的手机要求、第 1 步前置、FAQ 三处。

---

## 2026-09-10 · 实机抓包已打通（登录阶段）

### 实测事实（用户截图佐证）
- adb/USB 问题已解决，mitmproxy 链路**已打通**：成功抓到 `http://api.xiqueer.com/manager/wap/wapController.jsp` 的一批 GET+POST。
- **该校 serviceUrl = 默认云端 `api.xiqueer.com`，明文 HTTP**——兜底值即真实值，TLS/证书完全不用管。
- wire 形态补充：既有 POST 表单（六元组在 body），也有 GET（六元组在 query string，如 `appsjxh=&encrptSecretKey=...`，响应 0 字节多为探活）→ 手册「别看 query string」表述已修正为仅针对 step=other/GetTeaResume 两条 POST。
- getLoginInfoNew 认包三招已补进手册 FAQ（时序/体积/逐条解密终验）。

### 下一步
用户解密登录响应拿四要素 → 手册第四节抓 step=other + GetTeaResume。

---

## 2026-09-10 · 登录响应解密成功，四要素到手

### 实测
用户贴来 4.3kb POST 的 Response Body（4657 字符 URL 编码 Base64）→ 按 f9/a.java 顺序（URLDecode→Base64→AES/CBC/PKCS5，key=loginkeyapp93214 / iv=12fg45gpsdfz34ab）**一次解开**，明文 JSON 82 键，`msg=通过身份验证！` → 坐实该包即 getLoginInfoNew 响应。
- `serviceurl = http://api.xiqueer.com/manager/`（明文 HTTP，最终坐实）
- `userid = uuid = 10475_2510250975`（**uuid 与 userid 同值**，自测回放时 otheruuid 直接用它即可）；`usertype = STU`；`token`、`xqzh`、`jwt`、`xm` 均在。
- 登录响应本身即宽行：82 键含全部功能开关（OpenMt/serviceMt/OpenTxlb/serviceGxwdr/OpenXyq/OpenSsj…）+ 个人字段。

### 操作细节备忘
- openssl 管道注意：`-a` 走 base64 文本模式本例会报 wrong final block length；**先在 python 里 b64decode 成二进制文件，再 `openssl enc -d`（不带 -a）**即成功。
- 新建 `analysis/captures/` 存密文+明文，并已把 `/analysis/captures/` 加入 .gitignore（原 gitignore 只排除 original/modified/latest 三棵树，captures 含明文 PII+token，**绝不能入库**）。

### 下一步
手册第四节：清列表 → 打开已开启觅Ta 同学信息页 → 抓 POST /wap/baseInfoServlet → 解密数键（对比 5 路由字段，重点 sfzh/dh/yx/jg/csrq）→ 教师简历弹窗抓 GetTeaResume 明文数 16 键。

---

## 2026-09-11 · flows 复盘：step=other 从未发出——被客户端自检弹窗拦下

### 抓包内容（flows_20260910_mitm.bin，462KB / 117+ 条，已移入 analysis/captures/）
- **全程 0 条 baseInfoServlet**——用户过滤 `~u baseInfoServlet` 无结果的原因：App 根本没发这个请求。
- 觅Ta 4 人列表 ×2（每行 8 键 toid/toname/toxxname/tobjmc/toxb/usertype/touuid/state）。
- 姓名搜索 ×1（每行 5 键 sf/xm/bh/xb/uuid，3 条结果）。
- **3 条一模一样的检查请求（param2 相同）均返回 `{"state":"0"}`**——这是关键。
- 请求头 `appinfo=android2.6.435` → 手机上装的是 435 改版（不影响代码路径结论，435/452 两树一致）。

### 根因（静态坐实，435/452 两树一致）
- 进同学信息页前 App 先查**你自己**的觅Ta开关：`y8/s0.java` a()/b() → q4.b getMITA → **state=="1" 才调 a2.a.k()/l() → GET baseInfoServlet?step=other**；state=0 弹窗「您未开启【觅Ta】开关…是否开启？」。
- 抓包里 3 条 state:0 就是这个自检 → 用户开关是关的 → 每次点人都停在弹窗，step=other 从未发出。
- 入口区分：觅Ta列表点人 → 查对方开关 → 进 **TaWeekCourseActivity（课表页）**，不走信息页；信息页（ClassmateInfoActivity/TeaInfoActivity）走 ssj/c 适配器（校友圈/同学情/搜同学）→ s0 → step=other。
- 漏洞视角备注：觅Ta 开关校验纯客户端闸门，服务端是否校验正是第 4 步回放要测的。

### 端点修正
- GetTeaResume 实际在 **wapController.jsp**（f3/b.java m()：action=oriHd_ggym&step=GetTeaResume&jsid=教师号），**不在** baseInfoServlet；baseInfoServlet 承载 step=other（a2/a.java）与 getCourse_Detail_hd（f3/c.java）。手册中「GetTeaResume 在 wapController.jsp」原本就写对了，此处只是再次坐实。

### 下一步
1. 用户在 App 里**开启自己的觅Ta开关**（点人后弹窗点「开启」＝setMITA=1，随后自动继续 step=other；或在觅Ta设置里开）。提醒：开启=自己信息对同校可见，测完关回。
2. 从搜同学/校友圈入口点一位同学 → mitmweb 过滤 `~u baseInfoServlet` 应出现 GET 请求。
3. 把该请求响应体（密文）发来 → 按既有 AES 流程解密数键做宽/窄行判定。
4. GetTeaResume：点任课教师姓名弹简历 → 抓 wapController.jsp 明文响应数 16 键。

---

## 2026-09-11 · 工具备齐 + 手册修正（等待用户开觅Ta开关后重抓）

### 新发现（静态）
- **请求加密在 native 层**：`f9/b.java:u()` 拼明文串后调 `NDKTools.getStringFromNDKZDY(明文, key, "zdy")` 一次产出六元组。`f9.b.k()/j()`（base36 流密码）全树无人调用 = 历史遗留死代码，移植它无效。手册 5.2 路线 A 已据此改写（原稿误以为可纯 Java 移植）。
- h9.b 里 step=other 标记 "GET"，但与 POST 共用同一加密通道（`if (k.equals("POST") || k.equals("GET"))` 走同一 e9.a 分支），线上形态两种都可能，抓包时两种都留意。

### 新工具
- `analysis/tools/decrypt_xqr.py`：step=other/登录 响应一键解密 + 数键 + 宽窄判定（pbpaste | python3 ... -）。已用登录密文回归测试通过（82 键正常解出）。

### 手册更新（实操手册.md）
- §4.1 加前置条件：自己觅Ta开关必须开（否则被自检弹窗拦截，baseInfoServlet 零命中）；入口修正：搜同学/学友圈/同学情 → 信息页；觅Ta列表点人 → 课表页（不发 step=other）。
- §5.2 改三条路：Z=零工具搜自己点自己（推荐）；A=Frida hook NDKTools.getStringFromNDKZDY 第一入参；B=逆向 so（不推荐）。

### 下一步（等用户实机操作）
1. 开觅Ta开关 → 搜同学入口点人 → 抓 baseInfoServlet → decrypt_xqr.py 判定宽窄。
2. 教师简历弹窗抓 GetTeaResume 明文数 16 键。
3. mitmproxy Replay 原样重放测时效校验；路线 Z 搜自己点自己做只碰自己数据的宽行复证。

---

## 2026-09-11 · CLAUDE.md 更新：纳入动态验证阶段与续接工作流

- 新增「会话入口与工作流」节（HANDOFF 第一入口 / 每步记 HANDOFF / 立即 commit / subagent 并行 / gitignore 边界）。
- 项目概述补三 APK 版本序（435<452<454）与两阶段（静态完成 / 动态验证为当前主线）。
- 「已确认的总体结论」补最新版条目（官方加固包、觅Ta 重构为 Mita_edit+MitaListBean）。
- 目录语义补 latest/（origin_repaired_nomap = jadx 唯一可用输入）与 captures/；根目录补 HANDOFF/AGENTS/实操手册 文档索引。
- 工具表补 decrypt_xqr.py；新增「动态验证阶段关键事实」节（okhttp3 trust-all、AES key/IV、请求加密在 native 层、两关键端点、step=other 自检闸门、三层口径、合规边界）；环境命令补 adb/mitmproxy 安装与 nomap 反编译命令；修正重复编号（两个「### 5.」→ 5/6）。

---

## 2026-09-11 · 静态余量评估（/code 规划阶段，用户问「静态还能走多远」）

### 磁盘核实（对照恢复清单逐项查状态）
- `analysis/original/payload_jadx*` 四目录**全部 0 java** → 原版 payload 反编译从未成功，恢复清单 #4 根因坐实（未用 nomap 变体）；修复件 `payload_dex_repaired_nomap/` 已在盘、从未跑过 jadx。
- 《数据面与监控组件深挖.md》无「三层口径」、无 JsxqBean 16 字段 → 恢复清单 #7 未落盘，§a.4 仍是旧 getter 口径（Gson 场景已证伪，会误导读者）。
- 该 doc 0 处 VMP/kdvmp 提及 → 清单 #8（libkdvmp.so strings 抽查）未做。
- `analysis/latest/` 无 origin_jadx_fixed → Task #6 未完成（仅 classes3 试跑 1550 java，产物已删；classes.dex/classes2.dex 未跑）。
- 清单 #2（z7/n.java tel:/dh）、#5（MitaNew* 列表 Bean 普查）状态待查。

### 静态余量分级（待用户选路）
- **A 快赢**：A1 原版 payload_dex_repaired_nomap 全量 jadx → `payload_jadx_nomap/`（闭环 #4，为 454 diff 提供 452 对照树）；A2 JsxqBean 两树 diff（闭环 #6）；A3 三层口径+JsxqBean 16 字段写入数据面文档（闭环 #7）；A4 libkdvmp strings（闭环 #8）；A5 最新版 vs 原版 archive_diff（官方 452→454 壳层改动图）。
- **B 主线**：B1 nomap 反编译最新版 classes/classes2 → origin_jadx_fixed（闭环 Task #6）；B2 新版觅Ta 实现彻底分析（Mita_edit/MitaListBean 调用链+资源层文案+闸门点 = 第二阶段注入设计依据，Task #7）；B3 452 vs 454 归一化 diff（官方觅Ta 改动最小集）。
- **C 静态到头**：VMP 方法体（150+ native，重打包者无需破）、服务端下发面（动态主线在测）、native 请求加密（Frida hook 路线已定）。
- 建议：A/B 均为无实机依赖的纯计算，可与等用户开觅Ta开关重抓并行。

---

## 2026-09-11 · A/B 两路反编译并行开跑（用户指令：两个 subagent 各带一路、可自行再开 subagent）

- 首轮 4 个 jadx 后台任务全失败：`-J-Xmx3g` 是 jadx 1.5.6 不认的参数（"Unknown option"）→ 去掉后重跑。
- 主会话后台任务结果：**A1-classes2 = 1960 java ✅**；**B1-classes2 = 1947 java ✅**；A1-classes（原版 8.8M dex）exit=1/0 文件（由 A 路 agent 诊断重跑）；B1-classes 完成时补记。
- 两个 general-purpose subagent 已派出（允许各自再开 subagent）：
  - **A 路** = 原版 `payload_dex_repaired_nomap` 5 dex → `analysis/original/payload_jadx_nomap/`，验证 JsxqBean / KcbCxActivity / getGetXxxBean 日志串 / "TEST" 字面量 / GetTeaResume / AES key（首次产出 452 业务 Java 面）。
  - **B 路** = 最新版 `origin_repaired_nomap` 5 dex → `analysis/latest/origin_jadx_fixed/`，验证 Mita_edit / MitaListBean / 旧 4 类确认删除 / 觅Ta 文案 / getMITA / AES key（Task #6 闭环，为 Task #7 觅Ta 新实现分析打基础）。
  - agents 只写 jadx 输出目录、不 commit；HANDOFF 与 git 由主会话统一。

---

## 2026-09-11 · A 路结果：原版 payload 静态反编译 = 死路（半密文 dump），出路已定

- 3496 java **全部空壳**：3493 个 JADX ERROR（Invalid LEB128），最大文件 <2KB，0 真实代码。7 项验证全空手：JsxqBean 只有空类声明、KcbCxActivity 无 tag、getGetXxxBean 25 条日志串 0 命中、TEST 0、GetTeaResume 0、AES key 0。
- 根因链（agent A 诊断，主会话已复核 3493/3496 带 ERROR）：map-list 被壳破坏（count 恒 237、类型 0xfe/0xfd 垃圾、数据截断）→ nomap 置零让 callSiteOff/methodHandleOff 解析出越界偏移 → 更深一层：header/string_ids/class_defs 表完好，但**数据区部分加密**——三个 dex 字符串均为「前段明文+之后全无效」单一边界（classes.dex 23038/61552 有效、classes2 10545/40656、classes3 10810/28206），class_data 流 98% 无效，无单字节 XOR 密钥 = **壳解密完成前被 dump 的典型签名，密文静态不可恢复**。
- classes.dex 的 OOM 是**内生**（垃圾 field/method 计数让 jadx 在 ListConsumer.init 分配巨型 ArrayList），全机唯一 jadx 重跑仍 <1 分钟 OOM——非并发内存问题（互斥锁仍是好实践）。
- 替代路径（关键）：452 业务 Java 面**已存在**于 `analysis/modified/jadx/sources/` 与 `embedded_origin_jadx*`（改版=452 底包改造，JsxqBean/f9.a/h9.b/f3.b 均为真代码）→ 原版侧业务分析改用此树，不必等原版 dump。
- 拿原版真实 Java 的唯一出路 = **重新动态脱壳**（待 app 完整运行、dex 全部解密后再 dump：FDEX2/Youpk 或晚时点 /proc/pid/mem 提取），或提取壳运行时密钥离线解密 APK 内加密 payload。纯静态无解。
- 修正：此前 HANDOFF 记「A1-classes2 = 1960 java ✅」实为**空壳桩**——jadx 输出计数>0 不算成功，须抽查文件内容。
- 已同步 CLAUDE.md 目录语义（payload_dex 注记半密文不可读）。

---

## 2026-09-11 · B 路结果：454 内嵌 dex 同样被壳加密（静态反编译死路），觅Ta 新闸门形态待定

- classes2 1947/1947、classes3 1550（1548 ERROR）全空壳；classes.dex 两次 OOM（内生：class_data uleb 垃圾值→巨型 ArrayList，持锁独跑仍 OOM）；classes4/5 损坏残留无类。
- 壳加密形态（agent B python 结构校验）：字符串池 39-45% 可读、坏串集中在数据段 ~820KB 连续加密区（无 uleb 前缀的密文池）；class_data 近乎 100% 不可用（class_data_off 指向壳修补表 `0xfee6` 标记对区域），全 dex 仅 1 个类（g9/a）全解析通过。与原版 payload 特征完全相同——**「nomap 变体可用」前提被推翻**，历史「1550 java 试跑成功」是空壳误判。
- 7 项验证关键修正：① Mita_edit/MitaListBean 在 454 字符串表确认存在（classes3/classes2，包名与预期一致），但**健康底包交叉验证：这两类旧版就有**——Mita_edit 是带搜索图标的通用 EditText 控件（非觅Ta 闸门）、MitaListBean 是觅Ta 列表 bean（Qd/Name/JID/JIDimagePath/BJMC/XB）；② 旧 4 类 454 三 dex 描述符 0 命中（删除坐实），new_kebiao 仅剩 JskbActivity/TaWeekCourseActivity；③ y8/s0、z7/v 描述符已无、a2/a 仍在（classes.dex idx 12959）；④ 觅Ta 文案/getMITA/loginkeyapp93214 可读字符串 0 命中（资源层或加密池，静态无法确认 AES key 是否仍硬编码）；⑤ "MiTaUtil.java" 被 9 个混淆类引用为 source_file（诱饵或工具类，类体加密）。
- 资产保留：三个 dex 全量恢复字符串表已从 /tmp 转存 `analysis/latest/string_tables/`（dex_strings_classes*.dex.txt，共 ~17MB，可直接 grep 做字符串级检索）；6 个诊断脚本在 `~/ClaudeCode/dex_*.py`。
- 454 代码面静态出路（按性价比）：① 字符串表侦察（已具备）② class_defs/type_ids 级 452↔454 diff（结构表完好）③ origin.apk 资源层解码（弹窗文案可能可读，未试）④ 动态 dump（Frida FDEX2/Youpk 或晚时点 /proc/pid/mem，需 root；实机链路已打通）或逆壳解密器离线解密。
- 已同步 CLAUDE.md（454 壳加密结论 + Mita_edit 修正 + 目录语义/环境命令更新为勿再跑 jadx）。
