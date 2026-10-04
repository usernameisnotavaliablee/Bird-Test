# 觅Ta 服务能查出目标哪些值（除课表外）· 2.6.454 静态普查

> 目标：把「觅Ta 相关链路能拿到的**目标（他人）** 字段」穷举出来，明确区分 **展示面 / 解析面 / 下发面**，并标出 VMP 静态不可达的边界。
> 证据源：454 官方包**明文 dex** 的 jadx 产物 `analysis/latest/plain_jadx/sources/`（10,388 java）、454 资源 `analysis/latest/jadx/resources/`、452/435 对照树 `analysis/modified/embedded_origin_jadx|jadx/`。
> 日期：2026-10-04。方法：全树 grep + 逐类读 + (action,step) 全量清单（脚本口径见 §7）。

---

## 0. 结论速览（除课表外，能查到目标什么）

| # | 值 | 载体端点 | 静态证据强度 |
|---|---|---|---|
| 1 | **姓名** `xm` | baseInfoServlet?step=other / 觅Ta 搜索列表 | 强（Java 可见解析） |
| 2 | **性别** `xb` | 同上（列表 + 信息页性别图标） | 强 |
| 3 | **头像**（uuid 派生 URL `/…/headavatar/<xx>/<yy>/<uuid>_64x64.jpg`） | 同上 | 强 |
| 4 | **学号 / 工号**（`xh` / `jsdm` / `userid`，JID=`xxdm_xh`） | 同上 | 强 |
| 5 | **学校代码** `xxdm` | 同上（并用于同校校验） | 强 |
| 6 | **院系** `yx` | 档案接口（MitaNewActivity 回调） | 强 |
| 7 | **专业** `zy` | 同上 | 强 |
| 8 | **入学年级/入校年份** `rxnj`（"XX级"）/ `rxnf` | 同上 + 信息页分流键 | 强 |
| 9 | **所在班级** `ssbj` | 同上 | 强 |
| 10 | **觅Ta 开关状态** `state` / `mita` | getSettings&step=getMITA|getMITAWithOther | 强 |
| 11 | **黑名单关系** `flag` | action=judgeBlackList | 强 |
| 12 | **教师公开简历**：性别/出生年月/学历/学位/入校年份/民族 | oriHd_ggym&step=GetTeaResume | 强（展示面 6 项） |
| 13 | **教师简历解析面扩展字段**：**身份证号 sfzh** / **电话 dh** / 籍贯 jg / 年龄 nl / 职称 zc / 岗位 gw / 照片 img / 院系 yx / 是否在岗 sfzg | 同一响应，Gson 转 `JsxqBean.ResultSetBean` | 强（Bean 有字段，全树 getter 0 调用）／下发面未知 |
| 14 | **课程详情**（点课表内某门课）：`KcxqCopyBean` 课程名/英文名/承担单位/简介/学分/总学时/上机学时/其它学时/课程代码/先修课程/替代课程/教材（名称·代码·出版社·定价） | oriHd_kc&step=getCourse_Detail_hd | 强 |
| 15 | **收藏课程**（对方收藏的课） | kingo_course&step=course_shoucang_* | 中（u8/v.java 可读） |
| 16 | **学期列表** `xnxq[{dm,mc}]`、**节次/教室** `jcbw/jcsw/jcws/jcxw/jczs/jczw/jcflag` | 课表链路（本条属课表，列出仅为完整） | 强 |
| 17 | **籍贯 / 专业 / 入学年级 / 姓名 / 性别 / 身份** | **作为搜索条件**（=服务端可检索字段，可当"验证 oracle"用） | 强（布局恒定） |
| 18 | 个人相册 / 随手记 / 跳蚤市场 | 他人信息页内嵌区（layout 有 id） | 弱：客户端有"功能不可用！"文案 |
| 19 | 他人信息页**动态明细行**（任意 label:value，schema 见 §3） | baseInfoServlet?step=other 响应 → native 行构造器 | **静态不可读（VMP）** |
| 20 | **同班同学名录**：姓名/性别/班级/用户学号/入学时间/是否在住 | `StudentListActivity` ← `StudentListBean.classmatesList[]` | 强（Gson，Java 可见） |
| 21 | **扫码身份页**（`hqsf xqxt\|<uuid>`）：学校/工号/学号/姓名/身份 | `GrxxActivity`（布局 `activity_grxx.xml`） | 强（布局静态 5 行） |

