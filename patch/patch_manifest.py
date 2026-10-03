#!/usr/bin/env python3
"""给壳 manifest 加一个 qx.Boot provider（进程启动即构造，用于脱壳 dump）。幂等。"""
import re
import sys

PROVIDER = ('        <provider android:name="qx.Boot" '
            'android:authorities="com.kingosoft.activity_kb_common.qxdump" '
            'android:exported="false" />\n')


def main(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "qx.Boot" in s:
        print("manifest: already patched")
        return
    m = re.search(r"^(\s*)</application>", s, re.M)
    if not m:
        raise SystemExit("manifest: </application> not found")
    s = s[:m.start()] + PROVIDER + s[m.start():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print("manifest: patched ->", path)


if __name__ == "__main__":
    main(sys.argv[1])
