#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描文件中可能存在的压缩流（判断壳的“密文区”是否其实是压缩数据）。

用法:
  python3 zlib_scan.py <file> [<file> ...]
  python3 zlib_scan.py --strdata <dex> <idx[,idx...]>
      # 打印指定 string_ids 下标对应字符串的原始数据（十六进制），用于观察隐藏区字节形态
"""
import bz2
import lzma
import struct
import sys
import zlib

SIGS = [
    (b'\x78\x01', 'zlib'), (b'\x78\x9c', 'zlib'),
    (b'\x78\xda', 'zlib'), (b'\x78\x5e', 'zlib'),
    (b'\x1f\x8b\x08', 'gzip'),
    (b'\xfd7zXZ\x00', 'xz'),
    (b'BZh', 'bz2'),
]


def try_zlib(data, i, wbits):
    try:
        d = zlib.decompressobj(wbits)
        out = d.decompress(data[i:i + 8 * 1024 * 1024], 32 * 1024 * 1024)
        while not d.eof and len(out) < 32 * 1024 * 1024:
            more = d.decompress(b'', 1024 * 1024)
            if not more:
                break
            out += more
        return len(out) if d.eof else None
    except Exception:
        return None


def try_lzma(data, i):
    try:
        d = lzma.LZMADecompressor()
        out = d.decompress(data[i:i + 8 * 1024 * 1024], 32 * 1024 * 1024)
        return len(out) if out else None
    except Exception:
        return None


def try_bz2(data, i):
    try:
        d = bz2.BZ2Decompressor()
        out = d.decompress(data[i:i + 8 * 1024 * 1024], 32 * 1024 * 1024)
        return len(out) if out else None
    except Exception:
        return None


def scan(path):
    data = open(path, 'rb').read()
    hits = []
    for sig, kind in SIGS:
        start = 0
        while True:
            i = data.find(sig, start)
            if i < 0:
                break
            start = i + 1
            if kind == 'zlib':
                n = try_zlib(data, i, 15) or try_zlib(data, i, -15)
            elif kind == 'gzip':
                n = try_zlib(data, i, 47)
            elif kind == 'xz':
                n = try_lzma(data, i)
            else:
                n = try_bz2(data, i)
            if n and n >= 512:
                hits.append((i, n, kind))
    hits.sort()
    print(f"== {path}  size={len(data)}  压缩流命中={len(hits)}")
    for off, n, kind in hits[:24]:
        print(f"   0x{off:08x}  {kind}  ->  {n} 字节")


def strdata(dex, idxs):
    buf = open(dex, 'rb').read()
    ss, so = struct.unpack_from('<II', buf, 56)
    sids = struct.unpack_from(f'<{ss}I', buf, so)
    for idx in idxs:
        off = sids[idx]
        chunk = buf[off:off + 48]
        print(f"idx={idx} off=0x{off:x}")
        print(f"    hex:   {chunk.hex()}")
        print(f"    ascii: {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")


def main():
    args = sys.argv[1:]
    if args and args[0] == '--strdata':
        strdata(args[1], [int(x) for x in args[2].split(',')])
        return
    for p in args:
        scan(p)


if __name__ == '__main__':
    main()
