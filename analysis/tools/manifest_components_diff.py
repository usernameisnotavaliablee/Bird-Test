#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比两个反编译 AndroidManifest.xml（XML 明文）的组件清单。

用法:
  python3 manifest_components_diff.py <left.xml> <right.xml> [--output out.json]

left = 基线（452/435），right = 新版（454）。
输出 activity / activity-alias / service / receiver / provider 的 added/removed 清单。
"""
import json
import re
import sys

TAG_RE = re.compile(r'<(activity-alias|activity|service|receiver|provider)\b(.*?)(?:/>|>)', re.S)
NAME_RE = re.compile(r'android:name="([^"]+)"')


def components(path):
    text = open(path, encoding='utf-8').read()
    out = {}
    for tag, body in TAG_RE.findall(text):
        m = NAME_RE.search(body)
        if m:
            out.setdefault(tag, set()).add(m.group(1))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    left_path, right_path = sys.argv[1], sys.argv[2]
    l, r = components(left_path), components(right_path)
    report = {}
    for tag in sorted(set(l) | set(r)):
        a, b = l.get(tag, set()), r.get(tag, set())
        report[tag] = {
            'left_count': len(a),
            'right_count': len(b),
            'added': sorted(b - a),
            'removed': sorted(a - b),
        }
    print(f"left  = {left_path}")
    print(f"right = {right_path}")
    for tag, d in report.items():
        print(f"== {tag}: {d['left_count']} -> {d['right_count']}  (+{len(d['added'])} / -{len(d['removed'])})")
        for n in d['added']:
            print(f"   + {n}")
        for n in d['removed']:
            print(f"   - {n}")
    if '--output' in sys.argv:
        out = sys.argv[sys.argv.index('--output') + 1]
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"saved: {out}")


if __name__ == '__main__':
    main()
