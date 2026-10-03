#!/usr/bin/env bash
# 喜鹊 · 2.6.454「榨干Ta」探测版：在 qx-454-mita 的基础上，
#   + ActivityLifecycleCallbacks 在他人页面浮一个「榨干Ta」按钮
#   + qx.ProbeActivity 弹窗：用 App 自己的 Lda/b; 请求并把服务端下发的键值全摊开
# 前置：/tmp/qx_build/flat 解包树（含已掏门禁的 smali）、analysis/latest/unpacked/plain/*.dex
# 产物：patch/out/qx-454-probe.apk
set -euo pipefail

WS=/Users/mac/Documents/喜鹊
SDK="${QX_SDK:-/tmp/qx_build/sdk2}"
TREE="${QX_TREE:-/tmp/qx_build/flat}"
BUILD="${QX_BUILD:-/tmp/qx_build/build-probe}"
OUT="$WS/patch/out"
MODSRC="$WS/analysis/modified/apktool"

BT=$(dirname "$(find "$SDK" -maxdepth 4 -name apksigner 2>/dev/null | head -1)")
AJAR=$(find "$SDK" -maxdepth 4 -name android.jar 2>/dev/null | head -1)
R8="${QX_R8:-/tmp/qx_build/r8.jar}"
[ -d "$TREE" ] || { echo "!! 解包树不存在: $TREE"; exit 1; }
[ -n "$AJAR" ] || { echo "!! android.jar 未找到 (QX_SDK=$SDK)"; exit 1; }
mkdir -p "$BUILD"

echo "== 1/8 页面/布局（幂等）"
python3 "$WS/patch/patch_layout.py" "$TREE/res/layout/home_page_grid.xml"
python3 "$WS/patch/patch_gates.py" "$TREE" | tail -3

echo "== 2/8 manifest：Application + provider + ProbeActivity"
python3 - "$TREE/AndroidManifest.xml" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
if 'com.nesun.stub.ZAP' in s:
    s = s.replace('android:name="com.nesun.stub.ZAP"',
                  'android:name="com.kingosoft.activity_kb_common.BaseApplication"')
    print("   application -> BaseApplication")
else:
    print("   application 已是业务 Application")
if 'qx.ProbeActivity' not in s:
    act = ('        <activity android:name="qx.ProbeActivity" '
           'android:exported="false" android:excludeFromRecents="true" '
           'android:theme="@android:style/Theme.DeviceDefault.Dialog" />\n')
    m = re.search(r"^(\s*)</application>", s, re.M)
    if not m:
        raise SystemExit("manifest: </application> not found")
    s = s[:m.start()] + act + s[m.start():]
    print("   activity -> qx.ProbeActivity")
else:
    print("   activity 已在")
open(p, "w", encoding="utf-8").write(s)
PY
python3 "$WS/patch/patch_manifest.py" "$TREE/AndroidManifest.xml" qx.Boot

echo "== 3/8 清壳层 lib/资源"
rm -f "$TREE"/lib/*/libzprotect.so "$TREE"/assets/origin.apk "$TREE"/assets/libso.zip 2>/dev/null || true

echo "== 4/8 复用改版签名绕过 smali"
if [ ! -d "$TREE/smali_classes6/bin/mt/signature" ]; then
  mkdir -p "$TREE/smali_classes6/bin/mt" "$TREE/smali_classes6/org"
  cp -R "$MODSRC/smali_classes3/bin/mt/signature" "$TREE/smali_classes6/bin/mt/"
  cp -R "$MODSRC/smali_classes3/org/lsposed" "$TREE/smali_classes6/org/"
fi
echo "   $(find "$TREE/smali_classes6" -name '*.smali' | wc -l | tr -d ' ') smali"

echo "== 5/8 编译桩（javac 读不了 dex，仅编译期用）"
STUB="$BUILD/stubs"; rm -rf "$STUB"; mkdir -p "$STUB"
javac -nowarn --release 8 -classpath "$AJAR" -d "$STUB" $(find "$WS/patch/stubs" -name '*.java')

echo "== 6/8 编译注入 dex（qx/*）"
SRC="$BUILD/classes"; rm -rf "$SRC" "$BUILD/dex"; mkdir -p "$SRC" "$BUILD/dex"
javac -nowarn --release 8 -classpath "$AJAR:$STUB" -d "$SRC" \
  $(find "$WS/patch/src/qx" -name '*.java' | grep -v -e '/BootDump.java' -e '/Dumper.java' -e '/Smoke.java')
java -cp "$R8" com.android.tools.r8.D8 --min-api 21 --lib "$AJAR" --output "$BUILD/dex" \
  --classpath "$STUB" $(find "$SRC" -name '*.class') > "$BUILD/d8.log" 2>&1
mv "$BUILD/dex/classes.dex" "$BUILD/classes7.dex"
echo "   classes7.dex $(wc -c < "$BUILD/classes7.dex") bytes"

echo "== 7/8 apktool 回编（慢）"
apktool b "$TREE" -o "$BUILD/unsigned.apk" > "$BUILD/apktool-b.log" 2>&1

echo "== 8/8 塞注入 dex + 对齐 + 签名"
python3 - "$BUILD/unsigned.apk" "$BUILD/classes7.dex" "$BUILD/withdex.apk" <<'PY'
import sys, zipfile
src, dex, dst = sys.argv[1:4]
zin = zipfile.ZipFile(src)
names = set(zin.namelist())
zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    zout.writestr(it, zin.read(it.filename))
if 'classes7.dex' not in names:
    zout.write(dex, 'classes7.dex')
zout.close(); zin.close()
z = zipfile.ZipFile(dst)
print("   dex:", sorted(n for n in z.namelist() if n.startswith('classes') and n.endswith('.dex')),
      "| entries:", len(z.infolist()))
PY
KS="$WS/patch/qx.keystore"
mkdir -p "$OUT"
"$BT/zipalign" -f -p 4 "$BUILD/withdex.apk" "$BUILD/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:qx123456 --key-pass pass:qx123456 \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT/qx-454-probe.apk" "$BUILD/aligned.apk"
"$BT/apksigner" verify "$OUT/qx-454-probe.apk" | head -3
echo "== done: $OUT/qx-454-probe.apk $(wc -c < "$OUT/qx-454-probe.apk") bytes"
