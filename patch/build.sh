#!/usr/bin/env bash
# 喜鹊 · 最新版 2.6.454 觅Ta 注入构建
#   产物: patch/out/qx-454-<MODE>.apk
#   MODE=button  首页右上角「觅Ta」入口按钮 + 签名绕过（正式形态）
#   MODE=dump    同上 + 进程内脱壳 provider（开发形态，用来拿明文 dex）
#   环境变量 QX_NATIVE=1  额外塞 libSignatureKiller.so + assets/SignatureKiller/origin.apk
#                          （native 层 open() 重定向，Java 层伪造不够时用）
#
# 依赖: apktool / JDK21(javac,keytool) / build-tools(zipalign,apksigner,aapt2) / android.jar / r8(d8)
set -euo pipefail

WS=/Users/mac/Documents/喜鹊
MODE="${1:-button}"
SDK="${QX_SDK:-/tmp/qx_build/sdk2}"
BUILD="/tmp/qx_build/build-$MODE"
OUT="$WS/patch/out"
MODSRC="$WS/analysis/modified/apktool"     # 改版的 smali 树（复用 KillerApplication + HiddenApiBypass）
PKG=com.kingosoft.activity_kb_common

BT=$(dirname "$(find "$SDK" -maxdepth 4 -name apksigner 2>/dev/null | head -1)")
[ -n "$BT" ] && [ -x "$BT/apksigner" ] || { echo "!! build-tools not found under $SDK"; exit 1; }
AJAR=$(find "$SDK" -maxdepth 4 -name android.jar 2>/dev/null | head -1)
[ -n "$AJAR" ] || { echo "!! android.jar not found under $SDK"; exit 1; }
R8="${QX_R8:-/tmp/qx_build/r8.jar}"

echo "== mode=$MODE native=${QX_NATIVE:-0} build-tools=$BT"

# 1. 解包最新版（壳 APK 全明文：dex + res + manifest 均可改）
SHELL_DIR="$BUILD/shell"
if [ ! -d "$SHELL_DIR" ]; then
  mkdir -p "$BUILD"
  apktool d -f -o "$SHELL_DIR" "$WS/最新版.apk" > "$BUILD/apktool-d.log" 2>&1
fi

# 2. 复用改版的签名绕过类（bin/mt/signature + org/lsposed）作为 smali_classes3
if [ ! -d "$SHELL_DIR/smali_classes3/bin/mt/signature" ]; then
  mkdir -p "$SHELL_DIR/smali_classes3/bin/mt" "$SHELL_DIR/smali_classes3/org"
  cp -R "$MODSRC/smali_classes3/bin/mt/signature" "$SHELL_DIR/smali_classes3/bin/mt/"
  cp -R "$MODSRC/smali_classes3/org/lsposed" "$SHELL_DIR/smali_classes3/org/"
  echo "== killer smali copied: $(find "$SHELL_DIR/smali_classes3" -name '*.smali' | wc -l | tr -d ' ') files"
fi

# 3. 首页布局插按钮（幂等）
python3 "$WS/patch/patch_layout.py" "$SHELL_DIR/res/layout/home_page_grid.xml"

# 4. dump 版：脱壳 provider；button 版：只挂签名绕过的 provider
PROVIDER=qx.Boot
[ "$MODE" = "dump" ] && PROVIDER=qx.BootDump
python3 "$WS/patch/patch_manifest.py" "$SHELL_DIR/AndroidManifest.xml" "$PROVIDER"

# 5. 编译注入 dex（qx/*）
SRC="$BUILD/classes"
rm -rf "$SRC" && mkdir -p "$SRC"
FILES=$(find "$WS/patch/src/qx" -name '*.java')
if [ "$MODE" = "button" ]; then
  FILES=$(echo "$FILES" | grep -v -e '/BootDump.java' -e '/Dumper.java' -e '/Smoke.java')
fi
javac -nowarn --release 8 -classpath "$AJAR" -d "$SRC" $FILES
rm -rf "$BUILD/dex" && mkdir -p "$BUILD/dex"
java -cp "$R8" com.android.tools.r8.D8 --min-api 21 --lib "$AJAR" --output "$BUILD/dex" \
  $(find "$SRC" -name '*.class') > "$BUILD/d8.log" 2>&1
mv "$BUILD/dex/classes.dex" "$BUILD/classes4.dex"   # classes.dex/2 是壳，classes3 由 smali_classes3 汇编
echo "== injected dex $(wc -c < "$BUILD/classes4.dex") bytes"

# 6. 可选：native 层签名绕过（lib + 官方包副本）
if [ "${QX_NATIVE:-0}" = "1" ]; then
  for abi in arm64-v8a armeabi-v7a armeabi; do
    mkdir -p "$SHELL_DIR/lib/$abi"
    unzip -o -q -j "$WS/改版.apk" "lib/$abi/libSignatureKiller.so" -d "$SHELL_DIR/lib/$abi"
  done
  mkdir -p "$SHELL_DIR/assets/SignatureKiller"
  cp "$WS/最新版.apk" "$SHELL_DIR/assets/SignatureKiller/origin.apk"
  echo "== native killer added: $(ls "$SHELL_DIR/lib"/*/libSignatureKiller.so | wc -l | tr -d ' ') abi"
fi

# 7. 回编 + 塞注入 dex + 回填壳原 dex + 对齐 + 签名
apktool b "$SHELL_DIR" -o "$BUILD/unsigned.apk" > "$BUILD/apktool-b.log" 2>&1
python3 - "$BUILD/unsigned.apk" "$BUILD/classes4.dex" "$WS/最新版.apk" "$BUILD/withdex.apk" <<'PY'
import sys, zipfile, hashlib
src, dex, orig, dst = sys.argv[1:5]
zo = zipfile.ZipFile(orig)
keep = {n: zo.read(n) for n in ("classes.dex", "classes2.dex")}   # 壳自家 dex 保持逐字节原样
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
added = False
for it in zin.infolist():
    data = keep.pop(it.filename, None)
    zout.writestr(it, zin.read(it.filename) if data is None else data)
for n, data in keep.items():
    zout.writestr(n, data)
if "classes4.dex" not in zin.namelist():
    zout.write(dex, 'classes4.dex')
    added = True
zout.close(); zin.close()
z = zipfile.ZipFile(dst)
print("classes4.dex added:", added, "| entries:", len(z.infolist()),
      "| shell classes.dex identical:",
      hashlib.md5(z.read("classes.dex")).hexdigest() == hashlib.md5(zo.read("classes.dex")).hexdigest())
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
"$BT/apksigner" verify "$OUT/qx-454-$MODE.apk" | head -3
echo "== done: $OUT/qx-454-$MODE.apk $(wc -c < "$OUT/qx-454-$MODE.apk") bytes"
