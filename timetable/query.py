#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
喜鹊儿 / 青果 课表批量查询 + 空闲时间可视化
================================================

输入：CSV 名单（name,student_id[,class]）
过程：逐个请求学校 jw 厂商接口 /wap/mycourseschedule.action，
      响应原样落盘，再解析成“周课表 → 忙闲节次”。
输出：一次运行一个目录：
      runs/<run_id>/report.html   可视化（单人格子 + 全员共同空闲热力图）
      runs/<run_id>/raw/<id>.json 原始响应
      runs/<run_id>/manifest.json 运行元数据 / 请求参数 / 错误

协议要点（2026-10 实测）：
  POST {jw_url}/wap/mycourseschedule.action
  form: param=<base36 编码的明文>&param2=<md5 变形>
  明文: jsdm=&week=<周>&xnxq=<学期>&usertype=STU&userid=<学号>&bjdm=
  key : 登录响应 info[] 中 os=="jw" 的 encrpt 字段（各校不同）
  UA 等头默认留空；HENU 实测空 UA 也能通。需要时用 --user-agent/--header 补。

合规：只查询你有权查询的名单（本人 / 已获授权的班级成员）。
本工具不猜 ID、不枚举、不做超出名单的任何请求。live 模式必须加 --authorized。

仅标准库。示例：
  python3 query.py --selftest
  python3 query.py --demo
  python3 query.py --live --authorized --roster roster.csv \
      --key-from-login analysis/captures/login_resp_plain_0910.json --semester 20260
  python3 query.py --from-raw runs/20261027-190000
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

VERSION = "1.0"
DEFAULT_BASE = "https://xk.henu.edu.cn"
DEFAULT_SEMESTER = "20260"
DEFAULT_UA = ""  # 占位：需要时填
DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 占位请求头：按需填。空值不会发送。
HEADER_PLACEHOLDERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "",
    "Origin": "",
    "Cookie": "",
}


# ---------------------------------------------------------------------------
# 协议编码：base36 流密码 + param2 变形 MD5（从 ba.b.k / ba.b.f 移植）
# ---------------------------------------------------------------------------

def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _param2(text: str) -> str:
    """ba.b.f(): md5 → 去掉第 3/11/18/26 个字符（1-based）→ 再 md5。"""
    first = _md5_hex(text)
    keep = [ch for i, ch in enumerate(first) if i not in (2, 9, 16, 24)]
    return _md5_hex("".join(keep))


_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(value: int) -> str:
    if value < 0:
        return "-" + _b36(-value)
    out = ""
    while True:
        out = _B36[value % 36] + out
        value //= 36
        if value <= 0:
            return out


