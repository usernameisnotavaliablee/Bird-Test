#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计 dex 中 class_defs 的「名字缺口」：给一个包前缀，报告它在字符串表中的隐藏范围。

原理：class_defs 完好 -> class_idx -> type_ids -> string_ids 下标（不依赖 class_data）。
字符串表按内容排序；「可读类名」是隐藏区之外的抽样。若某包的全部类名都落在隐藏区，
就在相邻两个可读类名之间形成一个大缺口；缺口内的 class_defs 数量 = 该区间类的总数
（其中类名不可读的即被壳遮蔽的部分）。

用法:
  python3 dex_class_span.py <dex> [<dex> ...] --prefix 'Lcom/x/y/'
输出: 每个 dex 的总类数/可读数；前缀匹配类；括号对（下界/上界可读类名）；
      括号区间内 class_defs 总数、可读/隐藏拆分。
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
    readable = sorted((d, n) for d, n in classes if n)
    hidden = sum(1 for _, n in classes if not n)
    print(f"== {path}")
    print(f"   class_defs={cs}  类名可读={len(readable)}  类名隐藏={hidden}")

    match = [(d, n) for d, n in readable if n.startswith(prefix)]
    print(f"   -- 可读且以 {prefix} 开头的类: {len(match)} 个")
    for d, n in match[:40]:
        print(f"      [{d}] {n}")

    names = [n for _, n in readable]
    pos = bisect.bisect_left(names, prefix)
    lo = readable[pos - 1] if pos > 0 else None
    hi = readable[pos] if pos < len(readable) else None
    print(f"   -- 括号对: 下界={lo}  上界={hi}")
    if lo and hi:
        mid = [(d, n) for d, n in classes if lo[0] < d < hi[0]]
        mid_r = [(d, n) for d, n in mid if n]
        print(f"   -- 区间 [{lo[0]}, {hi[0]}] 内 class_defs: {len(mid)} 个；"
              f"可读 {len(mid_r)}，隐藏 {len(mid) - len(mid_r)}")
        for d, n in mid_r[:80]:
            print(f"      [{d}] {n}")


def main():
    args = sys.argv[1:]
    prefix = None
    if '--prefix' in args:
        k = args.index('--prefix')
        prefix = args[k + 1]
        args = args[:k] + args[k + 2:]
    for p in args:
        try:
            one(p, prefix or '')
        except Exception as e:
            print(f"== {p}\n   [error] {e}")


if __name__ == '__main__':
    main()