**明确查不到（静态 0 证据）**：身份证号（学生）、高考号、政治面貌、出生地、生源地、毕业中学、邮箱、家长/家庭信息、地址、宿舍、成绩、考勤、借阅——**觅Ta 链路上不存在对应端点**；这些字段仅在「查自己」或教师端页面出现（`activity_person_stu_information.xml` 等）。
**唯一例外**：教师简历端点（第 13 行）的解析面里**有** `sfzh`/`dh`/`jg`——是否真下发需实测。

---

## 1. 觅Ta 服务边界（入口 → 请求）

| 入口类（454） | 作用 | 发出的请求 |
|---|---|---|
| `MitaNew2Activity`（新搜索页） | 按条件找 Ta | 搜索请求**构造代码是 native**（`k2()/l2()/o2()/p2()`），仅回调可见：响应 `{result:{flag,msg,data[]}}`（`MitaNew2Activity.java:266-288`）；`xnxq` 学期下拉（:184-189） |
| `MitaNewListActivity` | 搜索结果列表 | `wapController.jsp action=getSettings step=getMITA`（`MitaNewListActivity.java:120-132`）；列表项 = `BbsBean` |
| `MitaNewActivity`（旧档案页） | Ta 的档案 | `getMITA`（:422-434）；档案数据回调 `i`（:455-470）→ `rxnj/yx/zy/ssbj`；筛选下拉 `resultSet[{nj}]`、`[{dm,mc}]`、`xnxq`（回调 `j/k/l`） |
| `ClassmateInfoActivity`（学生信息页） | 目标详细信息 | `baseInfoServlet step=other`（`t9/t0.java:82,166` → `e2/a.java:585/601/617`）；`judgeBlackList`（:534/645）；**自身另有一条 native 主信息请求（回调 `l`/`m`），URL 静态不可见，见 §5 证据等级** |
| `TeaInfoActivity`（教师信息页） | 同上 | 同上 + `GetTeaResume`（`x3/b.java`） |
| `TdkbActivity` / `TaWeekCourseActivity` | 课表（排除项） | `resultSet`/`state`；`xnxq` + 节次字段 |
| `x3/b`（JsxqDialog） | 教师简历弹窗 | `oriHd_ggym&step=GetTeaResume&jsid=&userid=`（:151-167） |
| `x3/c`（KcxqDialog） | 课程详情弹窗 | 先查**自己** `baseInfoServlet`（取 xh）→ `oriHd_kc&step=getCourse_Detail_hd&kcid=&xgh=`（:171-186） |
| `u8/v`（TdkbListItemAdapter）/ `u8/f`（ClassmateGridItemNewAdapter） | BbsBean 列表项渲染 + 点人 | `getMITAWithOther`（`u8/v.java:518-535`）→ 再进信息页 |
| `t9/t0`（MiTaUtil，原 y8/s0） | 门禁判定 | 门禁通过后调 `e2.a.l/m/n` 拉 `step=other` |
| `e2/a` 回调 `d`（二维码 `hqsf xqxt\|<uuid>`） | 扫码看某人 | `step=other` → `GrxxActivity`（`t9/z.java:96-101`） |
| `w8/b`（ClassmateListItemNew2Adapter） | 同学列表点人 | 教师→直接周课表；学生→`getMITA` 门禁（:130-144） |
| `ClassmatesGridActivity`（同学网格） | 点人**直接跳信息页、不经任何开关闸门**（:96-105） | 无请求 |
| `StudentListActivity`（同班同学列表） | 班级同学名录 | Gson→`bean/StudentListBean`：`classmatesList[].xm/xb/bjmc/yhxh/entertime/islive`（回调 `b`，:54-79） |
| `l5/a`（看过我的）/ `l5/b`（收藏我的） | 访客/收藏列表 → 点人 | 查自己 `guanxin&step=course_chakan_me / course_shoucang_me`；点项 → `e2.a.l`（`step=other`，`l5/a.java:53`、`l5/b.java:53`） |
| `ssj/c`（留言/动态列表，被信息页复用） | 点头像/昵称 | → `t9/t0` 闸门 → `step=other`（`ssj/c.java:329-338,588-598`） |
| `GrxxActivity`（扫码落地身份页） | 扫 `hqsf xqxt\|<uuid>` 看某人 | `step=other`（`t9/z.java:96-101`）；布局 `activity_grxx.xml` 显示 **学校/工号/学号/姓名/身份** 5 行 |

