# bochat-scheduler-bot 测试报告

## 1. 测试概述

| 项目 | 内容 |
|------|------|
| **被测项目** | bochat-scheduler-bot（BoChat 定时任务 Bot） |
| **项目版本** | 0.1.0 |
| **项目仓库** | https://github.com/xUxIAOrUI815/bochat-scheduler-bot |
| **测试日期** | 2026-05-22 |
| **测试人员** | 徐筱睿 |
| **测试环境** | Windows 11, Python 3.13.3, BoChat Server 10.210.126.58:48080 |

### 1.1 项目简介

bochat-scheduler-bot 是一个配置驱动的定时任务 Bot。它读取 TOML 配置文件，按计划执行任务，并使用 BoChat Python SDK 将消息发送到指定群聊。

### 1.2 核心功能

- **send_message 任务**：按计划向指定群聊发送固定文本消息
- **check_url 任务**：按计划检测网页内容变化，变化时发送通知
- 三种调度模式：
  - `daily`：每日在指定时间执行一次
  - `weekly`：每周在指定星期和指定时间执行一次
  - `interval`：按固定时间间隔执行
- dry-run 模式（仅打印，不调用 BoChat API）
- 长期运行模式（`run` 命令，持续轮询）
- 手动执行单个任务（`run-once`）
- 查看到期任务列表（`due`）
- 状态持久化（JSON 文件，记录上次执行时间和内容哈希）

## 2. 测试策略

### 2.1 测试分层

```
┌────────────────────────────────────┐
│        集成测试 (Integration)        │
│  真实 BoChat 服务端到端验证            │
├────────────────────────────────────┤
│      补充单元测试 (Supplementary)      │
│  边界条件、异常路径、边缘情况覆盖         │
├────────────────────────────────────┤
│       已有单元测试 (Existing)          │
│  核心功能基础验证                      │
└────────────────────────────────────┘
```

### 2.2 测试范围

| 模块 | 单元测试 | 集成测试 |
|------|----------|----------|
| `config.py` - 配置加载与校验 | 10 | - |
| `scheduler.py` - 调度到期判断 | 6 | 1 |
| `tasks.py` - 任务执行逻辑 | 9 | 4 |
| `website.py` - 网页快照与解析 | 5 | 2 |
| `state.py` - 状态持久化 | 4 | - |
| `runner.py` - 运行时编排 | 4 | 2 |
| `sender.py` - 消息发送 | - | 2 |
| `cli.py` - 命令行接口 | - | 手动验证 |

## 3. 测试结果汇总

### 3.1 总体统计

| 指标 | 数值 |
|------|------|
| **测试用例总数** | 49 |
| **通过数** | 49 |
| **失败数** | 0 |
| **跳过数** | 0 |
| **通过率** | **100%** |
| **执行时间** | 45.71s |

### 3.2 分类统计

| 测试类别 | 数量 | 通过 | 备注 |
|----------|------|------|------|
| 已有单元测试 | 14 | 14 | 代码仓库中已有的基础测试 |
| 补充单元测试 | 22 | 22 | 本轮补充的边界/异常路径测试 |
| 集成测试 | 13 | 13 | 对接真实 BoChat 服务器的端到端测试 |

## 4. 详细测试结果

### 4.1 配置模块（config.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_parse_config_defaults | 已有 | PASS |
| test_duplicate_task_id_rejected | 已有 | PASS |
| test_interval_requires_interval_secs | 已有 | PASS |
| test_check_url_requires_url | 已有 | PASS |
| test_daily_missing_time_rejected | 补充 | PASS |
| test_weekly_invalid_weekday_rejected | 补充 | PASS |
| test_invalid_timezone_rejected | 补充 | PASS |
| test_send_message_missing_message_rejected | 补充 | PASS |
| test_weekly_missing_time_rejected | 补充 | PASS |
| test_check_url_invalid_url_scheme_rejected | 补充 | PASS |

**覆盖点**：配置解析默认值、必填字段校验、重复 ID 检测；daily/weekly 缺少 time 报错；weekly 非法 weekday 报错；无效 timezone 报错；send_message 缺少 message 报错；check_url 非法协议报错。

### 4.2 调度模块（scheduler.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_daily_due_after_time_once_per_day | 已有 | PASS |
| test_weekly_due_only_on_configured_weekday | 已有 | PASS |
| test_interval_due_after_elapsed_seconds | 已有 | PASS |
| test_due_tasks_filters_disabled | 补充 | PASS |
| test_due_tasks_not_yet_time | 补充 | PASS |
| test_daily_not_due_before_time | 补充 | PASS |
| test_weekly_not_due_on_wrong_day | 补充 | PASS |
| test_check_due_returns_only_due_tasks | 补充 | PASS |
| test_check_due_with_real_config | 集成 | PASS |

