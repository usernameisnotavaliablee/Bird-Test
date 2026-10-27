#!/usr/bin/env python3
"""扫描 jadx 源码树里所有 da.b.f 回调，导出「响应解析面」清单。

用途：查他人接口的每个回调读了响应里的哪些键、异常分支怎么走、宿主类是谁。
只做静态文本匹配（不执行代码）；键名从 getString/has/opt*/get 调用里提取。

用法:
    python3 analysis/tools/parse_surface_scan.py <jadx_sources_root> [-o out.md] [--json out.json]

输出列:
    宿主类 | 回调类 | 读取键 | 异常/默认分支 | 文件:行

说明:
  * 仅扫描 `implements da.b.f` 的类；jadx 偶尔把接口写成 `da.b.f` / `da.b.InterfaceC....`，
    这里按 `da.b.f` 字面匹配（本工程 454 明文树即此形态）。
  * 键提取是启发式：`getString("x")` 记 x；`has("x")` 单独标记为 as:has；
    `getJSONObject("x")`/`getJSONArray("x")` 标记 as:obj/arr。
  * 异常分支只做「callback 内是否出现 catch + 默认赋值」的粗判，供人工复核。
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

CALLBACK_RE = re.compile(r'public\s+void\s+callback\s*\(\s*String\s+(\w+)\s*\)\s*\{')
CLASS_RE = re.compile(r'\bclass\s+(\w+)[^{]*implements[^{]*\bda\.b\.f\b')
HOST_RE = re.compile(r'\b(?:public\s+)?(?:final\s+)?(?:abstract\s+)?class\s+(\w+)')
KEY_PATTERNS = [
    (re.compile(r'\.getString\s*\(\s*"([^"]+)"'), 'str'),
    (re.compile(r'\.optString\s*\(\s*"([^"]+)"'), 'str'),
    (re.compile(r'\.has\s*\(\s*"([^"]+)"'), 'has'),
    (re.compile(r'\.getInt\s*\(\s*"([^"]+)"'), 'int'),
    (re.compile(r'\.getJSONObject\s*\(\s*"([^"]+)"'), 'obj'),
    (re.compile(r'\.getJSONArray\s*\(\s*"([^"]+)"'), 'arr'),
    (re.compile(r'\.get\s*\(\s*"([^"]+)"\s*\)'), 'any'),
    # 常量键（本项目只有这一个高频常量）
    (re.compile(r'\.getString\s*\(\s*LocationConst\.HDYawConst\.KEY_HD_YAW_STATE\s*\)'), 'str'),
]
CONST_KEYS = {'LocationConst.HDYawConst.KEY_HD_YAW_STATE': 'state'}


def find_block(text, open_idx):
    """text[open_idx] == '{'，返回匹配的 '}' 下标（跳过字符串/字符/注释）。"""
    depth = 0
    i = open_idx
    n = len(text)
    in_str = in_chr = in_line = in_block = False
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if in_line:
            if c == '\n':
                in_line = False
        elif in_block:
            if c == '*' and nxt == '/':
                in_block = False
                i += 1
        elif in_str:
            if c == '\\':
                i += 1
            elif c == '"':
                in_str = False
        elif in_chr:
            if c == '\\':
                i += 1
            elif c == "'":
                in_chr = False
        else:
            if c == '/' and nxt == '/':
                in_line = True
                i += 1
            elif c == '/' and nxt == '*':
                in_block = True
                i += 1
            elif c == '"':
                in_str = True
            elif c == "'":
                in_chr = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def line_of(text, idx):
    return text.count('\n', 0, idx) + 1


def scan_file(path, root):
    try:
        text = open(path, encoding='utf-8', errors='ignore').read()
    except OSError:
        return []
    if 'da.b.f' not in text:
        return []
    out = []
    for cm in CLASS_RE.finditer(text):
        cls_name = cm.group(1)
        # 类体起点：类声明后的第一个 '{'
        brace = text.find('{', cm.end())
        if brace < 0:
            continue
        end = find_block(text, brace)
        if end < 0:
            continue
        body = text[brace:end]
        for cb in CALLBACK_RE.finditer(body):
            cb_open = brace + cb.end() - 1  # '{' 位置
            cb_end = find_block(text, cb_open)
            if cb_end < 0:
                continue
            cb_body = text[cb_open:cb_end]
            keys = OrderedDict()
            for pat, kind in KEY_PATTERNS:
                for m in pat.finditer(cb_body):
                    k = m.group(1) if m.groups() else None
                    if k is None:
                        if 'KEY_HD_YAW_STATE' in m.group(0):
                            k = 'state'
                        else:
                            continue
                    keys.setdefault(k, set()).add(kind)
            # 异常分支粗判
            has_catch = 'catch' in cb_body
            catch_defaults = []
            for m in re.finditer(r'catch\s*\([^)]*\)\s*\{([^}]{0,300})\}', cb_body, re.S):
                seg = ' '.join(m.group(1).split())
                if re.search(r'=\s*(true|false|"|new |null|\d)', seg):
                    catch_defaults.append(seg[:120])
            rel = os.path.relpath(path, root)
            host = ''
            hm = HOST_RE.search(text)
            if hm:
                host = hm.group(1)
            out.append({
                'host': host,
                'callback_class': cls_name,
                'file': rel,
                'line': line_of(text, cb_open),
                'keys': [{'key': k, 'kinds': sorted(v)} for k, v in keys.items()],
                'has_catch': has_catch,
                'catch_defaults': catch_defaults,
                'native_calls': sorted(set(re.findall(r'\b(\w+)\(.*?\)\s*;', cb_body)))[:0],
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('-o', '--out')
    ap.add_argument('--json')
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    rows = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith('.java'):
                rows.extend(scan_file(os.path.join(dirpath, f), root))
    rows.sort(key=lambda r: (r['host'], r['callback_class'], r['file']))

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        print('json: %s (%d callbacks)' % (args.json, len(rows)), file=sys.stderr)

    md = ['| 宿主类 | 回调类 | 读取键（kind） | 异常默认分支 | 位置 |',
          '|---|---|---|---|---|']
    for r in rows:
        keys = ', '.join('%s%s' % (k['key'], '' if k['kinds'] == ['str'] else ':' + '/'.join(k['kinds']))
                         for k in r['keys']) or '—'
        default = '; '.join(r['catch_defaults']) or ('有 catch' if r['has_catch'] else '—')
        md.append('| %s | %s | %s | %s | %s:%d |' % (
            r['host'] or '?', r['callback_class'], keys,
            default.replace('|', '\\|')[:160], r['file'], r['line']))
    text = '\n'.join(md) + '\n'
    if args.out:
        open(args.out, 'w', encoding='utf-8').write(text)
        print('md: %s (%d callbacks)' % (args.out, len(rows)), file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