---

## 2. 每个端点的解析面（Java 可见的取键）

| 端点 / action / step | 参数 | 454 里被读取的键 | 证据 |
|---|---|---|---|
| `/wap/baseInfoServlet` `step=other` | userId, usertype, **otheruuid** | **无 Bean，裸 JSONObject**：`xm` `xb` `xxdm` `xh` `jsdm` `userid` `ssbj`（`rxnj`/`rxnf` 只作 `has()` 分流：有 rxnj=学生页、有 rxnf=教师页）；信息页另有 `uuid` `mita` `state` `flag` | `e2/a.java:72-270`（三回调 b/c/d）、`:585-629`；`ClassmateInfoActivity.java:552-627,663-738`；`TeaInfoActivity.java:436-…` |
| 同学列表项（`ClassmateListItemNew2Adapter`） | — | `xm`（姓名）`yhxh`（学号）`bjmc`（班级）`xb` | `w8/b.java:118-146` |
| `/wap/wapController.jsp` `getSettings` `getMITA` | userId=`xxdm_对方id`, usertype | `state`/`resultSet` | `e2/a.java:543-557`；`MitaNewActivity.java:419-435`；`w8/b.java:133`；`j5/b.java:96` |
| `…` `getSettings` `getMITAWithOther` | userId, usertype, **other** | `state` | `e2/a.java:434-450`；`u8/v.java:518-535` |
| `…` `getSettings` `setMITA` | — | 设置自己的开关 | `j5/b.java:112` |
| `…` `judgeBlackList` | touserId, tousertype | `flag`（0=正常，非 0=拦截） | `e2/a.java:563-582` |
| `…` `oriHd_ggym` `GetTeaResume` | userid, jsid | `resultSet[0]`：`csrq` `dh` `gw` `img` `jg` `mz` `nl` `rxnf` `sfzg` **`sfzh`** `xb` `xl` `xm` `xw` `yx` `zc` | `x3/b.java:150-167`；Bean `bean/HYDX/bean/JsxqBean.java` |
| `…` `oriHd_kc` `getCourse_Detail_hd` | kcid, xgh | `KcxqCopyBean`（resultSet[0].cddwdm / xxkcset …） | `x3/c.java:121-133,171-186` |
| `…` `kingo_course` `course_shoucang_*` | fromid, toid | 收藏列表/删除 | `u8/v.java:540-556` |
| 档案接口（native 构造请求） | — | `rxnj` `yx` `zy` `ssbj`；`resultSet[{nj}]`、`[{dm,mc}]`、`xnxq` | `MitaNewActivity.java:455-650` |
| 课表 | — | `resultSet`、`state`；`xnxq[]`、`jcbw/jcsw/jcws/jcxw/jczs/jczw/jcflag`、`qssj/jssj/zc` | `TdkbActivity.java:74`；`TaWeekCourseActivity` |

**响应加密**：`da/b.java:306-307` 对 `/wap/baseInfoServlet` 与 `getLoginInfoNew` 的响应做 AES 解密（key `loginkeyapp93214` / iv `12fg45gpsdfz34ab`）→ 抓包必须解密（工具 `analysis/tools/decrypt_xqr.py`）。

---

## 2b. 响应 Bean 字段表（解析面全集）

> 口径：**Gson 反射直写 private 字段、不走 getter** → 「getter 调用数=0」只证明**展示面不读**，不代表字段不存在或不下发。

**① `HYDX/bean/JsxqBean.ResultSetBean`（教师简历，16 字段）** — 请求见 §2；`x3/b.java:136-141` 只显示 7 项。