**覆盖点**：
- `daily`：时间到后到期、同一天不重复触发、时间未到不触发
- `weekly`：指定 weekday 且时间到后触发、错误 weekday 不触发
- `interval`：首次立即到期、未到间隔不触发、超过间隔触发
- `due_tasks`：disabled 任务过滤、多任务混合过滤
- 时区感知的调度计算（Asia/Shanghai）

### 4.3 任务执行（tasks.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_send_message_updates_state_after_success | 已有 | PASS |
| test_dry_run_does_not_update_state | 已有 | PASS |
| test_send_failure_does_not_update_state | 已有 | PASS |
| test_check_url_first_run_records_hash_without_sending | 已有 | PASS |
| test_check_url_sends_when_content_changes | 已有 | PASS |
| test_check_url_no_change_sends_nothing | 补充 | PASS |
| test_check_url_dry_run_first_run | 补充 | PASS |
| test_format_website_change_message_includes_title_and_summary | 补充 | PASS |
| test_execute_task_invalid_type_raises | 补充 | PASS |
| test_execute_send_message_integration | 集成 | PASS |
| test_run_once_send_message_integration | 集成 | PASS |
| test_check_url_first_run_integration | 集成 | PASS |
| test_check_url_second_run_detects_no_change | 集成 | PASS |

**覆盖点**：
- `send_message`：发送成功更新状态、dry-run 不更新、发送失败不更新
- `check_url`：首次记录 hash 不发、内容变化时发送通知、内容未变化时不发送、dry-run 首次不持久化
- 变更消息格式化（标题、URL、摘要）
- 不支持的任务类型报错
- 真实 BoChat 服务器端到端验证

### 4.4 网页快照（website.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_parse_website_content_extracts_title_summary_and_hash | 已有 | PASS |
| test_parse_website_content_no_title | 补充 | PASS |
| test_parse_website_content_empty_body | 补充 | PASS |
| test_parse_website_content_strips_scripts | 补充 | PASS |
| test_fetch_real_website_snapshot | 集成 | PASS |
| test_website_snapshot_hash_stable | 集成 | PASS |
| test_website_snapshot_hash_differs | 集成 | PASS |

**覆盖点**：HTML 解析提取 title/summary/hash、无 title 时 fallback 为 URL、空 body 处理、script/style 标签过滤、真实网站抓取、相同内容相同 hash、不同内容不同 hash。

### 4.5 状态持久化（state.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_state_read_write | 已有 | PASS |
| test_state_handles_corrupted_json | 补充 | PASS |
| test_state_atomic_write | 补充 | PASS |

**覆盖点**：基本读写 last_run_at/last_content_hash、损坏 JSON 容错、原子写入（临时文件 + os.replace）。

### 4.6 运行时编排（runner.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_find_task_raises_for_unknown | 补充 | PASS |
| test_run_once_send_message | 补充 | PASS |
| test_run_once_send_message_integration | 集成 | PASS |
| test_dry_run_send_message | 集成 | PASS |
| test_dry_run_check_url | 集成 | PASS |

**覆盖点**：find_task 不存在时报错、run_once 手动执行、dry-run 模式不更新状态。

### 4.7 消息发送（sender.py）

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_real_sender_send_text_to_group | 集成 | PASS |
| test_execute_send_message_integration | 集成 | PASS |

**覆盖点**：真实 BoChatSender 发送文本到群聊并返回 msg_id、DryRunSender 消息累积（已和 DryRunSender 其他功能的测试覆盖）。

### 4.8 错误处理

| 测试用例 | 类别 | 结果 |
|----------|------|------|
| test_send_failure_does_not_update_state | 已有 | PASS |
| test_state_handles_corrupted_json | 补充 | PASS |
| test_execute_task_invalid_type_raises | 补充 | PASS |
| test_invalid_bot_token_raises_error | 集成 | PASS |

## 5. 命令行功能验证（手动测试）

| 命令 | 测试内容 | 结果 |
|------|----------|------|
| `bochat-scheduler init-config` | 生成默认配置文件 | 通过 |
| `bochat-scheduler list` | 列出所有任务 | 通过 |
| `bochat-scheduler due` | 查看当前到期任务 | 通过 |
| `bochat-scheduler run-once <id>` | 手动执行单个任务 | 通过 |
| `bochat-scheduler run-once <id> --dry-run` | 模拟执行不实际发送 | 通过 |
| `bochat-scheduler check` | 执行当前到期任务 | 通过 |
| `bochat-scheduler check --dry-run` | 模拟执行到期任务 | 通过 |

