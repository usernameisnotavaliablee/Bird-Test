# 课表批量查询 + 课余时间可视化

给一份名单，逐个查课表，保留服务器原始响应，生成 HTML：
- 个人周课表（节次 × 周一~周日）
- 全员“共同空闲”热力图（绿色=全员空闲，黄色=部分，红色=全员有课）
- 名单总览（课程数、忙/闲节次、空闲率）
- `raw/<学号>.json` 原样响应 + `manifest.json` 请求参数/哈希/错误

只查名单里的人。**不要用它枚举、猜学号或查无关的人。** live 模式必须显式加
`--authorized`，默认请求间隔 3 秒（约 20 次/分钟），别把学校接口打崩。

## 快速开始

```bash
cd timetable

# 1) 自检：编码向量、解析、空闲计算、HTML
python3 query.py --selftest

# 2) 合成数据演示（不联网）
python3 query.py --demo
# 打开 runs/demo-*/report.html

# 3) 真实查询（示例：河南大学 / 喜鹊儿）
#    名单格式见 roster.example.csv
python3 query.py --live --authorized \
    --roster roster.example.csv \
    --key-from-login ../analysis/captures/login_resp_plain_0910.json \
    --semester 20260 --week "" \
    --run-id my-run
```

`--key-from-login` 只读取登录响应 JSON 里的 `info[os=="jw"].encrpt` 和同项的
`url`，不使用 token、账号或密码。也可以直接传 key：

```bash
python3 query.py --live --authorized --roster roster.csv \
    --base-url https://xk.henu.edu.cn --key '<jw encrpt>' --semester 20260
```

没有历史登录响应时，从自己的客户端抓一次登录响应，或从 `analysis/captures/`
里的本地样本取 `info` 中的 jw 项。key 不要提交进 git。

## 实测记录（2026-10-27，河南大学 / 喜鹊儿）

- 本人测试账号，空 UA，`week` 空 → 第 09 周（2026-10-26~11-01）10 门课、忙 22 节、空闲 83 节；`--week 10` → 第 10 周（11-02~11-08）同 10 门。
- 批量冒烟 3 行：本人 + 两个明显无效空号；3/3 HTTP 200，空号返回空课表（报告标“空课表”）。
- 单份响应约 4.6KB；`raw/` 原样保存，未把真实课表提交进 git。
- 这些结果只用于验证工具链路；没有查询名单以外的真实学生。

## 名单格式

CSV，UTF-8，表头至少要有 `student_id`（也识别 `学号`/`id`/`userid`）：

```csv
name,student_id,class
张三,2026000001,示例班
李四,2026000002,示例班
```

- `name` 可空，空时用学号代替。
- 学号重复会直接报错。
- 名单里的每个人都会且只会请求一次；不做分页/猜测/枚举。

## 输出目录

```
runs/<run_id>/
  report.html          # 可视化
  manifest.json        # 时间、学期、请求明文、HTTP 状态、原始文件 SHA-256
  raw/<学号>.json      # 服务器原始响应（原样文本）
```

- `report.html` 里的“原始 JSON”链接指向同目录 `raw/`。
- `--from-raw runs/<run_id>` 可离线重渲染报告，不重新请求。
- `--dry-run` 只打印请求参数，不发送；用于核对名单。
- `--limit N` 只查前 N 人（调试）。
- `--out path` 自定义报告路径；默认 `<run_dir>/report.html`。

## 空闲时间怎么算

接口一次返回一周（`zc` 周次、`qssj`~`jssj` 日期、`week1`~`week7` 对应周一到周日）。
每门课用 `jcdm`（如 `03,04`）或 `jcxx`（如 `3-5`）标占用节次：

- 忙节 = 该周所有课程占用的节次并集。
- 空闲 = `1..maxjc` 中未占用的节次；连续空闲合并为“第 a-b 节”。
- 全员共同空闲 = 每个学生都空闲的节次，按天合并。
- 空闲率 = 空闲节次 / (7 × `maxjc`)。

**注意**：只按“节次”算，不猜上下课钟点；不同学校的节次时间不同，
需要精确到几点就把 `maxjc`/节次时间表接入 HTML 或另建配置。
周末没课会天然显示为空闲；`week1` 是否周一取决于服务端约定（HENU 实测为周一）。

## 协议（实现细节）

`POST {jw_url}/wap/mycourseschedule.action`，表单：

```
param=<base36 编码>&param2=<变形 MD5>
```

明文（字段顺序固定）：

```
jsdm=&week=<周>&xnxq=<学期>&usertype=STU&userid=<学号>&bjdm=
```

- `param` = `ba.b.k()` 的移植：明文字符 ASCII + key 循环 + 偏移，三位一组、九位一组转 base36。
- `param2` = `ba.b.f()` 的移植：md5 → 去掉第 3/11/18/26 个字符 → 再 md5。
- key = 登录响应 `info[]` 中 `os=="jw"` 的 `encrpt`（各校/各部署不同）。
- 响应是明文 JSON；`jcdm` 是节次，`week1..week7` 是周一到周日。

`--selftest` 里固定了两个由 Java 参考实现生成的编码向量，改编码逻辑会立刻失败。

## 请求头

`HEADER_PLACEHOLDERS` 里预留了 `User-Agent`、`Referer`、`Origin`、`Cookie`，
默认空值不发送。HENU 实测空 UA 也能通；其他学校若被 WAF/网关拦，补：

```bash
python3 query.py --live --authorized ... \
  --user-agent 'Mozilla/5.0 ...' \
  --header 'Referer:https://xk.example.edu.cn/' \
  --header 'Cookie:JSESSIONID=...'
```

不要在代码里写死 token/Cookie；用命令行或本地未跟踪文件。

## 限制 / 已知问题

- 只支持 `mycourseschedule.action` 这一种 jw 厂商接口；其他学校若接口名/字段不同，
  改 `build_plain()` 和 `normalize_schedule()`。
- 未实现登录：本工具假设 jw 接口不需要登录态（HENU 实测如此），只需要名单和 key。
  若目标学校要求会话，先用自己的客户端拿到 Cookie，再用 `--header` 传入。
- 空课表（0 门课）无法区分“本周真没课”和“学号不存在”，报告会标“空课表”提醒。
- 响应字段缺失/改版会进“失败明细”，原始响应仍保存在 `raw/`。
- 不做并发；串行 + 固定间隔，避免触发风控。

## 安全与合规

- 仅查询本人或已获明确授权的名单；`--authorized` 是人工确认，不是技术授权。
- 原始响应可能含姓名、课程、教室等个人信息：`runs/`、`raw/` 已在 `.gitignore`，
  不要提交、不要公开转发。
- 发现接口可越权查他人课表，应向学校/厂商负责任披露，不要在公开报告里贴真实名单。
