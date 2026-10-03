#!/usr/bin/env bash
# 喜鹊 · 最新版 2.6.454「觅Ta」魔改：去壳扁平化 + 掏门禁 + 首页入口按钮 + 签名绕过
# 前置：analysis/latest/unpacked/plain/classes*.dex（明文 dex）已就位
# 产物：patch/out/qx-454-mita.apk
set -euo pipefail

WS=/Users/mac/Documents/喜鹊
SDK="${QX_SDK:-/tmp/qx_build/sdk2}"
UNP="$WS/analysis/latest/unpacked"
TREE="${QX_TREE:-/tmp/qx_build/flat}"          # apktool 解包树（base_flat.apk 解出）
BUILD=/tmp/qx_build/build-mita
OUT="$WS/patch/out"
MODSRC="$WS/analysis/modified/apktool"
PKG=com.kingosoft.activity_kb_common

BT=$(dirname "$(find "$SDK" -maxdepth 4 -name apksigner 2>/dev/null | head -1)")
AJAR=$(find "$SDK" -maxdepth 4 -name android.jar 2>/dev/null | head -1)
R8="${QX_R8:-/tmp/qx_build/r8.jar}"
[ -d "$TREE" ] || { echo "!! 解包树不存在: $TREE（先 apktool d base_flat.apk）"; exit 1; }
mkdir -p "$BUILD"

echo "== 1/7 首页布局插「觅Ta」按钮"
python3 "$WS/patch/patch_layout.py" "$TREE/res/layout/home_page_grid.xml"

echo "== 2/7 manifest：去壳桩 + 挂 provider"
python3 - "$TREE/AndroidManifest.xml" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
if 'com.nesun.stub.ZAP' in s:
    s = s.replace('android:name="com.nesun.stub.ZAP"',
                  'android:name="com.kingosoft.activity_kb_common.BaseApplication"')
    open(p, "w", encoding="utf-8").write(s)
    print("   application -> BaseApplication")
else:
    print("   application 已是业务 Application")
PY
python3 "$WS/patch/patch_manifest.py" "$TREE/AndroidManifest.xml" qx.Boot

echo "== 3/7 清掉壳层的 lib/资源"
rm -f "$TREE"/lib/*/libzprotect.so "$TREE"/assets/origin.apk "$TREE"/assets/libso.zip 2>/dev/null || true
ls "$TREE/assets/origin.apk" 2>/dev/null && echo "   !! assets/origin.apk 仍在" || echo "   已移除 libzprotect.so / assets/origin.apk"

echo "== 4/7 复用改版签名绕过 smali（bin/mt/signature + org/lsposed）"
if [ ! -d "$TREE/smali_classes6/bin/mt/signature" ]; then
  mkdir -p "$TREE/smali_classes6/bin/mt" "$TREE/smali_classes6/org"
  cp -R "$MODSRC/smali_classes3/bin/mt/signature" "$TREE/smali_classes6/bin/mt/"
  cp -R "$MODSRC/smali_classes3/org/lsposed" "$TREE/smali_classes6/org/"
fi
echo "   $(find "$TREE/smali_classes6" -name '*.smali' | wc -l | tr -d ' ') smali"

echo "== 5/7 编译注入 dex（qx/*）"
SRC="$BUILD/classes"; rm -rf "$SRC" "$BUILD/dex"; mkdir -p "$SRC" "$BUILD/dex"
javac -nowarn --release 8 -classpath "$AJAR" -d "$SRC" $(find "$WS/patch/src/qx" -name '*.java' | grep -v -e '/BootDump.java' -e '/Dumper.java' -e '/Smoke.java')
java -cp "$R8" com.android.tools.r8.D8 --min-api 21 --lib "$AJAR" --output "$BUILD/dex" $(find "$SRC" -name '*.class') \
  > "$BUILD/d8.log" 2>&1
mv "$BUILD/dex/classes.dex" "$BUILD/classes7.dex"
echo "   $(wc -c < "$BUILD/classes7.dex") bytes"

echo "== 6/7 apktool 回编（几万 smali，慢）"
apktool b "$TREE" -o "$BUILD/unsigned.apk" > "$BUILD/apktool-b.log" 2>&1

echo "== 7/7 塞注入 dex + 对齐 + 签名"
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
[ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -alias qx -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass qx123456 -keypass qx123456 -dname "CN=qx, OU=qx, O=qx, L=CN, S=CN, C=CN" >/dev/null 2>&1
mkdir -p "$OUT"
"$BT/zipalign" -f -p 4 "$BUILD/withdex.apk" "$BUILD/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:qx123456 --key-pass pass:qx123456 \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT/qx-454-mita.apk" "$BUILD/aligned.apk"
"$BT/apksigner" verify "$OUT/qx-454-mita.apk" | head -3
echo "== done: $OUT/qx-454-mita.apk $(wc -c < "$OUT/qx-454-mita.apk") bytes"