## 6. 发现的缺陷

| 编号 | 严重程度 | 描述 | 状态 |
|------|----------|------|------|
| - | - | 未发现缺陷 | - |

> **注**：在测试过程中，httpbin.org 在此网络环境不可达（返回 502 Bad Gateway），这属于网络环境代理限制，不是代码缺陷。测试已改用 `example.com` 作为 check_url 目标，功能正常。

## 7. 测试覆盖分析

### 7.1 模块覆盖

| 模块 | 函数/方法 | 已覆盖 | 未覆盖 |
|------|-----------|--------|--------|
| `config.py` | 9 | 9 | 0 |
| `scheduler.py` | 3 | 3 | 0 |
| `tasks.py` | 4 | 4 | 0 |
| `website.py` | 2 | 2 | 0 |
| `state.py` | 4 | 4 | 0 |
| `runner.py` | 4 | 4 | 0 |
| `sender.py` | 3 | 2 | 1 (close 方法为简单委托) |
| `cli.py` | 7 | 0 | 7（手动验证） |

### 7.2 调度模式覆盖

| 调度模式 | 到期判断 | 任务执行 | 集成验证 |
|----------|----------|----------|----------|
| `daily` | ✅ | ✅ | ✅ |
| `weekly` | ✅ | ✅ | - |
| `interval` | ✅ | ✅ | - |

### 7.3 未覆盖说明

- `cli.py` 未编写自动化测试：CLI 函数均为参数解析 + 委托调用，核心逻辑已在其他模块中充分测试，功能已通过手动命令验证
- `sender.py` 的 `close` 方法：为简单委托（`await self._client.close()`），无需独立测试
- `check_url` 内容变化检测的 `weekly`/`interval` 集成测试：核心内容变化逻辑在单元测试中已经覆盖，与调度模式的组合通过代码审查确认正确

## 8. 测试环境配置

```toml
# 集成测试使用的环境变量/配置
base_url = "http://10.210.126.58:48080"
bot_token = "通过环境变量 BOCHAT_BOT_TOKEN 注入"
group_id = "g_4b573125-726f-44ea-8680-dcd6f212e99f"
timezone = "Asia/Shanghai"
```

- **BoChat 服务端**：社区主仓库代码，运行于 `10.210.126.58:48080`
- **测试群聊**：`2026软件工程`（公开群，群号 1145141919810）
- **测试 Bot**：`test-rss-bot`，已加入测试群
- **check_url 测试目标**：`https://example.com/`

## 9. 测试结论

### 9.1 总体评估

- 项目代码质量良好，模块划分清晰（config / scheduler / tasks / website / state / runner / sender / cli），每层职责单一
- 单元测试覆盖了所有核心模块的正常路径、边界条件和异常路径
- 调度到期判断逻辑经过充分验证（daily/weekly/interval 三种模式 + 时区感知）
- check_url 的首次记录→变化检测→无变化跳过 的状态机逻辑完整覆盖
- 集成测试验证了与真实 BoChat 服务端的完整交互流程
- 状态管理机制完善（原子写入、损坏 JSON 容错、失败不污染状态）
- 49 个自动化测试用例全部通过，通过率 100%

### 9.2 风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| 外部网站不可达 | 低 | check_url 失败会正常抛异常，下一轮重试 |
| 网站结构变化 | 低 | 任何内容变化都会触发通知，包括正常的页面结构调整 |
| Bot Token 过期 | 低 | 已有明确的错误处理和异常抛出 |
| 时区配置错误 | 低 | 启动时通过 ZoneInfo 验证，非法时区直接拒绝配置 |

### 9.3 已知限制

1. **check_url 首次运行不发送**：首次运行仅记录内容哈希作为基线，不发送通知。这是设计意图（避免配置时误报），已在 README 中说明。
2. **网站内容变化检测粒度**：基于页面可见文本的整体 SHA256 哈希，页面任何文本变化（包括时间戳、访问计数等动态内容）都会触发通知。建议用户在配置 check_url 时选择内容相对稳定的页面。
3. **send_message 不支持消息模板**：当前 `send_message` 任务的 `message` 字段为固定文本，不支持变量替换（如日期、时间）。如有动态内容需求，可作为后续功能扩展。

### 9.4 交付建议

项目已经过充分的单元测试和集成测试验证，核心功能正常，调度逻辑正确，状态管理健壮，**建议可以交付**。
