# 大连沙河口 · 和风天气与变化提醒

坐标 **38.88, 121.53**。唯一数据源为 **QWeather（和风天气）**，不使用其他天气源或旧数据兜底。Python 3.10+，仅标准库，无需安装依赖。

## Secret 安全与首次配置

主人亲自在本 GitHub 仓库 **Settings → Secrets and variables → Actions** 填入 `QWEATHER_API_KEY` 与 `QWEATHER_API_HOST`。Host 使用和风控制台分配的专属 API 域名，不含协议或路径。请勿在聊天、代码、文件、日志、README、命令历史或提交中放入凭据值。程序仅从进程环境读取这两个变量，不读取 `.env`，不打印认证头、环境变量值、请求地址或原始错误响应，认证请求禁止重定向。

缺少任一变量时，脚本明确输出缺少的变量名，退出码为 **1**；根目录 `weather.json` 写入 `status: error`、检查时间及错误说明，`updated_at: null`、天气数据清空。不会调用其他来源，也不会将旧数据冒充新抓取结果。其他抓取错误同样写错误状态并退出 1。

## 运行与修改坐标

在本仓库目录执行（本地进程的环境变量应由自己的安全环境配置注入，勿创建凭据文件）：

```sh
python3 scripts/fetch_weather.py
python3 -m http.server 8000 --bind 127.0.0.1
```

浏览器打开 `http://127.0.0.1:8000/`。安卓 Termux 先执行 `pkg install python git`，进入仓库后用同样命令运行。安卓后台省电可能停止任务，持续更新建议使用 GitHub Actions。

临时修改坐标：

```sh
python3 scripts/fetch_weather.py --latitude 38.88 --longitude 121.53
```

长期修改脚本默认参数或工作流运行参数。改到其他地区还需修改地点名称和网页标题。坐标变化会重置去重基线。`--data-dir` 仅指定内部状态和兼容提醒目录，天气始终写入仓库根目录 `weather.json`。

## 输出与网页

- **`weather.json`**：唯一网页数据文件，含 `source: qweather`、`status`、最后成功抓取时间 `updated_at`、实况 `current`、24小时 `hourly`、3天 `daily`、分钟降水 `minute`、空气质量 `air`、生活指数 `indices`、中文风险摘要 `alert_text` 及去重提醒 `alerts`。
- `data/state.json`：风险档位和已通知时间，仅作为内部比较基线，不用于网页展示。
- `data/alerts.json` / `data/latest_alert.txt`：兼容原 Muse 文件出口，每次检查覆盖，失败时明确报错。

核心实况、逐小时、逐日接口必须成功且预报完整；生活指数、分钟降水和空气质量每次均尝试抓取，权限或区域不支持时标为 `null`，并在 `limitations` 明确说明。和风未提供的阵风、降水概率保持未知，不当作 0。

`index.html` **只 fetch 根目录 `./weather.json`**，不读 `data/weather.json` 或独立提醒文件，不携带认证信息、不直接调用和风。立即加载且每 **10分钟**禁用缓存自动重拉，显示最后更新时间、来源、实况时间和刷新倒计时；超过3小时明确提示过旧。后端错误状态会清空旧显示并显示原因。文件缺失、读取异常时明确警告。须通过 HTTP 服务打开，不能直接双击使用 `file://`。

也可在仓库 Settings → Pages 选择默认分支根目录发布，是否支持私有仓库取决于账号方案。

## 后台更新

`.github/workflows/weather.yml` 每 **10分钟**运行一次（cron：`*/10 * * * *`），支持 Actions 页面手动 Run workflow；脚本和工作流推送也触发。Secrets 仅注入抓取步骤，`GITHUB_TOKEN` 以 `contents: write` 权限提交根目录 `weather.json` 和 `data/` 中的更新。缺少 Secret 或抓取失败时仍提交错误状态，并将工作流标红。

定时仅对默认分支生效，GitHub 调度可能延迟。仓库需允许 Actions 运行和机器人写入；分支保护若限制直接提交，需按仓库规则允许数据更新。

电脑可 `crontab -e` 配置（替换路径；不要将凭据值写进 crontab）：

```cron
*/10 * * * * cd /absolute/path/codex-sandbox && /usr/bin/python3 scripts/fetch_weather.py
```

Termux 可安装 cronie 并运行 crond，使用实际仓库和 Python 绝对路径。定时进程必须从安全环境获得变量。同一个目录不要并行运行多个本地抓取进程。

## 中文提醒与 Muse

`weather.json` 的 **`alert_text` 是当前风险摘要**：实况或未来24小时出现雨雪雷、降水概率≥60%或累计降水≥1mm；风速≥39km/h或阵风≥50km/h；未来24小时较当前降温/升温≥8℃；天气转为雨雪雷雾时生成中文提醒。最近6小时的两次实况温差≥6℃也生成变化提醒。没有风险则为“无提醒”；抓取失败则明确写无法判断，绝不伪称无提醒。

`alerts` 和兼容文件保留原来的新变化去重逻辑：新风险或升档才通知，持续风险24小时后复核，未加剧时明确“无重要变化”。`alert_text` 与去重通知用途不同：同一风险持续时前者仍展示风险，后者可能无新通知。

Muse 后续可读取根目录 `weather.json` 的 `alert_text`；原有出口 `data/latest_alert.txt` / `data/alerts.json` 继续可用。按检查时间去重，只有抓取成功且有提醒时转达；错误状态不得转发成天气提醒。本仓库没有新增付费推送服务，也没有替 Muse 建立外部轮询任务。

## 验证

```sh
python3 -m unittest discover -s tests -v
python3 scripts/fetch_weather.py
```

测试使用天气响应模拟数据，不需要任何认证值；覆盖提醒、去重、升档、扩展接口不可用和缺少环境变量时的错误输出。真实抓取必须由主人配置 Secrets 后在 Actions 运行验证。
