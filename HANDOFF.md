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
