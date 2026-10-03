#!/usr/bin/env bash
# 喜鹊 · 最新版 2.6.454 觅Ta 注入构建
#   产物: patch/out/qx-454-<MODE>.apk
#   MODE=button  只加首页右上角「觅Ta」入口按钮（正式版形态）
#   MODE=dump    button + 进程内脱壳 provider（开发版，用来拿明文 dex）
#
# 依赖: apktool / JDK21(javac,keytool) / Android build-tools(d8,zipalign,apksigner) / platform android.jar
set -euo pipefail

WS=/Users/mac/Documents/喜鹊
MODE="${1:-button}"
SDK="${QX_SDK:-/tmp/qx_build/sdk2}"
BUILD="/tmp/qx_build/build-$MODE"
OUT="$WS/patch/out"
CACHE="/tmp/qx_build"
PKG=com.kingosoft.activity_kb_common

BT=$(dirname "$(find "$SDK" -maxdepth 4 -name apksigner 2>/dev/null | head -1)")
[ -n "$BT" ] && [ -x "$BT/apksigner" ] || { echo "!! build-tools not found under $SDK"; exit 1; }
AJAR=$(find "$SDK" -maxdepth 4 -name android.jar 2>/dev/null | head -1)
[ -n "$AJAR" ] || { echo "!! android.jar not found under $SDK"; exit 1; }

echo "== mode=$MODE build-tools=$BT android.jar=$AJAR"

# 1. 解包最新版（壳 APK 全明文：dex + res + manifest 均可改）
SHELL_DIR="$BUILD/shell"
if [ ! -d "$SHELL_DIR" ]; then
  mkdir -p "$BUILD"
  apktool d -f -o "$SHELL_DIR" "$WS/最新版.apk" > "$BUILD/apktool-d.log" 2>&1
fi

# 2. 首页布局插按钮（幂等）
python3 "$WS/patch/patch_layout.py" "$SHELL_DIR/res/layout/home_page_grid.xml"

# 3. 编译注入 dex
SRC="$BUILD/classes"
rm -rf "$SRC" && mkdir -p "$SRC"
FILES=$(find "$WS/patch/src" -name '*.java')
if [ "$MODE" = "button" ]; then
  FILES=$(echo "$FILES" | grep -v -e '/Boot.java' -e '/Dumper.java')
fi
javac -nowarn --release 8 -classpath "$AJAR" -d "$SRC" $FILES
rm -rf "$BUILD/dex" && mkdir -p "$BUILD/dex"
# build-tools 33 自带的 d8 在 JDK21 上 NPE，改用 Google Maven 的最新 r8
R8="${QX_R8:-/tmp/qx_build/r8.jar}"
java -cp "$R8" com.android.tools.r8.D8 --min-api 21 --lib "$AJAR" --output "$BUILD/dex" \
  $(find "$SRC" -name '*.class') > "$BUILD/d8.log" 2>&1
mv "$BUILD/dex/classes.dex" "$BUILD/classes3.dex"
echo "== classes3.dex $(wc -c < "$BUILD/classes3.dex") bytes"

# 4. dump 模式：加 provider 声明（幂等）
if [ "$MODE" = "dump" ]; then
  python3 "$WS/patch/patch_manifest.py" "$SHELL_DIR/AndroidManifest.xml"
fi

# 5. 回编 + 塞 dex + 对齐 + 签名
apktool b "$SHELL_DIR" -o "$BUILD/unsigned.apk" > "$BUILD/apktool-b.log" 2>&1
python3 - "$BUILD/unsigned.apk" "$BUILD/classes3.dex" "$WS/最新版.apk" "$BUILD/withdex.apk" <<'PY'
import sys, zipfile, hashlib
src, dex, orig, dst = sys.argv[1:5]
zo = zipfile.ZipFile(orig)
keep = {n: zo.read(n) for n in ("classes.dex", "classes2.dex")}   # 壳自家 dex 保持逐字节原样，别吃 smali 往返
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    data = keep.pop(it.filename, None)
    zout.writestr(it, zin.read(it.filename) if data is None else data)
for n, data in keep.items():
    zout.writestr(n, data)
zout.write(dex, 'classes3.dex')
zout.close(); zin.close()
for n, data in [("classes.dex", zipfile.ZipFile(orig).read("classes.dex"))]:
    got = zipfile.ZipFile(dst).read(n)
    print("shell dex %s identical: %s" % (n, hashlib.md5(got).hexdigest() == hashlib.md5(data).hexdigest()))
print("withdex.apk entries:", len(zipfile.ZipFile(dst).infolist()))
PY

KS="$WS/patch/qx.keystore"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias qx -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass qx123456 -keypass qx123456 -dname "CN=qx, OU=qx, O=qx, L=CN, S=CN, C=CN" >/dev/null 2>&1
fi
mkdir -p "$OUT"
"$BT/zipalign" -f -p 4 "$BUILD/withdex.apk" "$BUILD/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:qx123456 --key-pass pass:qx123456 \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT/qx-454-$MODE.apk" "$BUILD/aligned.apk"
"$BT/apksigner" verify --print-certs "$OUT/qx-454-$MODE.apk" | head -5
echo "== done: $OUT/qx-454-$MODE.apk $(wc -c < "$OUT/qx-454-$MODE.apk") bytes"
