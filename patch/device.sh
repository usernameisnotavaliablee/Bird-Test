#!/usr/bin/env bash
# 实机操作小工具：adb install / 拉脱壳产物 / 看日志 / 起探测弹窗
#   bash patch/device.sh install-probe | install-mita | install-dump | install-button
#                       pull | log | probe | uninstall
set -euo pipefail
WS=/Users/mac/Documents/喜鹊
PKG=com.kingosoft.activity_kb_common
OUT="$WS/patch/out"
ADB=${ADB:-adb}

case "${1:-}" in
  install-button) "$ADB" install -r "$OUT/qx-454-button.apk" ;;
  install-dump)   "$ADB" install -r "$OUT/qx-454-dump.apk" ;;
  install-mita)   "$ADB" install -r "$OUT/qx-454-mita.apk" ;;
  install-probe)  "$ADB" install -r "$OUT/qx-454-probe.apk" ;;
  uninstall)      "$ADB" uninstall "$PKG" || true ;;
  # 单机验证弹窗（无需登录）：直接拉起 qx.ProbeActivity，塞一组假目标身份
  probe)
    "$ADB" root >/dev/null 2>&1 || true
    sleep 2
    "$ADB" shell am start -n "$PKG/qx.ProbeActivity" \
      --es qx_host TdkbActivity --es qx_name 测试同学 --es qx_xb 男 \
      --es qx_bjmc 测试班 --es qx_jid "${2:-10475_12345}" --es qx_uuid "${2:-10475_12345}" --es qx_type STU
    ;;
  pull)
    DEST="$WS/analysis/captures/qxdump-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$DEST"
    "$ADB" pull "/sdcard/Android/data/$PKG/files/qxdump/." "$DEST" || true
    echo "-> $DEST"
    ls -la "$DEST" "$DEST/dex" 2>/dev/null | head -30
    ;;
  log) "$ADB" logcat -c; "$ADB" logcat | grep -Ei "qx|zprotect|ActivityManager.*$PKG" ;;
  *) sed -n '2,5p' "$0" ;;
esac
