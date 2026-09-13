#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给定 dex 与类名前缀（如 'Lcom/x/y/'），统计该前缀区间内 class_defs 的总数。

原理：class_defs 完好 → class_idx → type_ids → string_ids 下标。字符串表按内容排序，
同前缀类名在表中连续。取「可读类名」中该区间的左右括号，统计括号之间（按 desc 下标）
的 class_defs 数 = 该包的类总数（可读 + 名字被壳遮蔽的）。
用途：在不解密的前提下判断某个包是否还存在、大概有多少类。

用法:
  python3 dex_class_band.py <dex> [<dex>...] --prefix 'Lcom/x/y/'
"""
import bisect
import struct
import sys


def uleb(buf, off):
    r = 0
    s = 0
    while True:
        b = buf[off]
        off += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80):
            return r, off
        s += 7


def read_str(buf, sids, idx):
    if idx >= len(sids):
        return None
    off = sids[idx]
    if off >= len(buf):
        return None
    try:
        _, p = uleb(buf, off)
        e = buf.index(b'\x00', p)
        s = buf[p:e].decode('utf-8')
    except Exception:
        return None
    if any(ord(c) < 0x20 or c == '�' for c in s):
        return None
    return s


def one(path, prefix):
    buf = open(path, 'rb').read()
    (ss, so, ts, to, ps, po, fs, fo, ms, mo, cs, co) = struct.unpack_from('<12I', buf, 56)
    if so + ss * 4 > len(buf) or to + ts * 4 > len(buf) or co + cs * 32 > len(buf):
        print(f"== {path}\n   [skip] 表越界")
        return
    sids = struct.unpack_from(f'<{ss}I', buf, so)
    tids = struct.unpack_from(f'<{ts}I', buf, to)
    classes = []
    for i in range(cs):
        ci = struct.unpack_from('<I', buf, co + 32 * i)[0]
        if ci >= len(tids):
            continue
        di = tids[ci]
        classes.append((di, read_str(buf, sids, di)))
    classes.sort()
    readable = [(d, n) for d, n in classes if n]
    print(f"== {path}")
    print(f"   class_defs={len(classes)}  可读类名={len(readable)}  隐藏={len(classes) - len(readable)}")

    run = [(d, n) for d, n in readable if n.startswith(prefix)]
    print(f"   -- 前缀匹配的可读类名: {len(run)} 个")
    for d, n in run[:60]:
        print(f"      [{d}] {n}")

    names = [n for _, n in readable]
    left = bisect.bisect_left(names, prefix)
    prev = readable[left - 1] if left > 0 else None
    right = bisect.bisect_left(names, prefix + '\U0010ffff')
    nxt = readable[right] if right < len(readable) else None
    lo = prev[0] if prev else -1
    hi = nxt[0] if nxt else (1 << 60)
    band = [(d, n) for d, n in classes if lo < d < hi]
    band_r = [(d, n) for d, n in band if n]
    print(f"   -- 括号: prev={prev}")
    print(f"            next={nxt}")
    print(f"   -- 区间内 class_defs: {len(band)} 个（可读 {len(band_r)}，隐藏 {len(band) - len(band_r)}）")
    for d, n in band_r[:80]:
        print(f"      [{d}] {n}")


def main():
    args = sys.argv[1:]
    prefix = ''
    if '--prefix' in args:
        k = args.index('--prefix')
        prefix = args[k + 1]
        args = args[:k] + args[k + 2:]
    for p in args:
        try:
            one(p, prefix)
        except Exception as e:
            print(f"== {p}\n   [error] {e}")


if __name__ == '__main__':
    main()
