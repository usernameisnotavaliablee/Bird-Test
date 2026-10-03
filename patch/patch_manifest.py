#!/usr/bin/env python3
"""给壳 manifest 加一个 provider（进程启动即构造：挂签名绕过；dump 版还带脱壳）。幂等。"""
import re
import sys

TMPL = ('        <provider android:name="{cls}" '
        'android:authorities="com.kingosoft.activity_kb_common.qxdump" '
        'android:exported="false" />\n')


def main(path, cls="qx.Boot"):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    old = re.search(r'<provider android:name="(qx\.\w+)"[^>]*/>\n', s)
    if old:
        if old.group(1) == cls:
            print("manifest: provider already", cls)
            return
        s = s[:old.start()] + TMPL.format(cls=cls) + s[old.end():]
    else:
        m = re.search(r"^(\s*)</application>", s, re.M)
        if not m:
            raise SystemExit("manifest: </application> not found")
        s = s[:m.start()] + TMPL.format(cls=cls) + s[m.start():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print("manifest: provider ->", cls)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "qx.Boot")
