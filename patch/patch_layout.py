#!/usr/bin/env python3
"""在首页布局的标题栏右侧（@id/blue 更多按钮左边）插入 qx.MitaEntry 控件。幂等。"""
import sys

ANCHOR = '<ImageView android:id="@id/blue"'
VIEW = ('<qx.MitaEntry android:layout_width="wrap_content" android:layout_height="match_parent" '
        'android:layout_toLeftOf="@id/blue" android:layout_centerVertical="true" '
        'android:layout_marginRight="4.0dp" />\n            ')


def main(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "qx.MitaEntry" in s:
        print("layout: already patched")
        return
    if ANCHOR not in s:
        raise SystemExit("layout: anchor not found: " + ANCHOR)
    s = s.replace(ANCHOR, VIEW + ANCHOR, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print("layout: patched ->", path)


if __name__ == "__main__":
    main(sys.argv[1])
