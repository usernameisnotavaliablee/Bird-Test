#!/usr/bin/env python3
"""娜迦(zprotect) at-rest payload dex 解密：分段按位取反 (x -> ~x)，跳过 0x00/0xFF。

规则（2026-10-04 由 454 明文/密文对照逐字节坐实，对 3 个 dex 零反例）：
  设 T = 加密区起点（字节偏移），
    offset <  T : 明文原样
    offset >= T : enc = p           若 p ∈ {0x00, 0xFF}
                  enc = (~p) & 0xFF 其它
  该映射是双射，故解密无歧义：
    p = enc          若 enc ∈ {0x00, 0xFF}
    p = (~enc)&0xFF  其它

T 的定位：dex 头/ids/class_defs 均在加密区之前，可直接解析 string_ids。
dex 工具链按 string_ids 顺序排布 string_data_item，因此**第一个解不出的字符串**
（ULEB 长度与 MUTF-8 单位数不符 / 越界）必然横跨 T；在该 item 的字节范围内
枚举 T，取能让全表字符串自洽、且头部 SHA-1/Adler-32 与重算值一致的那个。

用法：
  unmask_zprotect.py <encrypted.dex> <out.dex> [more pairs...]
自检（需要仓库内 454 产物）：
  unmask_zprotect.py --selftest
"""
import hashlib
import struct
import sys
import zlib

HDR_KEYS = ['file_size', 'header_size', 'endian', 'link_size', 'link_off', 'map_off',
            'string_ids_size', 'string_ids_off', 'type_ids_size', 'type_ids_off',
            'proto_ids_size', 'proto_ids_off', 'field_ids_size', 'field_ids_off',
            'method_ids_size', 'method_ids_off', 'class_defs_size', 'class_defs_off',
            'data_size', 'data_off']


def header(b):
    return dict(zip(HDR_KEYS, struct.unpack_from('<20I', b, 32)))


def string_item_end(b, off, limit=None):
    """解析 string_data_item（按明文），返回结束偏移；不合法返回 None。"""
    i, val, shift, n = off, 0, 0, 0
    while True:
        if i >= len(b) or n > 4:
            return None
        c = b[i]
        val |= (c & 0x7F) << shift
        shift += 7
        n += 1
        i += 1
        if c < 0x80:
            break
    j, units = i, 0
    while True:
        if j >= len(b):
            return None
        c = b[j]
        if c == 0:
            break
        if c < 0x80:
            j += 1
        elif (c & 0xE0) == 0xC0:
            j += 2
        elif (c & 0xF0) == 0xE0:
            j += 3
        elif (c & 0xF8) == 0xF0:
            j += 4
        else:
            return None
        units += 1
    if units != val or (limit is not None and j + 1 > limit):
        return None
    return j + 1


def strings_ok(b, h, lo, hi):
    offs = struct.unpack_from('<%dI' % h['string_ids_size'], b, h['string_ids_off'])
    for idx in range(lo, min(hi, h['string_ids_size'])):
        limit = offs[idx + 1] if idx + 1 < h['string_ids_size'] else None
        if string_item_end(b, offs[idx], limit) is None:
            return False
    return True


def unmask(enc, t):
    out = bytearray(enc)
    for i in range(t, len(enc)):
        v = enc[i]
        if v != 0 and v != 0xFF:
            out[i] = (~v) & 0xFF
    return bytes(out)


def header_ok(b):
    return (zlib.adler32(b[12:]) & 0xFFFFFFFF) == struct.unpack_from('<I', b, 8)[0] \
        and hashlib.sha1(b[32:]).digest() == b[12:32]


def find_t(enc):
    h = header(enc)
    offs = struct.unpack_from('<%dI' % h['string_ids_size'], enc, h['string_ids_off'])
    first_bad = None
    for idx in range(h['string_ids_size']):
        limit = offs[idx + 1] if idx + 1 < h['string_ids_size'] else None
        if string_item_end(enc, offs[idx], limit) is None:
            first_bad = idx
            break
    # 候选区间：第一个坏串的数据起点 ~ 下一个串起点
    lo = offs[first_bad] if first_bad is not None else 0
    hi = offs[first_bad + 1] if first_bad is not None and first_bad + 1 < h['string_ids_size'] else len(enc)
    checked = 0
    for t in range(lo, hi):
        cand = unmask(enc, t)
        if not strings_ok(cand, h, first_bad, first_bad + 64):
            continue
        checked += 1
        if header_ok(cand) or checked > 1:
            return t, cand
    # 兜底：全量枚举 T，用头部 SHA-1 判定（小文件可行）
    if len(enc) <= 1 << 20:
        for t in range(len(enc)):
            cand = unmask(enc, t)
            if header_ok(cand):
                return t, cand
    raise SystemExit('T not found (first_bad=%s)' % first_bad)


def main(argv):
    if argv[:1] == ['--selftest']:
        base = 'analysis/latest/unpacked'
        for name in ('classes.dex', 'classes2.dex', 'classes3.dex'):
            enc = open('%s/zprotect/%s' % (base, name), 'rb').read()
            plain = open('%s/plain/%s' % (base, name), 'rb').read()
            t, cand = find_t(enc)
            assert cand == plain and header_ok(cand), name
            print('selftest ok %s T=%d' % (name, t))
        return
    for i in range(0, len(argv), 2):
        src, dst = argv[i], argv[i + 1]
        enc = open(src, 'rb').read()
        t, cand = find_t(enc)
        open(dst, 'wb').write(cand)
        print('%s -> %s | T=%d bytes=%d header_ok=%s'
              % (src, dst, t, len(cand), header_ok(cand)))


if __name__ == '__main__':
    main(sys.argv[1:])