| 字段 | 中文 | 454 是否上屏 |
|---|---|---|
| csrq | 出生年月 | ✅ `x3/b.java:137` |
| mz | 民族 | ✅ `:141` |
| xl / xw | 学历 / 学位 | ✅ `:138` / `:139` |
| rxnf | 入校年份 | ✅ `:140` |
| `f18569xb`(xb) | 性别 | ✅ `:136` |
| xm | 姓名 | ✅（由调用方 `:130` setText） |
| **sfzh** | **身份证号** | ❌ 0 调用 |
| **dh** | **电话** | ❌ 0 调用 |
| jg | 籍贯 | ❌ 0 调用 |
| nl | 年龄 | ❌ 0 调用 |
| gw | 岗位 | ❌ 0 调用 |
| `f18570zc`(zc) | 职称 | ❌ 0 调用 |
| yx | 院系 | ❌ 0 调用 |
| img | 头像图 | ❌ 0 调用 |
| sfzg | （在岗/资格，无字面量） | ❌ 0 调用 |

> 另：`x3/b.java` onCreate 里第 8 个 TextView `f48922h`（id `2131299178`）**全类无 setText** —— 布局留了一行但代码不填。

**② 三个 `UserInfoBean`（本人信息 Bean，**不属** step=other 链路）**

- `bean/jsjy/bean/UserInfoBean`（26 字段，解析点 `JSJY/activity/JsjysqdActivity.java:53`）与 `bean/HYDX/bean/UserInfoBean`（27 字段，7 个解析点）字段基本同构：`sfzh gkksh jg csrq mz zzmm zy yx rxnj(xznj) xh xm xb uuid userid xxdm xxmc ssbj syd byzx cym xz initqx mita lxrdh dminfo jtcyset`。
- `bean/UserInfoBean`（根包，含 `csd` 出生地 / `lxr` / `lxryj` 邮箱）在 454 是**死代码**（`PersonSTUInformationActivity.java:186` 声明后无赋值无读取）。
- **敏感 getter 454 全树调用统计**（CALLS）：`getSfzh` **0**、`getJg` **0**、`getZzmm` **0**、`getGkksh` **0**、`getCsd` **0**、`getLxryj` **0**、`getJtcyset` **0**（家庭信息三通道全未读）、`getSfzg/getNl/getGw` **0**；`getDh` 7 处但全属 `XzXsDate`/`JftemBean`（考勤/缴费），三个 `JtcysetBean.getDh` 与 `JsxqBean.getDh` 均 0。
- 敏感字段里**唯一上屏**：`HYDX.UserInfoBean.getLxrdh()` → `JsjysqdActivity.java:750`（就业意向，**查自己**）。
- `getJtdz`（家庭地址）/`getDz`（地址）/`getJz`（家长）在 454 **连字段都不存在**。

**③ `BbsBean`（觅Ta/他人列表卡片，22 字段全混淆，native 填充）** — Java 侧无 Gson；`toString` 字面量与实际用法**5 处冲突**（引用需谨慎）：

| 字段 | getter | 实际语义（按调用点断言） |
|---|---|---|
| f35944f | `i()` | **姓名**（→ `intent "Name"`、`MitaListBean.Name`） |
| f35945g | `b()` | **他人 uuid/JID**（→ `map.put("other",…)`、`xxdm+"_"+…`） |
| f35951m | `q()` | **性别**（与 `"男"/"女"` 比较） |
| f35952n | `n()` | **班级名称**（→ `intent "BJMC"`） |
| f35949k | `l()` | **身份 STU/TEA** |
| f35939a | `j()` | 用户类型（→ `usertype`，与 toString 字面量 `mUserType` 一致） |
| f35954p | `h()` | **头像文件名**（拼 `_64x64.jpg`） |

> ⚠️ 命名陷阱：`bean/jsjy/bean/MitaListBean`（Qd/Name/JID/JIDimagePath/BJMC/XB）**不是觅Ta 搜索结果 Bean**，它是就业（JSJY）经办人列表用的，构造于 `JbrListActivity.java:69`、消费在 `JsjysqdActivity.java:940`（native）。觅Ta 列表用 `BbsBean`。

**④ `HYDX/bean/KcxqCopyBean`（课程详情，13+9 字段）** — `x3/c.java:121` 解析，`y3/a.java` 表头显示：`kcmc` 课程名称、`kcywmc` 英文名、`cddwmc` 承担单位、`kcjj` 课程简介、`xf` 学分、`zxs` 总学时、`sjxs` 上机学时、`qtxs` 其它学时、`kcdm` 课程代码、`xxkcset` 先修课程、`tdkcset` 替代课程、`ckjcset` 教材（`jcmc/jcdm/cbsmc/dj`）。同名 `KcxqBean`（resultset 小写）全树 0 引用。


