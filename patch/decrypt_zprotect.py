#!/usr/bin/env python3
"""zprotect 明文 dex 还原：单字节 NOT（异或 0xFF）掩码。

发现（2026-10-03，见 HANDOFF）：壳对 payload dex 的**部分字节**做了按位取反（x ^ 0xFF），
其余字节原样。运行时 ART 读到的内存副本即明文，因此用「内存副本 vs on-disk 副本」逐字节比对
就能求出掩码：两者相同的字节 = 未加密，不同的字节 = 取反。

用法：
  decrypt_zprotect.py <on-disk-encrypted.dex> <memory-dump.dex> <out.dex>
"""
import sys


def main(enc_path, mem_path, out_path):
    enc = open(enc_path, "rb").read()
    mem = open(mem_path, "rb").read()
    if len(enc) != len(mem):
        raise SystemExit("size mismatch: %d vs %d" % (len(enc), len(mem)))
    bad = 0
    for i in range(len(enc)):
        if enc[i] != mem[i] and (enc[i] ^ mem[i]) != 0xFF:
            bad += 1
    plain = bytes(mem[i] if enc[i] == mem[i] else (~enc[i]) & 0xFF for i in range(len(enc)))
    open(out_path, "wb").write(plain)
    masked = sum(1 for i in range(len(enc)) if enc[i] != mem[i])
    print("%s -> %s | bytes=%d masked=%d(%.1f%%) non-NOT-diff=%d"
          % (enc_path, out_path, len(enc), masked, 100.0 * masked / len(enc), bad))


if __name__ == "__main__":
    main(*sys.argv[1:4])
