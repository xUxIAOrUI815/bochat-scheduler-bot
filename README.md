# BoChat Scheduler Bot

BoChat Scheduler Bot 是一个社区版定时任务 Bot。它读取 TOML 配置文件，按计划执行任务，并使用 BoChat Python SDK 将消息发送到指定群聊。

MVP 支持两类任务：

- `send_message`：按计划发送固定文本。
- `check_url`：按计划检查网页内容是否变化，变化时发送通知。

## 安装

开发时先安装 BoChat 主仓库里的 Python SDK：

```bash
python -m pip install -e E:/bochat/python-sdk
```

然后安装本工具：

```bash
cd E:/bochat-scheduler-bot
python -m pip install -e ".[dev]"
```

## 配置

生成示例配置：

```bash
bochat-scheduler init-config ./config.toml
```

示例：

```toml
base_url = "http://127.0.0.1:8080"
bot_token = "b_xxx:1710000000:signature"
state_path = "./scheduler_state.json"
timezone = "Asia/Shanghai"

[[tasks]]
id = "daily-hello"
type = "send_message"
enabled = true
group_id = "g_xxx"
schedule = "daily"
time = "09:00"
message = "早上好，今天也要继续推进任务。"

[[tasks]]
id = "weekly-site-check"
type = "check_url"
enabled = true
group_id = "g_xxx"
schedule = "weekly"
weekday = "monday"
time = "10:00"
url = "https://example.com/news"
title = "Example News"
```

`bot_token` 来自 BoChat Bot 列表接口。`group_id` 是目标群 ID，且该 Bot 必须已加入目标群。

## 使用

列出任务：

```bash
bochat-scheduler list --config config.toml
```

查看当前到期任务：

```bash
bochat-scheduler due --config config.toml
```

手动执行某个任务：

```bash
bochat-scheduler run-once daily-hello --config config.toml
```

执行当前到期任务：

```bash
bochat-scheduler check --config config.toml
```

长期运行：

```bash
bochat-scheduler run --config config.toml
```

只打印将发送内容，不调用 BoChat：

```bash
bochat-scheduler run-once daily-hello --config config.toml --dry-run
```

## 调度规则

- `daily`：当前日期到达 `time` 后执行，当天只执行一次。
- `weekly`：当前星期等于 `weekday` 且到达 `time` 后执行，当周只执行一次。
- `interval`：距离上次执行超过 `interval_secs` 后执行；从未执行过则立即到期。

## 状态文件

工具使用 `state_path` 指定的 JSON 文件保存任务状态：

- `last_run_at`：上次成功执行时间。
- `last_content_hash`：`check_url` 上次检测到的网站内容 hash。

`check_url` 首次运行只记录内容 hash，不发送通知，避免第一次配置时误报。

不要提交真实 `config.toml`、`.env` 或 `scheduler_state.json`。

## 作为 BoChat 主仓库 submodule

本工具作为独立社区仓库维护。BoChat 主仓库中应以 submodule 形式挂载：

```bash
git submodule add https://github.com/xUxIAOrUI815/bochat-scheduler-bot.git community/bochat-scheduler-bot
```

如果你没有 BoChat 主仓库写权限，可以在本仓库完成开发并推送后，让有权限的维护者在主仓库添加 submodule。
