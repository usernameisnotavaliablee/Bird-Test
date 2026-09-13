#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 class_defs 统计每个类的字段/方法数（直接读 dex 表，不依赖 class_data）。

用途：壳加密使 class_data 不可用时，仍可从完好的 field_ids/method_ids 表
（条目含 class_idx）统计「形状」；类名（descriptor）从 string_ids 读，
可能因加密不可读——不可读的类自动跳过（计入统计）。

用法:
  python3 dex_shape_probe.py <a.dex> [<b.dex> ...] [--grep 关键词] [--stat] [--limit N]
    --grep K   只打印类名含 K 的类
    --stat     只打印统计行，不逐类打印
    --limit N  无 --grep 时逐类打印上限（默认 40）
"""
import struct
import sys


def uleb128(buf, off):
    result = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def read_string(buf, string_ids, idx):
    if idx >= len(string_ids):
        return None
    off = string_ids[idx]
    if off >= len(buf):
        return None
    try:
        _, p = uleb128(buf, off)
        end = buf.index(b'\x00', p)
        raw = buf[p:end]
        s = raw.decode('utf-8')
    except (UnicodeDecodeError, ValueError, IndexError):
        return None
    if any(ord(c) < 0x20 or c == '�' for c in s):
        return None
    return s


def probe(path, grep, stat_only, limit):
    buf = open(path, 'rb').read()
    (string_ids_size, string_ids_off, type_ids_size, type_ids_off,
     proto_ids_size, proto_ids_off, field_ids_size, field_ids_off,
     method_ids_size, method_ids_off, class_defs_size, class_defs_off) = \
        struct.unpack_from('<12I', buf, 56)

    def table(size, off):
        if size == 0 or off + size * 4 > len(buf):
            return ()
        return struct.unpack_from(f'<{size}I', buf, off)

    string_ids = table(string_ids_size, string_ids_off)
    type_ids = table(type_ids_size, type_ids_off)
    print(f"== {path}")
    print(f"   ids: string={string_ids_size} type={type_ids_size} proto={proto_ids_size} "
          f"field={field_ids_size} method={method_ids_size} class_defs={class_defs_size}")
    if not string_ids or not type_ids:
        print("   [skip] 表不可读")
        return

    fields_by_class = {}
    for i in range(field_ids_size):
        off = field_ids_off + 8 * i
        if off + 8 > len(buf):
            break
        cidx = struct.unpack_from('<H', buf, off)[0]
        fields_by_class[cidx] = fields_by_class.get(cidx, 0) + 1
    methods_by_class = {}
    for i in range(method_ids_size):
        off = method_ids_off + 8 * i
        if off + 8 > len(buf):
            break
        cidx = struct.unpack_from('<H', buf, off)[0]
        methods_by_class[cidx] = methods_by_class.get(cidx, 0) + 1

    visited = readable = 0
    shown = 0
    for i in range(class_defs_size):
        off = class_defs_off + 32 * i
        if off + 32 > len(buf):
            break
        class_idx = struct.unpack_from('<I', buf, off)[0]
        if class_idx >= len(type_ids):
            continue
        visited += 1
        desc = read_string(buf, string_ids, type_ids[class_idx])
        if desc is None:
            continue
        readable += 1
        if stat_only:
            continue
        if grep and grep not in desc:
            continue
        print(f"   {desc}  fields={fields_by_class.get(class_idx, 0)} "
              f"methods={methods_by_class.get(class_idx, 0)}")
        shown += 1
        if not grep and shown >= limit:
            print("   ... (截断，--limit/-grep 调整)")
            break
    ratio = (readable / visited * 100) if visited else 0
    print(f"   [stat] 类名可读 {readable}/{visited} ({ratio:.1f}%)；"
          f"字段类 {len(fields_by_class)} 个 / 方法类 {len(methods_by_class)} 个")


def main():
    args = sys.argv[1:]
    grep = None
    stat_only = '--stat' in args
    limit = 40
    if '--stat' in args:
        args.remove('--stat')
    if '--limit' in args:
        k = args.index('--limit')
        limit = int(args[k + 1])
        args = args[:k] + args[k + 2:]
    if '--grep' in args:
        k = args.index('--grep')
        grep = args[k + 1]
        args = args[:k] + args[k + 2:]
    for p in args:
        probe(p, grep, stat_only, limit)


if __name__ == '__main__':
    main()
