#!/usr/bin/env python3
"""掏门禁：把 454 客户端「觅Ta 开关」闸门的条件跳转抹平（照改版做法——只保留 state==1 那条路）。

原理：闸门在 smali 里都是
    const-string vX, "1"
    invoke-virtual {vY, vX}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result vZ
    if-eqz vZ, :bad      ← 未开启时跳去弹窗
把 `if-eqz vZ, :bad` 换成 `nop` → 永远走"已开启"那条路（弹窗成为死代码）。
另有几处是「if (state != 1) { 弹窗 }」与「if (自己/对方开关不为 0) { 弹窗 }」的守卫块，
走 special 规则把入块跳转抹平。

用法：patch_gates.py <smali 树根>
"""
import re
import sys

# 通用规则：state/mita 的 "1" 比较之后的 if-eqz 抹平（限定方法名，避免误伤）
GENERIC_FILES = [
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/MitaNewActivity$h$a.smali", "public callback"),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/MitaNewListActivity$a$a.smali", "public callback"),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/TdkbActivity$b.smali", "public callback"),
    ("smali_classes2/e2/a$e.smali", "public callback"),
    ("smali_classes2/w8/b$a$a.smali", "public callback"),
    ("smali_classes3/t9/t0$a.smali", "public callback"),
    ("smali_classes3/t9/t0$b.smali", "public callback"),
]

# 「if (state != 1) { 弹窗 }」型守卫：把进块的两处跳转都抹平
SPECIAL = [
    ("smali_classes2/e2/a$g.smali", [
        ('    move-result-object p1\n\n    if-eqz p1, :cond_0\n',
         '    move-result-object p1\n\n    nop\n'),
        ('    move-result p1\n\n    if-eqz p1, :cond_0\n',
         '    move-result p1\n\n    nop\n'),
    ]),
    # 回调里第二次用到 mita flag 的地方（列表 vs 弹窗）
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/ClassmateInfoActivity$l.smali", [
        ('    if-eqz v8, :cond_7\n', '    nop\n'),
    ]),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/ClassmateInfoActivity$m.smali", [
        ('    if-eqz v8, :cond_7\n', '    nop\n'),
    ]),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/TeaInfoActivity$j.smali", [
        ('    if-eqz v6, :cond_4\n', '    nop\n'),
    ]),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/TeaInfoActivity$k.smali", [
        ('    if-eqz v6, :cond_4\n', '    nop\n'),
    ]),
    # 「您/对方的觅Ta开关未开启」守卫块（onClick 里）→ 两处入块跳转抹平
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/TeaInfoActivity$b.smali", [
        ('    move-result p1\n\n    if-eqz p1, :cond_0\n',
         '    move-result p1\n\n    nop\n'),
    ]),
    ("smali_classes2/com/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/ClassmateInfoActivity$a.smali", [
        ('    move-result p1\n\n    if-eqz p1, :cond_0\n',
         '    move-result p1\n\n    nop\n'),
    ]),
]


def split_methods(lines):
    """返回 [(method_header_index, end_index, header_text)]"""
    out = []
    start = None
    for i, l in enumerate(lines):
        if l.startswith(".method"):
            start = i
        elif l.startswith(".end method") and start is not None:
            out.append((start, i, lines[start]))
            start = None
    return out


def patch_generic(root, path, method_filter):
    full = "%s/%s" % (root, path)
    with open(full, encoding="utf-8") as f:
        lines = f.readlines()
    n = 0
    for s, e, hdr in split_methods(lines):
        if method_filter not in hdr:
            continue
        for i in range(s, e):
            m = re.match(r'^(\s*)move-result ([vp]\d+)\s*$', lines[i])
            if not m:
                continue
            reg = m.group(2)
            # 往前找 const-string X, "1" + invoke-virtual {Y, X}, String->equals
            back = "".join(lines[max(s, i - 24):i])
            if 'const-string' not in back or '"1"' not in back:
                continue
            if 'Ljava/lang/String;->equals(Ljava/lang/Object;)Z' not in back:
                continue
            # 往后找第一条 if-eqz
            for j in range(i + 1, min(e, i + 9)):
                b = re.match(r'^(\s*)if-eqz %s, (:\w+)\s*$' % re.escape(reg), lines[j])
                if b:
                    lines[j] = b.group(1) + "nop\n"
                    n += 1
                    break
    if n:
        with open(full, "w", encoding="utf-8") as f:
            f.writelines(lines)
    return n


def patch_special(root, path, rules):
    full = "%s/%s" % (root, path)
    with open(full, encoding="utf-8") as f:
        txt = f.read()
    n = 0
    for old, new in rules:
        c = txt.count(old)
        if c == 0:
            continue
        txt = txt.replace(old, new)
        n += c
    if n:
        with open(full, "w", encoding="utf-8") as f:
            f.write(txt)
    return n


def main(root):
    total = 0
    for path, mf in GENERIC_FILES:
        n = patch_generic(root, path, mf)
        total += n
        print("%-100s generic patched=%d" % (path.split('/')[-1], n))
    for path, rules in SPECIAL:
        n = patch_special(root, path, rules)
        total += n
        print("%-100s special patched=%d" % (path.split('/')[-1], n))
    print("total branches neutralised:", total)


if __name__ == "__main__":
    main(sys.argv[1])