---

## 3. 展示面：他人信息页到底显示什么

`res/layout/classmate_info.xml`（454，与 452 一致）结构 = 固定头 + **动态行列表** + 社交区：

| 区块 | 控件 id | 内容 | 来源键 |
|---|---|---|---|
| 头部 | `contactAvatar_img` | 头像图 | `uuid` → `/_data/mobile/headavatar/<xx>/<yy>/<uuid>_64x64.jpg`（`ClassmateInfoActivity.java:577-587`） |
| | `contactAvatar_xb` | 性别图标（男/女 drawable） | `xb`（:565-575） |
| | `contact_nickname_tv` | 昵称 | `xm` |
| | `contact_id_tv` | 账号（`classmatelist_item.xml` 静态标注"昵称/账号"） | native |
| | `kb_button` | 课表入口（默认 gone） | — |
| 明细 | `classmateInfoList` | **动态行**：`HashMap{tag=标签, content=值, image=图标, dh?, jsdm?}` | native `y2()` |
| 社交 | `gallery`/`picture_grid` | 个人相册（默认 gone） | native |
| | `classmate_album_lable2` "随手记" / `classmate_album_lable3` "跳蚤市场" | 入口按钮 | native |

**动态行 schema（可读，`u8/n.java:258-294`）**：
- `tag` = 左列标签文本；`content` = 右列值；
- `dh=="1"` → 该行可点击**拨号**（`tel:` 意图，`u8/n.java:282-284`）；
- `jsdm` 非空 → 该行可跳**教师课表**（`wdkb` 场景）；
- `tag=="链接"` → 显示为"网课："，可点开 URL；`tag=="教师："` → 教师行。

> 关键推论：行构造器对 `tag`/`content` **不做字段白名单**——服务端下发什么标签/值，就能显示什么（含电话行）。字段面的真实边界在**服务端**，不在客户端。

---

## 4. 搜索条件面 = 服务端可检索字段（可作验证 oracle）

`res/layout/activity_mita_new2.xml`（**452 与 454 完全一致**，即官方设计非改动引入）：

| 条件 | 控件 |
|---|---|
| 姓名 | `activity_mita_edit_xm`（hint "姓名"）、`activity_mita_edit_xm1`（"输入姓名"） |
| 身份 | `activity_mita_layout_stu` 学生 / `activity_mita_layout_tea` 教师 |
| 性别 | `activity_mita_layout_buxian|bx|nv|nan`（不限/女/男） |
| 专业 | `activity_mita_edit_zy`（hint "专业"） |
| **籍贯** | `activity_mita_edit_jg`（hint "籍贯"） |
| 入学年级 | `activity_mita_layout_rxnj` + picker |

⇒ 即使某字段不显示，也能**用搜索命中与否反推**目标属性（姓名/性别/专业/籍贯/入学年级/身份六维），命中过多时服务端返回 `flag="2"`（"满足条件的人数太多"）。

搜索结果 `data[]` → `BbsBean`（native 构造）；454 里两个 BbsBean 列表 adapter 是 `u8/v`（`TdkbListItemAdapter`）与 `u8/f`（`ClassmateGridItemNewAdapter`），它们只渲染 **姓名 `i()` + 班级 `n()`**（`u8/v.java:451-455`）、头像 `h()`、性别 `q()`，并在点击时携带 `b()`=JID(`xxdm_学号/工号`)、`j()`/`l()`=身份类型。⚠️ **哪个 adapter 真正渲染觅Ta 搜索结果列表由 native 决定**（`MitaNewListActivity` 的 onCreate 是 native），此处只报 adapter 能力，不断言绑定关系。

---

## 5. VMP 边界（为什么有些字段查不到静态证据）

