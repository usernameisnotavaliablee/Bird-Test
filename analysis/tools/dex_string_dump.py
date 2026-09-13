#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 dex 中「可读」字符串（跳过加密/乱码区），用于加密壳的字符串级侦察。

用法:
  python3 dex_string_dump.py <dex> [输出文件]

输出格式: 每行 "<string_ids 下标>\t<字符串>"。
统计信息打到 stderr（不污染输出文件的 grep）。
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


def main():
    src = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    buf = open(src, 'rb').read()
    string_ids_size, string_ids_off = struct.unpack_from('<II', buf, 56)
    out = open(out_path, 'w', encoding='utf-8') if out_path else sys.stdout
    ok = bad = 0
    for i in range(string_ids_size):
        off_pos = string_ids_off + 4 * i
        if off_pos + 4 > len(buf):
            break
        off = struct.unpack_from('<I', buf, off_pos)[0]
        if off >= len(buf):
            bad += 1
            continue
        try:
            _, p = uleb128(buf, off)
            end = buf.index(b'\x00', p)
            s = buf[p:end].decode('utf-8')
        except (UnicodeDecodeError, ValueError, IndexError):
            bad += 1
            continue
        if any(ord(c) < 0x20 or c == '�' for c in s):
            bad += 1
            continue
        out.write(f"{i}\t{s}\n")
        ok += 1
    if out_path:
        out.close()
    print(f"[{src}] 可读 {ok} / 总 {string_ids_size}（坏/加密 {bad}）", file=sys.stderr)


if __name__ == '__main__':
    main()
