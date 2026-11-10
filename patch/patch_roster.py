#!/usr/bin/env python3
"""Ta 的课表 · 课程详情班名单：复用官方「同学列表」页显示教学班学生。

原版 Home_F.I0() 在打开课程详情前已经请求 getKb&step=skbjmc，回调 Home_F$x.callback
把 resultSet 解析到 p1；但 tdkb（Ta 的课表）分支用开头固定的 v0="[]" 当 classmatesList，
且把 rs 固定为 "0"。本补丁在 tdkb 分支：
  1) new-instance Intent 之前插入 move-object v0, p1，传名单；
  2) 把 putExtra("rs", "0") 换成 CourseBean.getRs()；
  3) 把目标从 CourseDetailActivity 改成 ClassmatesListActivity，并补齐
     kcmc/bjdm/bjmc/ly，直接复用官方「同学列表」页（头像+姓名+班级+日历，点人进觅Ta）。
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
PKG = "Lcom/kingosoft/activity_kb_common/ui/activity/new_wdjx/new_kebiao/"
COURSE_DETAIL = "    const-class v10, " + PKG + "CourseDetailActivity;\n"
CLASSMATES = "    const-class v10, " + PKG + "ClassmatesListActivity;\n"
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
CONTEXT = (
    "    .line 15\n"
    "    iget-object v0, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->b:Landroid/content/Context;\n"
)
EXTRAS = (
    "    .line 15\n"
    "    const-string v1, \"kcmc\"\n\n"
    "    iget-object v2, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->c:Lcom/kingosoft/activity_kb_common/bean/CourseBean;\n\n"
    "    invoke-virtual {v2}, Lcom/kingosoft/activity_kb_common/bean/CourseBean;->getKcmc()Ljava/lang/String;\n\n"
    "    move-result-object v2\n\n"
    "    invoke-virtual {p1, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n\n"
    "    const-string v1, \"bjdm\"\n\n"
    "    iget-object v2, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->c:Lcom/kingosoft/activity_kb_common/bean/CourseBean;\n\n"
    "    invoke-virtual {v2}, Lcom/kingosoft/activity_kb_common/bean/CourseBean;->getSkbj()Ljava/lang/String;\n\n"
    "    move-result-object v2\n\n"
    "    invoke-virtual {p1, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n\n"
    "    const-string v1, \"bjmc\"\n\n"
    "    iget-object v2, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->c:Lcom/kingosoft/activity_kb_common/bean/CourseBean;\n\n"
    "    invoke-virtual {v2}, Lcom/kingosoft/activity_kb_common/bean/CourseBean;->getKcmc()Ljava/lang/String;\n\n"
    "    move-result-object v2\n\n"
    "    invoke-virtual {p1, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n\n"
    "    const-string v1, \"ly\"\n\n"
    "    const-string v2, \"OpenTxlb\"\n\n"
    "    invoke-virtual {p1, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;\n\n"
    "    iget-object v0, p0, Lcom/kingosoft/activity_kb_common/ui/activity/frame/Home_F$x;->b:Landroid/content/Context;\n"
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


def block(lines):
    """返回 tdkb 分支 [if-eqz, goto/16 :goto_1] 的下标。"""
    t = next((i for i, l in enumerate(lines) if l == TDKB), -1)
    if t < 0:
        raise SystemExit("没找到 tdkb")
    i = next((j for j in range(t + 1, len(lines)) if IF.match(lines[j])), -1)
    if i < 0:
        raise SystemExit("没找到 tdkb if-eqz")
    end = next((k for k in range(i + 1, len(lines)) if lines[k] == "    goto/16 :goto_1\n"), -1)
    if end < 0:
        raise SystemExit("没找到 tdkb 分支结尾")
    return i, end


def patch_list(lines):
    i, end = block(lines)
    sub = "".join(lines[i:end])
    changed = False
    if "ClassmatesListActivity;" not in sub:
        if sub.count(COURSE_DETAIL) != 1:
            raise SystemExit("CourseDetailActivity const-class 不唯一")
        sub = sub.replace(COURSE_DETAIL, CLASSMATES, 1)
        changed = True
    if 'const-string v1, "kcmc"' not in sub:
        if sub.count(CONTEXT) != 1:
            raise SystemExit("Context 插入点不唯一")
        sub = sub.replace(CONTEXT, EXTRAS, 1)
        changed = True
    if changed:
        lines[i:end] = sub.splitlines(True)
    return changed


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
    i, end = block(lines)
    sub = "".join(lines[i:end])
    list_ok = "ClassmatesListActivity;" in sub and 'const-string v1, "kcmc"' in sub

    if check:
        ok = roster_ok and rs_ok and list_ok
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
    if patch_list(lines):
        print("patched ClassmatesListActivity + extras")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 补丁后自检
    lines = open(path, encoding="utf-8").readlines()
    k = locate(lines)
    assert any(l.strip() == "move-object v0, p1" for l in lines[max(0, k - 4):k]), "插入点丢失"
    i, end = block(lines)
    sub = "".join(lines[i:end])
    assert "ClassmatesListActivity;" in sub, "目标类未改成 ClassmatesListActivity"
    assert 'const-string v1, "kcmc"' in sub and 'const-string v1, "bjdm"' in sub, "名单页 extras 缺失"
    assert 'invoke-virtual {p1, v6, v0}, Landroid/content/Intent;->putExtra' in sub, "classmatesList 不再用 v0"
    assert "CourseBean;->getRs()Ljava/lang/String;" in sub, "rs 未改成 getRs"
    print("check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