def encode_param(plain: str, key: str) -> str:
    """ba.b.k(): 明文按 key 循环逐字符加偏移，三位一组，再九位一组转 base36。"""
    if not plain or not key:
        raise ValueError("encode_param: 明文和 key 都不能为空")
    key_len = len(key)
    n = len(plain)
    # ba.b.k: iCeil2 = (ceil(n*3*6/9/6)*6) % key_len == (ceil(n/3)*6) % key_len
    shift = (((n + 2) // 3) * 6) % key_len
    digits: list[str] = []
    for i in range(0, n, key_len):
        for j in range(key_len):
            idx = i + j
            if idx >= n:
                break
            val = ord(plain[idx]) + ord(key[j]) + shift
            digits.append(str(val).rjust(3, "0")[-3:])
    joined = "".join(digits)
    out: list[str] = []
    for i in range(0, len(joined), 9):
        out.append(_b36(int(joined[i:i + 9])).rjust(6, "0")[-6:])
    return "".join(out)


# ---------------------------------------------------------------------------
# 名单 / 课表解析
# ---------------------------------------------------------------------------

def read_roster(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"名单不存在: {path}")
    aliases = {
        "name": {"name", "姓名", "名字"},
        "student_id": {"student_id", "studentid", "id", "学号", "userid", "user_id"},
        "class": {"class", "班级", "bj"},
    }
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise SystemExit(f"名单为空: {path}")
        mapping: dict[str, str] = {}
        for field in reader.fieldnames:
            key = (field or "").strip().lower()
            for canon, names in aliases.items():
                if key in names:
                    mapping[canon] = field
        if "student_id" not in mapping:
            raise SystemExit(f"名单缺 student_id/学号 列: {path}")
        for raw in reader:
            name = (raw.get(mapping.get("name", "")) or "").strip()
            sid = (raw.get(mapping["student_id"]) or "").strip()
            cls = (raw.get(mapping.get("class", "")) or "").strip()
            if not sid:
                continue
            rows.append({"name": name or sid, "student_id": sid, "class": cls})
    if not rows:
        raise SystemExit(f"名单没有有效行: {path}")
    seen: set[str] = set()
    for row in rows:
        if row["student_id"] in seen:
            raise SystemExit(f"名单学号重复: {row['student_id']}")
        seen.add(row["student_id"])
    return rows


def parse_periods(value: Any) -> list[int]:
    """'01,02' / '1-2' / '3-5' → [1,2] / [1,2] / [3,4,5]。"""
    if not value:
        return []
    text = str(value).replace("，", ",").strip()
    periods: set[int] = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            a, _, b = token.partition("-")
            if a.strip().isdigit() and b.strip().isdigit():
                periods.update(range(int(a), int(b) + 1))
        elif token.isdigit():
            periods.add(int(token))
    return sorted(periods)


def normalize_schedule(resp: dict[str, Any]) -> dict[str, Any]:
    maxjc = int(resp.get("maxjc") or 15)
    days: dict[int, list[dict[str, Any]]] = {}
    for day in range(1, 8):
        items: list[dict[str, Any]] = []
        for course in (resp.get(f"week{day}") or []):
            periods = parse_periods(course.get("jcdm")) or parse_periods(course.get("jcxx"))
            if not periods:
                continue
            items.append({
                "name": str(course.get("kcmc") or "").strip(),
                "teacher": str(course.get("rkjs") or "").strip(),
                "room": str(course.get("skdd") or "").strip(),
                "periods": periods,
            })
        days[day] = items
    return {
        "semester": f'{resp.get("xn", "")}-{resp.get("xq", "")}'.strip("-"),
        "week": str(resp.get("zc") or ""),
        "start_date": str(resp.get("qssj") or ""),
        "end_date": str(resp.get("jssj") or ""),
        "maxjc": maxjc,
        "days": days,
    }


def busy_by_day(schedule: dict[str, Any]) -> dict[int, set[int]]:
    return {
        day: {p for course in courses for p in course["periods"]}
        for day, courses in schedule["days"].items()
    }


def free_ranges(busy: set[int], maxjc: int) -> list[tuple[int, int]]:
    ranges: list[list[int]] = []
    for p in range(1, maxjc + 1):
        if p in busy:
            continue
        if ranges and p == ranges[-1][1] + 1:
            ranges[-1][1] = p
        else:
            ranges.append([p, p])
    return [(a, b) for a, b in ranges]


def free_periods(busy: set[int], maxjc: int) -> list[int]:
    return [p for p in range(1, maxjc + 1) if p not in busy]


def common_free_slots(students: list[dict[str, Any]], maxjc: int) -> list[tuple[int, int, int]]:
    """返回 [周一..周日, 起, 止]，要求全体学生都空闲。"""
    if not students:
        return []
    slots: list[tuple[int, int, int]] = []
    for day in range(1, 8):
        free = [
            p for p in range(1, maxjc + 1)
            if all(p not in s["busy"][day] for s in students)
        ]
        for a, b in _runs(free):
            slots.append((day, a, b))
    return slots


def _runs(values: list[int]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for value in values:
        if out and value == out[-1][1] + 1:
            out[-1][1] = value
        else:
            out.append([value, value])
    return [(a, b) for a, b in out]


def _period_label(a: int, b: int) -> str:
    return f"第{a}节" if a == b else f"第{a}-{b}节"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _headers(user_agent: str, extra: list[str]) -> dict[str, str]:
    headers = {k: v for k, v in HEADER_PLACEHOLDERS.items() if v}
    if user_agent:
        headers["User-Agent"] = user_agent
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    for item in extra:
        if ":" not in item:
            raise SystemExit(f"--header 需要 K:V 格式: {item}")
        key, value = item.split(":", 1)
        key = key.strip()
        if key:
            headers[key] = value.strip()
    return headers


def build_plain(student_id: str, semester: str, week: str) -> str:
    return f"jsdm=&week={week}&xnxq={semester}&usertype=STU&userid={student_id}&bjdm="


def fetch_schedule(
    base_url: str,
    key: str,
    student: dict[str, str],
    semester: str,
    week: str,
    headers: dict[str, str],
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    plain = build_plain(student["student_id"], semester, week)
    param = encode_param(plain, key)
    param2 = _param2(plain)
    body = parse.urlencode({"param": param, "param2": param2}).encode("utf-8")
    url = base_url.rstrip("/") + "/wap/mycourseschedule.action"
    result: dict[str, Any] = {
        "request_plain": plain,
        "url": url,
        "http_status": None,
        "raw_text": "",
        "error": None,
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = request.Request(url, data=body, headers=headers, method="POST")
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                result["http_status"] = getattr(resp, "status", 200)
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", "replace")
            result["raw_text"] = text
            return result
        except error.HTTPError as exc:
            result["http_status"] = exc.code
            try:
                result["raw_text"] = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            last_error = exc
            if 400 <= exc.code < 500:
                break
        except (error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    result["error"] = f"{type(last_error).__name__}: {last_error}"
    return result


# ---------------------------------------------------------------------------
# 演示数据
# ---------------------------------------------------------------------------

def _course(name: str, teacher: str, room: str, jcdm: str) -> dict[str, str]:
    return {"kcmc": name, "rkjs": teacher, "skdd": room, "jcdm": jcdm, "jcxx": jcdm}


def demo_responses() -> list[tuple[dict[str, str], dict[str, Any]]]:
    base = {"xn": "2026", "xq": "0", "zc": "09", "maxzc": "18",
            "qssj": "2026-10-26", "jssj": "2026-11-01", "maxjc": "15"}
    a = dict(base, **{
        "week1": [_course("高等数学", "沈老师", "综合楼201", "01,02")],
        "week3": [_course("大学英语", "秦老师", "外语楼305", "03,04,05")],
        "week5": [_course("程序设计", "陈老师", "计算机楼101", "07,08")],
    })
    b = dict(base, **{
        "week1": [_course("线性代数", "韩老师", "综合楼102", "03,04")],
        "week2": [_course("大学物理", "吕老师", "物理楼401", "01,02")],
        "week4": [_course("数据结构", "陈老师", "计算机楼101", "09,10")],
    })
    c = dict(base, **{
        "week2": [_course("概率论", "谢老师", "综合楼203", "03,04,05")],
        "week3": [_course("离散数学", "魏老师", "计算机楼202", "01,02")],
        "week5": [_course("体育", "樊老师", "篮球场", "03,04")],
    })
    return [
        ({"name": "张三", "student_id": "2026000001", "class": "示例班"}, a),
        ({"name": "李四", "student_id": "2026000002", "class": "示例班"}, b),
        ({"name": "王五", "student_id": "2026000003", "class": "示例班"}, c),
    ]


# ---------------------------------------------------------------------------
# 结果组装 / 原始数据落盘
# ---------------------------------------------------------------------------

def _safe_name(student_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in student_id)


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_result(student: dict[str, str], fetched: dict[str, Any], raw_rel: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": student["name"],
        "student_id": student["student_id"],
        "class": student.get("class", ""),
        "status": "error",
        "raw_file": raw_rel,
        "error": fetched.get("error"),
        "http_status": fetched.get("http_status"),
        "schedule": None,
        "busy": None,
        "free": None,
        "empty": False,
    }
    if fetched.get("error"):
        return result
    try:
        resp = json.loads(fetched["raw_text"])
    except json.JSONDecodeError as exc:
        result["error"] = f"JSONDecodeError: {exc}"
        return result
    if not isinstance(resp, dict) or "maxjc" not in resp:
        result["error"] = "响应不是课表 JSON（缺 maxjc）"
        return result
    schedule = normalize_schedule(resp)
    busy = busy_by_day(schedule)
    result.update({
        "status": "ok",
        "schedule": schedule,
        "busy": busy,
        "free": {day: free_ranges(busy[day], schedule["maxjc"]) for day in range(1, 8)},
        "course_count": sum(len(v) for v in schedule["days"].values()),
        "busy_count": sum(len(v) for v in busy.values()),
        "free_count": sum(len(free_periods(busy[day], schedule["maxjc"])) for day in range(1, 8)),
        "empty": sum(len(v) for v in schedule["days"].values()) == 0,
    })
    return result


def load_results(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"没有 manifest.json: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for item in manifest.get("students", []):
        raw_file = item.get("raw_file") or ""
        raw_path = run_dir / raw_file
        fetched = {"error": item.get("error"), "http_status": item.get("http_status"), "raw_text": ""}
        if raw_path.exists() and not item.get("error"):
            fetched["raw_text"] = raw_path.read_text(encoding="utf-8")
        student = {"name": item.get("name", ""), "student_id": item.get("student_id", ""),
                   "class": item.get("class", "")}
        results.append(make_result(student, fetched, raw_file))
    return manifest, results


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CSS = """
:root{--ink:#172033;--muted:#667085;--line:#e4e7ec;--bg:#f6f8fb;--card:#fff;
--blue:#2563eb;--blue-soft:#eff6ff;--green:#15803d;--green-soft:#ecfdf3;
--amber:#b45309;--amber-soft:#fffbeb;--red:#b42318;--red-soft:#fef3f2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 56px}
header h1{margin:0 0 6px;font-size:26px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 18px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 26px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;min-width:130px}
.stat b{display:block;font-size:20px;line-height:1.2}.stat span{color:var(--muted);font-size:12px}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin:0 0 20px}
h2{font-size:18px;margin:0 0 4px}h3{font-size:15px;margin:18px 0 8px}
.hint{color:var(--muted);font-size:12px;margin:0 0 12px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
.chip{background:var(--green-soft);color:var(--green);border:1px solid #bbf7d0;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:600}
.chip.none{background:var(--red-soft);color:var(--red);border-color:#fecaca}
.scroll{overflow:auto;border:1px solid var(--line);border-radius:12px}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:760px}
th,td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}
th:last-child,td:last-child{border-right:0}tr:last-child td,tr:last-child th{border-bottom:0}
thead th{background:#f9fafb;font-size:12px;color:var(--muted);font-weight:600;position:sticky;top:0;z-index:2}
tbody th{background:#fcfcfd;font-size:12px;color:var(--muted);font-weight:500;white-space:nowrap;text-align:left}
td.free{background:#fbfdff}td.busy{background:var(--blue-soft)}
.course{font-size:12px;font-weight:600;line-height:1.35}.meta{color:var(--muted);font-size:11px;line-height:1.3}
td.all{background:var(--green-soft);color:var(--green);font-weight:700}
td.some{background:var(--amber-soft);color:var(--amber);font-weight:600}
td.none{background:var(--red-soft);color:var(--red)}
.heat{text-align:center;font-variant-numeric:tabular-nums;min-width:74px}
table.people{min-width:860px}table.people td{font-size:13px}
.ok{color:var(--green);font-weight:600}.err{color:var(--red);font-weight:600}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.person{border-top:1px solid var(--line);padding-top:16px;margin-top:16px}
.person:first-of-type{border-top:0;padding-top:0;margin-top:0}
.person h3{margin:0 0 2px;font-size:16px}.person .who{color:var(--muted);font-size:12px;margin:0 0 10px}
.free-list{color:var(--green);font-size:12px;margin:8px 0 10px}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:8px}
@media (max-width:720px){.wrap{padding:16px 10px 40px}section{padding:12px;border-radius:12px}}
"""


def render_person_grid(student: dict[str, Any], maxjc: int) -> str:
    schedule = student["schedule"]
    parts = ['<div class="scroll"><table><thead><tr><th></th>']
    parts.extend(f"<th>{name}</th>" for name in DAY_NAMES)
    parts.append("</tr></thead><tbody>")
    for p in range(1, maxjc + 1):
        parts.append(f"<tr><th>第{p}节</th>")
        for day in range(1, 8):
            courses = [c for c in schedule["days"][day] if p in c["periods"]]
            if not courses:
                parts.append('<td class="free"></td>')
                continue
            bits = []
            for c in courses:
                title = " / ".join(x for x in (c["name"], c["teacher"], c["room"]) if x)
                bits.append(
                    f'<div class="course" title="{html.escape(title)}">{html.escape(c["name"])}</div>'
                    + (f'<div class="meta">{html.escape(c["room"])}</div>' if c["room"] else "")
                )
            parts.append(f'<td class="busy">{"".join(bits)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_person(student: dict[str, Any], maxjc: int, report_dir: Path, raw_root: Path) -> str:
    free_text = "；".join(
        f"{DAY_NAMES[day - 1]} {_period_label(a, b)}"
        for day in range(1, 8) for a, b in student["free"][day]
    )
    raw = ""
    if student["raw_file"]:
        rel = os.path.relpath(raw_root / student["raw_file"], report_dir)
        raw = f' · <a href="{html.escape(rel)}">原始 JSON</a>'
    return (
        f'<div class="person"><h3>{html.escape(student["name"])}</h3>'
        f'<p class="who">学号 {html.escape(student["student_id"])}'
        f'{" · " + html.escape(student["class"]) if student["class"] else ""}'
        f' · 课程 {student["course_count"]} 门 · 忙 {student["busy_count"]} 节 · 空闲 {student["free_count"]} 节{raw}</p>'
        + ('<p class="hint">空课表：请确认学号是否存在；若学号正确，则本周确实没有课。</p>' if student.get("empty") else "")
        + f'<div class="free-list">空闲：{html.escape(free_text) if free_text else "无"}</div>'
        f'{render_person_grid(student, maxjc)}</div>'
    )


def render_heatmap(students: list[dict[str, Any]], maxjc: int) -> str:
    n = len(students)
    parts = ['<div class="scroll"><table><thead><tr><th></th>']
    parts.extend(f"<th>{name}</th>" for name in DAY_NAMES)
    parts.append("</tr></thead><tbody>")
    for p in range(1, maxjc + 1):
        parts.append(f"<tr><th>第{p}节</th>")
        for day in range(1, 8):
            names = [s["name"] for s in students if p not in s["busy"][day]]
            count = len(names)
            cls = "all" if count == n else ("none" if count == 0 else "some")
            title = f"空闲 {count}/{n}：" + ("、".join(names) if names else "无")
            parts.append(f'<td class="heat {cls}" title="{html.escape(title)}">{count}/{n}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_summary(students: list[dict[str, Any]], report_dir: Path, maxjc: int, raw_root: Path) -> str:
    parts = ['<div class="scroll"><table class="people"><thead><tr>'
             '<th>姓名</th><th>学号</th><th>班级</th><th>状态</th><th>课程</th>'
             '<th>忙节</th><th>空闲节</th><th>空闲率</th><th>原始数据</th></tr></thead><tbody>']
    total = maxjc * 7
    for s in students:
        if s["status"] == "ok":
            rate = f'{s["free_count"] / total:.0%}'
            status = '<span class="ok">成功（空课表）</span>' if s.get("empty") else '<span class="ok">成功</span>'
            counts = (s["course_count"], s["busy_count"], s["free_count"])
        else:
            rate = "-"
            status = f'<span class="err" title="{html.escape(s["error"] or "")}">失败</span>'
            counts = ("-", "-", "-")
        raw = "-"
        if s["raw_file"]:
            rel = os.path.relpath(raw_root / s["raw_file"], report_dir)
            raw = f'<a href="{html.escape(rel)}">JSON</a>'
        parts.append(
            f'<tr><td>{html.escape(s["name"])}</td><td>{html.escape(s["student_id"])}</td>'
            f'<td>{html.escape(s["class"])}</td><td>{status}</td>'
            f'<td>{counts[0]}</td><td>{counts[1]}</td><td>{counts[2]}</td><td>{rate}</td><td>{raw}</td></tr>'
        )
    parts.append("</tbody></table></div>")
    return "".join(parts)


def build_html(students: list[dict[str, Any]], meta: dict[str, Any], report_dir: Path, raw_root: Path) -> str:
    ok = [s for s in students if s["status"] == "ok"]
    maxjc = max((s["schedule"]["maxjc"] for s in ok), default=15)
    slots = common_free_slots(ok, maxjc)
    if slots:
        chips = "".join(
            f'<span class="chip">{DAY_NAMES[day - 1]} {_period_label(a, b)}</span>'
            for day, a, b in slots
        )
    else:
        chips = '<span class="chip none">没有全员共同空闲时段</span>'
    week = meta.get("week") or (ok[0]["schedule"]["week"] if ok else "")
    dates = ""
    if ok:
        start = ok[0]["schedule"].get("start_date", "")
        end = ok[0]["schedule"].get("end_date", "")
        if start or end:
            dates = f"{start} ~ {end}"
    header_meta = " · ".join(x for x in [
        f"学期 {meta.get('semester', '')}",
        f"第 {week} 周" if week else "",
        dates,
        f"{len(ok)}/{len(students)} 人成功",
    ] if x)
    sections = [
        f'<header><h1>课表与课余时间</h1><p class="sub">{html.escape(header_meta)}</p></header>',
        '<div class="stats">'
        f'<div class="stat"><b>{len(students)}</b><span>名单人数</span></div>'
        f'<div class="stat"><b>{len(ok)}</b><span>查询成功</span></div>'
        f'<div class="stat"><b>{len(students) - len(ok)}</b><span>失败</span></div>'
        f'<div class="stat"><b>{sum(1 for s in ok if s.get("empty"))}</b><span>空课表</span></div>'
        f'<div class="stat"><b>{len(slots)}</b><span>全员空闲段</span></div>'
        '</div>',
    ]
    if ok:
        sections.append(
            '<section><h2>全员共同空闲</h2>'
            '<p class="hint">按节次计算；同一门课跨多节会连续占用。绿色=全员空闲，黄色=部分空闲，红色=全员有课。</p>'
            f'<div class="chips">{chips}</div>'
            f'<h3>空闲热力图</h3>{render_heatmap(ok, maxjc)}</section>'
        )
    sections.append(
        '<section><h2>名单总览</h2>'
        '<p class="hint">空闲率 = 空闲节次 / (周天数 × 每日最大节次)。原始 JSON 与本次报告同目录保存。</p>'
        f'{render_summary(students, report_dir, maxjc, raw_root)}</section>'
    )
    if ok:
        sections.append('<section><h2>个人课表</h2><p class="hint">蓝色=有课，空白=空闲。</p>')
        for s in ok:
            sections.append(render_person(s, maxjc, report_dir, raw_root))
        sections.append('</section>')
    if len(ok) < len(students):
        rows = "".join(
            f'<tr><td>{html.escape(s["name"])}</td><td>{html.escape(s["student_id"])}</td>'
            f'<td>{html.escape(s["error"] or "未知错误")}</td></tr>'
            for s in students if s["status"] != "ok"
        )
        sections.append(
            '<section><h2>失败明细</h2><div class="scroll"><table class="people"><thead>'
            '<tr><th>姓名</th><th>学号</th><th>错误</th></tr></thead><tbody>'
            f'{rows}</tbody></table></div></section>'
        )
    sections.append(f'<footer>生成于 {html.escape(meta.get("generated_at", ""))} · query.py v{VERSION}</footer>')
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>课表与课余时间 · {html.escape(meta.get("run_id", ""))}</title>'
        f'<style>{_CSS}</style></head><body><div class="wrap">'
        + "\n".join(sections)
        + '</div></body></html>'
    )


# ---------------------------------------------------------------------------
# 运行流程
# ---------------------------------------------------------------------------

def _make_run_dir(root: Path, run_id: str, demo: bool = False) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_id)
    if not safe:
        safe = "run"
    run_dir = root / safe
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"运行目录已存在且非空: {run_dir}（换 --run-id 或先清理）")
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    return run_dir


def _default_run_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _write_raw(run_dir: Path, student_id: str, text: str) -> str:
    name = _safe_name(student_id) + ".json"
    (run_dir / "raw" / name).write_text(text, encoding="utf-8")
    return f"raw/{name}"


def run_query(args: argparse.Namespace) -> int:
    if not args.authorized:
        raise SystemExit("live 模式需要 --authorized：确认名单中的每个人你都有权查询")
    roster = read_roster(args.roster)
    if args.limit:
        roster = roster[:args.limit]
    if args.dry_run:
        for idx, student in enumerate(roster, 1):
            print(f"[{idx}/{len(roster)}] {student['name']} {student['student_id']}")
            print("  " + build_plain(student["student_id"], args.semester, args.week))
        print(f"dry-run: {len(roster)} 条请求未发送")
        return 0
    if not args.key and not args.key_from_login:
        raise SystemExit("live 模式需要 --key 或 --key-from-login")
    base_url = args.base_url
    key = args.key
    if args.key_from_login:
        login_path = Path(args.key_from_login)
        if not login_path.exists():
            raise SystemExit(f"登录响应不存在: {login_path}")
        login = json.loads(login_path.read_text(encoding="utf-8"))
        jw = next((x for x in login.get("info", []) if x.get("os") == "jw"), None)
        if not jw or not jw.get("encrpt"):
            raise SystemExit(f"{args.key_from_login} 里没有 info[os=jw].encrpt")
        key = key or jw["encrpt"]
        if not args.base_url:
            base_url = jw.get("url") or DEFAULT_BASE
    if not key:
        raise SystemExit("没有可用的 jw key")
    base_url = base_url or DEFAULT_BASE

    run_id = args.run_id or _default_run_id("live")
    run_dir = _make_run_dir(Path(args.run_root), run_id)
    report_path = Path(args.out) if args.out else (run_dir / "report.html")
    headers = _headers(args.user_agent, args.header)

    manifest: dict[str, Any] = {
        "tool": "query.py", "version": VERSION, "run_id": run_id, "mode": "live",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": base_url, "semester": args.semester, "week": args.week,
        "roster": str(args.roster), "delay_seconds": args.delay,
        "students": [],
    }
    results: list[dict[str, Any]] = []
    total = len(roster)
    for idx, student in enumerate(roster, 1):
        if idx > 1 and not args.dry_run:
            time.sleep(args.delay)
        print(f"[{idx}/{total}] {student['name']} {student['student_id']} ...", flush=True)
        fetched = fetch_schedule(
            base_url, key, student, args.semester, args.week, headers,
            args.timeout, args.retries,
        )
        raw_rel = ""
        if fetched.get("raw_text"):
            raw_rel = _write_raw(run_dir, student["student_id"], fetched["raw_text"])
        result = make_result(student, fetched, raw_rel)
        results.append(result)
        manifest["students"].append({
            "name": student["name"], "student_id": student["student_id"], "class": student.get("class", ""),
            "status": result["status"], "error": result["error"],
            "http_status": result["http_status"], "raw_file": raw_rel,
            "request_plain": fetched.get("request_plain"),
            "raw_sha256": _sha256(fetched["raw_text"]) if fetched.get("raw_text") else "",
        })
        if result["status"] == "ok":
            print(f"    ok: {result['course_count']} 门课, 空闲 {result['free_count']} 节")
        else:
            print(f"    error: {result['error']}")
        _write_json(run_dir / "manifest.json", manifest)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_html(results, manifest, report_path.parent, run_dir), encoding="utf-8")
    print(f"report: {report_path}")
    print(f"raw   : {run_dir / 'raw'}")
    if args.json:
        print(json.dumps({"report": str(report_path), "run_dir": str(run_dir),
                          "ok": sum(1 for r in results if r["status"] == "ok"),
                          "total": len(results)}, ensure_ascii=False))
    return 0


def run_demo(args: argparse.Namespace) -> int:
    run_id = args.run_id or _default_run_id("demo")
    run_dir = _make_run_dir(Path(args.run_root), run_id, demo=True)
    report_path = Path(args.out) if args.out else (run_dir / "report.html")
    meta: dict[str, Any] = {
        "tool": "query.py", "version": VERSION, "run_id": run_id, "mode": "demo",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": "", "semester": DEFAULT_SEMESTER, "week": "09",
        "roster": "(synthetic)", "delay_seconds": 0, "students": [],
    }
    results: list[dict[str, Any]] = []
    for student, resp in demo_responses():
        text = json.dumps(resp, ensure_ascii=False, indent=2) + "\n"
        raw_rel = _write_raw(run_dir, student["student_id"], text)
        fetched = {"http_status": 200, "raw_text": text, "error": None,
                   "request_plain": build_plain(student["student_id"], DEFAULT_SEMESTER, "09")}
        result = make_result(student, fetched, raw_rel)
        results.append(result)
        meta["students"].append({
            "name": student["name"], "student_id": student["student_id"], "class": student.get("class", ""),
            "status": result["status"], "error": None, "http_status": 200,
            "raw_file": raw_rel, "request_plain": fetched["request_plain"],
            "raw_sha256": _sha256(text),
        })
    _write_json(run_dir / "manifest.json", meta)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_html(results, meta, report_path.parent, run_dir), encoding="utf-8")
    print(f"demo report: {report_path}")
    print(f"demo raw   : {run_dir / 'raw'}")
    return 0


def run_from_raw(args: argparse.Namespace) -> int:
    run_dir = Path(args.from_raw)
    manifest, results = load_results(run_dir)
    report_path = Path(args.out) if args.out else (run_dir / "report.html")
    report_path.write_text(build_html(results, manifest, report_path.parent, run_dir), encoding="utf-8")
    print(f"re-rendered: {report_path}")
    return 0


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def selftest() -> int:
    # 编码向量来自 Java 参考实现（ba.b.k / ba.b.f）
    assert encode_param("userid=123&x=1", "testkey") == "3w1jje3u95mj31nca92s466d003ioc"
    assert _param2("userid=123&x=1") == "fe0d4a36e2798b95624a02f7a95bbe2b"

    assert parse_periods("01,02") == [1, 2]
    assert parse_periods("3-5") == [3, 4, 5]
    assert parse_periods("07,08, 11-12") == [7, 8, 11, 12]

    students = []
    for student, resp in demo_responses():
        fetched = {"http_status": 200, "raw_text": json.dumps(resp), "error": None}
        students.append(make_result(student, fetched, ""))
    assert all(s["status"] == "ok" for s in students)
    s0 = students[0]
    assert (3, 15) in s0["free"][1], s0["free"][1]  # 周一只有 1-2 有课
    slots = common_free_slots(students, 15)
    assert any(day == 1 and a <= 5 and b == 15 for day, a, b in slots), slots

    with __import__("tempfile").TemporaryDirectory() as tmp:
        doc = build_html(students, {"run_id": "selftest", "generated_at": "now",
                                    "semester": "2026-0", "week": "09"}, Path(tmp), Path(tmp))
    assert "张三" in doc and "全员共同空闲" in doc and "空闲热力图" in doc
    print("selftest OK")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="喜鹊儿/青果课表批量查询 + 课余时间 HTML 可视化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--selftest", action="store_true", help="跑内置自检")
    mode.add_argument("--demo", action="store_true", help="用合成数据生成示例报告")
    mode.add_argument("--live", action="store_true", help="真实查询（需 --authorized）")
    mode.add_argument("--from-raw", metavar="RUN_DIR", help="从已有运行目录重新渲染")

    p.add_argument("--roster", default=str(Path(__file__).resolve().parent / "roster.example.csv"),
                   help="CSV 名单（name,student_id[,class]）")
    p.add_argument("--base-url", default="", help=f"jw 服务地址，默认 {DEFAULT_BASE}")
    p.add_argument("--key", default="", help="jw vendor key（登录响应 info[os=jw].encrpt）")
    p.add_argument("--key-from-login", default="", help="从登录响应 JSON 提取 jw key 和 url")
    p.add_argument("--semester", default=DEFAULT_SEMESTER, help=f"学期代码，默认 {DEFAULT_SEMESTER}")
    p.add_argument("--week", default="", help="周次；空=服务器当前周")
    p.add_argument("--run-root", default=str(Path(__file__).resolve().parent / "runs"), help="运行根目录")
    p.add_argument("--run-id", default="", help="运行目录名；默认时间戳")
    p.add_argument("--out", default="", help="报告路径；默认 <run_dir>/report.html")
    p.add_argument("--delay", type=float, default=3.0, help="请求间隔秒数，默认 3")
    p.add_argument("--timeout", type=float, default=20.0, help="HTTP 超时秒数")
    p.add_argument("--retries", type=int, default=2, help="失败重试次数")
    p.add_argument("--limit", type=int, default=0, help="只查前 N 人（调试用）")
    p.add_argument("--user-agent", default=DEFAULT_UA, help="UA；默认空占位")
    p.add_argument("--header", action="append", default=[], metavar="K:V", help="额外请求头，可重复")
    p.add_argument("--authorized", action="store_true", help="确认名单内每个人你都有权查询")
    p.add_argument("--dry-run", action="store_true", help="只打印请求，不发送")
    p.add_argument("--json", action="store_true", help="最后输出机器可读摘要")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if args.demo:
        return run_demo(args)
    if args.from_raw:
        return run_from_raw(args)
    if args.live:
        return run_query(args)
    # 默认：demo，方便直接看效果
    return run_demo(args)


if __name__ == "__main__":
    sys.exit(main())