- 454 明文 dex 里 **13,551 个 native 方法 / 822 个文件**；`com/nesun/KDVmp` → `System.loadLibrary("kdvmp")`，`MitaNewActivity` 末尾 `KDVmp.registerJni(1, 3562, 1123152)`。
- `libkdvmp.so`（arm64, 8.85 MB）字符串**全加密**：`ssbj/csrq/sfzh/xm/学号/院系/性别…` 全部 0 命中（`strings` 与字节 grep 双验）。
- 受影响且与本案直接相关的 native 方法：
  - `ClassmateInfoActivity.y2(String) → ArrayList<HashMap<String,Object>>`（**他人信息页行构造器**；452/435/454 三版**均为 native**）
  - `ClassmateInfoActivity.N2(String) → List<BbsBean>`（`:808`）、`TdkbActivity.e2(String) → List<BbsBean>`（`:175`，配 `KDVmp.registerJni(1, 2201, 1145024)`）、`ClassmatesGridActivity.Z1() → List<BbsBean>`（`:147`）→ **列表 JSON→Bean 的映射也在 JNI**
  - `MitaNew2Activity.k2/l2/o2/p2`（觅Ta 搜索请求构造）
  - `TeaInfoActivity`、`MitaNewActivity.C2/D2/E2`、`ClassmateInfoActivity.E2/M2/O2/S1/T1`
- ⇒ **静态读不出**：① 他人信息页动态行的完整标签/键集合；② 觅Ta 搜索请求的 `action/step` 名。
- ⇒ **可读**：行 schema（§3）、搜索结果结构与列表字段（§3/§4）、所有非 native 端点的取键（§2）。
- ⚠️ **端点归属的证据等级**：`ClassmateInfoActivity`/`TeaInfoActivity` **自身**发出的那条主信息请求（回调 `l`/`m` 取 `mita`/`xm`/`xb`/`uuid`，`:526-635`/`:637-746`，失败分支弹"未开启【觅Ta】服务"）构造在 native，**454 Java 里看不到它的 URL**。「它就是 `baseInfoServlet?step=other`」目前靠两点间接支撑：(a) `t9/t0` 闸门通过后 Java 直调 `e2/a.l/m/n`（= `step=other`）拉起这两个页面；(b) 先前会话的 435/452 静态比对（`改版深度探索文档.md`、`数据面与监控组件深挖.md`）。引用时按"高置信但非 454 直证"对待。
- ⚠️ 本工作区现有抓包 `analysis/captures/flows_20260910_mitm.bin` 里**没有任何觅Ta 流量**（`getMITA`/`judgeBlackList`/`baseInfoServlet` 0 命中）→ native 部分目前也无法动态补证；要拿准只能 hook `da.b` 的请求构造/回调或重抓。

---

## 6. 与 435/452 的一致性 & 待实测项

一致性（已用 452 官方 payload 明文树 `analysis/original/payload_plain_jadx/sources/` 复核）：`classmate_info.xml` / `activity_mita_new2.xml` 字段在两版相同；`JsxqBean` 16 字段相同（452 `bean/HYDX/bean/JsxqBean.java` 同为 `private String × 16`）；`step=other` 三处调用点同址（452 `e2/a.java:589/605/621` ↔ 454 `e2/a.java:590/606/622`）；信息页取键同为 `mita/xm/xb/uuid/flag`。改版（435）的差异只在**门禁被掏空**，不改字段面。

需动态（真机 + 抓包，手册 §4）才能定性的 4 条：
1. `step=other` 对**未开觅Ta**的对方实际下发宽行还是窄行（= 漏洞定性的核心）。
2. 他人信息页动态行实际包含哪些标签（是否含 学号/院系/电话 行）。
3. `GetTeaResume` 是否真下发 `sfzh`/`dh`/`jg`/`nl`/`gw`/`zc`（解析面有、展示面不用 → 若下发即"可读出但不显示"）。
4. 觅Ta 搜索的实际 `action/step` 与参数名（native，只能抓包看）。

**查他人链路的请求组合数**：Java 可见 **7 组**（① `judgeBlackList`；② `getSettings&step=getMITA`；③ `getSettings&step=getMITAWithOther`；④ `baseInfoServlet&step=other`；⑤ `oriHd_ggym&step=GetTeaResume`；⑥ `oriHd_kc&step=getCourse_Detail_hd`；⑦ `kingo_course&step=course_shoucang_delete`），另有 **2 处（信息页主请求、加黑名单）构造在 native 不可见** → 全链路 ≤ 9 组。

合规边界：回放只填自己的 uuid，不枚举他人；抓到他人数据只记键名不存值。

