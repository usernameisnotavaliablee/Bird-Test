#!/usr/bin/env bash
# 实机操作小工具：adb install / 拉脱壳产物 / 看日志
#   bash patch/device.sh install-dump | install-button | pull | log | uninstall
set -euo pipefail
WS=/Users/mac/Documents/喜鹊
PKG=com.kingosoft.activity_kb_common
OUT="$WS/patch/out"
ADB=${ADB:-adb}

case "${1:-}" in
  install-button) "$ADB" install -r "$OUT/qx-454-button.apk" ;;
  install-dump)   "$ADB" install -r "$OUT/qx-454-dump.apk" ;;
  uninstall)      "$ADB" uninstall "$PKG" || true ;;
  pull)
    DEST="$WS/analysis/captures/qxdump-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$DEST"
    "$ADB" pull "/sdcard/Android/data/$PKG/files/qxdump/." "$DEST" || true
    echo "-> $DEST"
    ls -la "$DEST" "$DEST/dex" 2>/dev/null | head -30
    ;;
  log) "$ADB" logcat -c; "$ADB" logcat | grep -Ei "qx|zprotect|ActivityManager.*$PKG" ;;
  *) sed -n '2,4p' "$0" ;;
esac
