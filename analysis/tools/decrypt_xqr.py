#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""喜鹊 baseInfoServlet/登录 响应解密 + 宽窄行判定

用法:
  python3 decrypt_xqr.py <密文文件>          # 文件内容为 URL 编码的 Base64 密文
  pbpaste | python3 decrypt_xqr.py -         # 从剪贴板/管道读

算法（f9/a.java 坐实）: URLDecode -> Base64 -> AES/CBC/PKCS5
  key = loginkeyapp93214  iv = 12fg45gpsdfz34ab
"""
import base64
import json
import sys
import urllib.parse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = b"loginkeyapp93214"
IV = b"12fg45gpsdfz34ab"

# step=other 客户端路由实际消费的字段（a2/a.java 回调）
ROUTE_KEYS_STU = {"xm", "xxdm", "xh", "ssbj", "xb"}   # rxnj 分支 -> ClassmateInfoActivity
ROUTE_KEYS_TEA = {"xm", "xxdm", "jsdm"}               # rxnf 分支 -> TeaInfoActivity
# 重点敏感字段
SENSITIVE = {"sfzh", "dh", "yx", "jg", "csrq", "zzmm", "jkzk", "rxnj", "rxnf"}


def decrypt(raw: str) -> str:
    text = urllib.parse.unquote(raw.strip())
    blob = base64.b64decode(text)
    dec = Cipher(algorithms.AES(KEY), modes.CBC(IV)).decryptor()
    padded = dec.update(blob) + dec.finalize()
    pad = padded[-1]
    return padded[:-pad].decode("utf-8")


def judge(obj):
    """对 resultSet/result.data/result 里第一行做宽窄判定"""
    row = None
    if isinstance(obj, dict):
        for path in (["resultSet"], ["result", "data"], ["result"]):
            cur = obj
            for p in path:
                cur = cur.get(p) if isinstance(cur, dict) else None
            if isinstance(cur, list) and cur:
                row = cur[0]
                break
        if row is None:
            row = obj
    elif isinstance(obj, list) and obj:
        row = obj[0]
    if not isinstance(row, dict):
        print("[判定] 未找到可判定的行")
        return
    keys = set(row.keys())
    print(f"[判定] 首行 {len(keys)} 键: {sorted(keys)}")
    hit_s = keys & SENSITIVE
    print(f"[判定] 敏感字段命中: {sorted(hit_s) if hit_s else '无'}")
    if "rxnj" in keys or "xh" in keys:
        extra = keys - ROUTE_KEYS_STU
        print(f"[判定] 学生路由字段 {sorted(ROUTE_KEYS_STU)}; 超出字段: {sorted(extra)}")
    elif "rxnf" in keys or "jsdm" in keys:
        extra = keys - ROUTE_KEYS_TEA
        print(f"[判定] 教师路由字段 {sorted(ROUTE_KEYS_TEA)}; 超出字段: {sorted(extra)}")
    wide = bool(hit_s)
    print(f"[结论] {'宽行 -> 水平越权+批量拖库面' if wide else '窄行 -> 降级为客户端解析面过宽+弱鉴权'}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
    plain = decrypt(raw)
    print("[明文]", plain[:2000])
    try:
        judge(json.loads(plain))
    except json.JSONDecodeError:
        print("[判定] 明文不是 JSON，请人工检查")


if __name__ == "__main__":
    main()
