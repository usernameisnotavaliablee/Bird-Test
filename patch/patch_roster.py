#!/usr/bin/env python3
"""Ta 的课表 · 课程详情班名单：把已拉到的 resultSet 传给 CourseDetailActivity。

原版 Home_F.I0() 在打开课程详情前已经请求 getKb&step=skbjmc，回调 Home_F$x.callback
把 resultSet 解析到 p1；但 tdkb（Ta 的课表）分支用开头固定的 v0="[]" 当 classmatesList，
且把 rs 固定为 "0"。本补丁在 tdkb 分支：
  1) new-instance Intent 之前插入 move-object v0, p1，传名单；
  2) 把 putExtra("rs", "0") 换成 CourseBean.getRs()，否则详情页按 0 人处理。
不发新请求、不改 skbj、不改 soure/kbtype。

用法:
    patch_roster.py <smali 树根>
    patch_roster.py --check <smali 树根>
"""
import re
import sys

REL = "smali_classes2/com/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x.smali"
TDKB = '    const-string v3, "tdkb"\n'
IF = re.compile(r'^    if-eqz v1, (:\w+)\s*$')
INTENT = "    new-instance p1, Landroid/content/Intent;\n"
RS_OLD = (
    "    .line 11\n"
    "    invoke-virtual {p1, v9, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n"
)
RS_NEW = (
    "    .line 11\n"
    "    iget-object v1, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->c:Lcom/kingosoft/activity_kb_common/bean/CourseBean;\n\n"
    "    invoke-virtual {v1}, Lcom/kingosoft/activity_kb_common/bean/CourseBean;->getRs()Ljava/lang/String;\n\n"
    "    move-result-object v1\n\n"
    "    invoke-virtual {p1, v9, v1}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n"
)


def locate(lines):
    """返回 tdkb 分支 Intent 构造前的插入下标；找不到则报错。"""
    for i, line in enumerate(lines):
        if line != TDKB:
            continue
        for j in range(i + 1, min(i + 40, len(lines))):
            if IF.match(lines[j]):
                for k in range(j + 1, min(j + 8, len(lines))):
                    if lines[k] == INTENT:
                        return k
                raise SystemExit("tdkb 分支后 8 行内没找到 Intent 构造")
        raise SystemExit("tdkb 判断后 40 行内没找到 if-eqz")
    raise SystemExit("没找到 const-string v3, \"tdkb\"（Home_F$x 结构变了）")


def main(argv):
    args = [a for a in argv[1:] if a != "--check"]
    check = len(args) != len(argv) - 1
    if len(args) != 1:
        raise SystemExit(__doc__)
    path = args[0].rstrip("/") + "/" + REL
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    k = locate(lines)
    roster_ok = any(l.strip() == "move-object v0, p1" for l in lines[max(0, k - 4):k])
    txt = "".join(lines)
    rs_ok = "CourseBean;->getRs()Ljava/lang/String;" in txt

    if check:
        ok = roster_ok and rs_ok
        print(("OK" if ok else "MISSING") + ": " + path)
        return 0 if ok else 1

    if not roster_ok:
        lines.insert(k, "    move-object v0, p1\n\n")
        print("patched classmatesList")
    if not rs_ok:
        txt = "".join(lines)
        if txt.count(RS_OLD) != 1:
            raise SystemExit("rs 替换点不唯一/未找到: count=%d" % txt.count(RS_OLD))
        lines = txt.replace(RS_OLD, RS_NEW, 1).splitlines(True)
        print("patched rs")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 补丁后自检
    lines = open(path, encoding="utf-8").readlines()
    k = locate(lines)
    assert any(l.strip() == "move-object v0, p1" for l in lines[max(0, k - 4):k]), "插入点丢失"
    tail = "".join(lines[k:k + 40])
    assert 'invoke-virtual {p1, v6, v0}, Landroid/content/Intent;->putExtra' in tail, "classmatesList 不再用 v0"
    assert "CourseBean;->getRs()Ljava/lang/String;" in tail, "rs 未改成 getRs"
    print("check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
