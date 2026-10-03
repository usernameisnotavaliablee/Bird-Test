# patch/ — 最新版 2.6.454 觅Ta 注入

在官方加固包 2.6.454 上做两件事：**首页右上角加「觅Ta」入口按钮**（正式形态），以及**进程内脱壳拿明文 dex**（开发形态，为掏门禁做准备）。

## 构建

```bash
QX_SDK=/tmp/qx_build/sdk2 bash patch/build.sh button   # -> patch/out/qx-454-button.apk
QX_SDK=/tmp/qx_build/sdk2 bash patch/build.sh dump     # -> patch/out/qx-454-dump.apk
```

依赖：

| 组件 | 位置 / 来源 |
|---|---|
| apktool 3.0.3 | `/opt/homebrew/bin/apktool` |
| JDK 21（javac/keytool） | 系统 |
| build-tools 33.0.2（zipalign/apksigner/aapt2） | `/tmp/qx_build/sdk2/bt/android-13` |
| platform android-33（android.jar） | `/tmp/qx_build/sdk2/pf/android-13` |
| d8 | Google Maven `r8-9.4.28.jar` → `/tmp/qx_build/r8.jar`（build-tools 自带的 d8 在 JDK21 上 NPE） |

`/tmp/qx_build` 会被系统清理；重建方式见 HANDOFF 2026-10-03 节（直下 `build-tools_r33.0.2-macosx.zip` 与 `platform-33-ext3_r03.zip`，sdkmanager 拉不到 manifest）。

## 结构

- `src/qx/MitaEntry.java` — 首页标题栏按钮（`res/layout/home_page_grid.xml` 里直接 new 出来）
- `src/qx/Boot.java` — 开发用 ContentProvider，启动 25s 后触发脱壳
- `src/qx/Dumper.java` — 搬 `.zprotect/**` + 扫 `/proc/self/mem` 里的明文 dex → `/sdcard/Android/data/<pkg>/files/qxdump/`
- `patch_layout.py` / `patch_manifest.py` — 幂等改 apktool 解包树
- `build.sh` — 全流程；`qx.keystore`（storepass/keypass `qx123456`）为一次性自签测试密钥，入库以保证后续版本可增量覆盖安装

## 注意

- 签名与官方不同 → 首次安装必须先卸载官方 454。
- 构建会**回填原始 `classes.dex`/`classes2.dex` 字节**，只新增 `classes3.dex`，把对壳的扰动压到最小。
- 资源 ID 重编前后逐项一致（17,454/17,454），payload dex 里的 R 常量不会错位。
- 产物在 `patch/out/`（gitignore）。
