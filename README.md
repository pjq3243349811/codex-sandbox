# 大连沙河口天气抓取与变化提醒

坐标默认 **38.88, 121.53**。Python 3.10+，仅标准库，无需 pip 安装。`index.html` 只读取仓库 JSON，不直接请求天气接口，不持有任何认证信息。

## 电脑运行

```sh
git clone https://github.com/pjq3243349811/codex-sandbox.git
cd codex-sandbox
python3 scripts/fetch_weather.py
python3 -m http.server 8000
```

浏览器打开 `http://localhost:8000/`。不能直接双击 HTML 使用 `file://`，浏览器会限制 fetch。页面打开立即读取 `./data/weather.json` 和 `./data/alerts.json`，每 **10 分钟**带时间戳、禁用缓存重新拉取；显示最后更新时间、数据来源、倒计时和实况时间。后台数据或实况超过 **3 小时**会警告，文件缺失和读取失败会明确提示。前台刷新不触发天气抓取。也可在 GitHub Settings → Pages 中选择默认分支根目录发布（私有仓库能否使用 Pages 取决于账号方案）。

## 安卓 Termux

```sh
pkg update
pkg install python git
git clone https://github.com/pjq3243349811/codex-sandbox.git
cd codex-sandbox
python scripts/fetch_weather.py
python -m http.server 8000 --bind 127.0.0.1
```

用安卓浏览器打开 `http://127.0.0.1:8000/`。Termux 必须保持运行；安卓省电和后台限制可能中断本地定时任务，推荐让 Actions 承担稳定后台更新。

## 数据源与 Secret 安全

主人亲自在 GitHub 本仓库 **Settings → Secrets and variables → Actions → New repository secret** 中添加：

- `QWEATHER_API_KEY`：和风 API 密钥。
- `QWEATHER_API_HOST`：账号专属 API Host，使用账号控制台给出的 `re.qweatherapi.com` 域名（如有专属前缀须保留），不含 `https://`、路径或斜杠。

**不要在聊天中发送密钥，不要将密钥写到任何代码、文件、README、日志或提交中。** 本地运行时仅通过安全的进程环境注入这两个变量，不在命令行参数中传密钥，也不要创建 `.env` 文件。脚本不打印环境变量、请求头、接口错误详情或响应体。认证头禁止随重定向发送。

Secret 未填完整时自动使用免费免密钥 **Open-Meteo**；填完后下次 Actions 自动优先使用 **QWeather**，无需改代码。和风实况、24 小时和 3 天预报为核心；分钟降水、空气质量、生活指数按权限和覆盖尽力获取，可选接口不可用不会阻断核心预报。核心和风接口失败时也自动兜底。数据中 `source` 明确为 `qweather` 或 `open-meteo`，`fallback_reason` 和 `limitations` 解释降级情况。未知值为 `null`，页面显示“未知”，绝不当成 0。Open-Meteo 实况为模型估计，非本地气象站直接测量。

## 坐标与定时更新

临时修改坐标：

```sh
python3 scripts/fetch_weather.py --latitude 38.88 --longitude 121.53
```

长期修改脚本参数默认值或工作流运行参数；地点改到大连以外时，同时修改地点名称和页面标题。修改坐标后状态基线自动重置。也可用 `--data-dir` 指定输出目录。

Actions 工作流 `.github/workflows/weather.yml` 每小时 **UTC 第 17 分钟**运行一次（北京时间同为每小时第 17 分钟），并支持 Actions 页面“Run workflow”手动执行；脚本或工作流推送也触发一次验证。工作流使用 `GITHUB_TOKEN` 提交 `data/` 内输出，权限仅 `contents: write`，同一分支串行运行。需在仓库 Actions 设置允许工作流读写内容；分支保护若禁止机器人直推，需按仓库规则允许数据更新或改用单独数据分支。**定时工作流仅在默认分支生效**；GitHub 调度可能延迟，公开仓库长期无活动可能被自动停用。新增的脚本推送到分支也会执行一次，合入默认分支后开始定时运行。

电脑可用 `crontab -e`（换成自己的绝对仓库路径）：

```cron
17 * * * * cd /absolute/path/codex-sandbox && /usr/bin/python3 scripts/fetch_weather.py
```

Termux 可安装 `cronie`、启动 `crond`，在 `crontab -e` 中使用 Termux 的绝对仓库路径及 `command -v python` 得到的 Python 路径。不要把认证变量值写进 crontab；本地定时进程必须自行从安全环境获得变量，否则自然走免密钥兜底。同一个数据目录不要同时运行多个本地抓取进程。

## 提醒规则与 Muse 文件出口

每次成功抓取产生：

- `data/weather.json`：来源、坐标、检查时间、实况、24 小时、3 天预报及可用的扩展数据；温度 ℃、风速/阵风 km/h、降水 mm、概率 %。
- `data/state.json`：上次实况及风险档位、通知时间，用于去重，不含凭据。
- `data/alerts.json`：`checked_at`（北京时间 ISO）、`level`、`changes`、`text`。
- `data/latest_alert.txt`：可直接转发的中文播报文本。

未来 24 小时：降水概率 ≥60%、累计降水 ≥1 mm 或雨雪雷天气；风速 ≥39 km/h 或阵风 ≥50 km/h；较当前降温/升温 ≥8℃；天气转为雨雪雷雾时提醒。最近 6 小时内两次实况温差 ≥6℃也提醒。风险升档阈值包括降水概率 80%、累计降水 10 mm、雪/雷，风速 50/62 或阵风 62/75 km/h，温变按 4℃分档。风险首次出现或明显升档才播报；持续风险 24 小时后复核提醒；风险消失后再次出现可重新提醒。切换数据源时重建风险基线。已知风险未加剧时明确写 **“无重要变化”**，并不表示全天无风无雨。

**Muse 会定期读取 codex-sandbox 仓库里的 `data/latest_alert.txt` / `data/alerts.json`，有新提醒就转达给主人。** 这是已落地的文件出口，不新增推送服务。Muse 端需配置读取默认分支最新文件（私有仓库使用 Muse 已有的仓库访问能力）；以 `checked_at` 记录已处理检查，只在 `level=重要` 且 `changes` 非空时转达 `text`。正常检查同样覆盖两个提醒文件为“无重要变化”及本次检查时间，避免旧提醒残留。错误时写“检查失败，无法判断重要变化”，不伪称“无重要变化”；保留上次成功天气及状态，Actions 标红。可监控错误级别和检查时间，避免转发过期提醒。本项目未替 Muse 创建外部轮询任务。

首次运行没有历史基线，仍会报告当前预报中的重要风险；这是辅助提醒，不替代气象台预警。

## 验证

```sh
python3 -m unittest discover -s tests -v
python3 scripts/fetch_weather.py
```

自动化测试覆盖无变化、雨雪与温变、大风升档、重复去重、风险解除、和风可选接口失败及抓取失败覆盖旧提醒。接口请求有超时及最多三次重试；所有数据写入单文件原子替换。前端还检测提醒和天气的时间一致性。网络失败退出码为 1，成功为 0。
