# AGENTS.md — 会话续接入口

> 本文件是给后续会话/代理的**第一入口**。工作区详细规范见 `CLAUDE.md`。

## 断点续接（最重要）

**先读 `HANDOFF.md` 全文** —— 它是实时工作交接日志，含当前断点、已完成证据、恢复核查清单。
当前断点（2026-09-06 封存）：主线 = 「查他人接口响应解析面深挖」，恢复入口 = HANDOFF.md 末尾「恢复后核查清单」8 项 + 「终端重启前最终快照」节。

## 工作流约定（用户指定）

1. **每步操作追加记录到 `HANDOFF.md`**（时间戳、操作、文件、结论、下一步）。
2. **每次更改立即 `git commit`**（中文 message）；大的反编译产物被 `.gitignore` 排除时，只 commit HANDOFF/文档/脚本，产物路径记入 HANDOFF。
3. 并行深挖任务**拆给 subagents** 执行，避免主会话上下文爆炸 / API 超长报错。

## 工作区速览

- 三份 APK：`原版.apk`(2.6.452 加固) / `改版.apk`(2.6.435 签名绕过+觅Ta掏空+Log22A16D窃密) / `最新版.apk`(2.6.454 官方，觅Ta 已重构)
- 分析产物：`analysis/`（original/modified/latest/comparison/tools）——均被 gitignore，不入库
- 核心文档：`analysis/改版深度探索文档.md`、`analysis/改版差异分析报告.md`、`analysis/数据面与监控组件深挖.md`（若已建）
- 工具脚本：`analysis/tools/`（archive_diff / manifest_diff / repair_dex_header）

## 关键技术备忘

- 最新版业务代码在内嵌 `assets/origin.apk` 的 5 个 dex；反编译必须用 **`analysis/latest/origin_repaired_nomap/`**（map-list 置零变体），用 `origin_repaired` 会让 jadx `BufferUnderflowException` 全空。
- jadx 参数：`jadx -d <out> --show-bad-code --no-res <dex>`。
- 觅Ta 旧 4 类（TeaInfoActivity/TdkbActivity/MitaNewActivity/MitaNewListActivity）在最新版已被官方删除。
- 三层口径分开论证：**展示面 / 解析面（Bean 字段集，Gson 反射不写 getter）/ 下发面**。