---

## 7. 复现口径

```bash
# 454 明文 dex（脱壳产物）→ jadx 树：analysis/latest/plain_jadx/sources/
# 全树 (action, step) 清单
python3 - <<'PY'
import re,glob,collections
s=collections.Counter(); a=collections.Counter()
for f in glob.glob('analysis/latest/plain_jadx/sources/**/*.java',recursive=True):
    t=open(f,encoding='utf-8',errors='ignore').read()
    for m in re.finditer(r'put\("step",\s*"([^"]+)"\)',t): s[m.group(1)]+=1
    for m in re.finditer(r'put\("action",\s*"([^"]+)"\)',t): a[m.group(1)]+=1
print(sorted(s.items(),key=lambda x:-x[1])); print(sorted(a.items(),key=lambda x:-x[1]))
PY
# 觅Ta 相关行定位
grep -rn 'getMITA\|judgeBlackList\|GetTeaResume\|getCourse_Detail_hd\|step", "other"' analysis/latest/plain_jadx/sources | head -40
```

---

## 8. 首次真机样本（2026-10-04，教师目标，用户实测）

查询者：学生（自己开关已开）；目标：教师「陈磊」，`uuid=10475_10250137`、① 里 `jsdm=t1001122`、`bm=[1025]软件学院`。

**① `baseInfoServlet?step=other`（GET，参数 userId/usertype=自己 STU、otheruuid=目标）= 18 键宽行**：

```json
{"msg":"人力系统未对接","jsdm":"t1001122","xznj":"","xb":"男","bm":"[1025]软件学院","rxnf":"",
 "userid":"10250137","uuid":"10475_10250137","xxmc":"河南大学","gangwei":"","zhichen":"",
 "xxdm":"10475","xueli":"","xm":"陈磊","xuewei":"","mita":"0","state":"0","jg":""}
```

要点：
1. **宽行实锤**：顶层 18 键 ≫ 官方客户端消费的 7 个路由字段（xm/xb/xxdm/xh|jsdm|userid/ssbj/state）。⇒ 「解析面过宽 + 服务端裁剪不足」成立，报告可写"水平越权面"（数据面口径见 §0/§2）。
2. **目标开关是关着的**（`mita=0`、`state=0`），服务端**照样下发了这条记录**（姓名/性别/学校/部门/账号），只在 `msg` 里告知 `人力系统未对接`；② 才回隐私门文案 → 说明 `step=other` 的下发**不以对方开关为前置**（至少教师样本如此）。样本量=1，学生目标待补。
3. 教师专属键 `bm`(部门/学院)、`gangwei`(岗位)、`zhichen`(职称)、`xueli`(学历)、`xuewei`(学位) 全部**键在值空** —— 与 `msg=人力系统未对接` 一致：该校没接人事系统。
4. `jg`(籍贯) 也是**键在值空**：之前静态结论「籍贯不下发」需要改成「**下发但在该校为空**」。

**④ `oriHd_ggym&step=GetTeaResume`**：`jsid=10250137`（JID 后缀=平台号）→ `{"resultSet":[]}`。**未定论**：官方调用点是 native，看不到 `jsid` 到底取 `jsdm`(t1001122) 还是平台号；探测弹窗已改成**两个候选都发**（并修掉误标的"学生工号"文案）。若两个都空，则空结果归因于 `人力系统未对接`（服务端），与 `jsid` 无关。

**② `getSettings&step=getMITAWithOther`**：`{"state":"0","msg":"由于对方设置【觅TA】隐私开关，您无法查看其信息"}` —— 与 ① 的 `state=0` 自洽；弹窗现在按官方两处不一致的写法（e2/a 用自己 usertype、u8/v 用对方 usertype）**各发一遍对照**。

**③ `judgeBlackList`**：`{"msg":"互相不是黑名单","flag":"0"}` —— 正常放行。

> 参数口径澄清（用户问过）：三条请求里的 `usertype=STU` 是**查询者自己**的身份，不是把老师当学生查（官方 `e2/a.java:584-629` 的 l/m/n 就是这么发的：`usertype=j0.usertype`=自己；目标由 `otheruuid` 指定）。目标类型只出现在 ③ 的 `tousertype` 与 ② 的一种写法里。
