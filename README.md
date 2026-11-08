# 大连沙河口 · 和风天气与变化提醒

坐标 **38.88, 121.53**。唯一数据源为 **QWeather（和风天气）**，不使用其他天气源或旧数据兜底。Python 3.10+，仅标准库，无需安装依赖。

## Secret 安全与首次配置

主人亲自在本 GitHub 仓库 **Settings → Secrets and variables → Actions** 填入 `QWEATHER_API_KEY` 与 `QWEATHER_API_HOST`。Host 使用和风控制台分配的专属 API 域名，不含协议或路径。请勿在聊天、代码、文件、日志、README、命令历史或提交中放入凭据值。程序仅从进程环境读取这两个变量，不读取 `.env`，不打印认证头、环境变量值、请求地址或原始错误响应，认证请求禁止重定向。

缺少任一变量时，脚本明确输出缺少的变量名，退出码为 **1**；根目录 `weather.json` 写入 `status: error`、检查时间及错误说明，相应字段标错并保留原成功时间；历史值仅作历史展示。不会调用其他来源，也不会将旧数据冒充新抓取结果。其他抓取错误同样写错误状态并退出 1。

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

六个接口按下述分层时段调用，互相独立合并。逐小时须有24条、逐日须有3条；任一字段失败保留该字段历史值及原成功时间，并在 `fields`、`layers` 标记错误，不把旧值视为新抓取。尚无历史值时保持缺失。和风未提供的阵风、降水概率保持未知，不当作 0。

`index.html` **只 fetch 根目录 `./weather.json`**，不读 `data/weather.json` 或独立提醒文件，不携带认证信息、不直接调用和风。立即加载且每 **10分钟**禁用缓存自动重拉，显示最后更新时间、来源、实况时间和刷新倒计时；超过3小时明确提示过旧。实况抓取失败会清空天气显示并显示原因；其他层失败仍展示成功实况和带独立时间标记的历史层。文件缺失、读取异常时明确警告。须通过 HTTP 服务打开，不能直接双击使用 `file://`。

也可在仓库 Settings → Pages 选择默认分支根目录发布，是否支持私有仓库取决于账号方案。

## 后台更新

工作流仍使用 `*/10 * * * *`，每10分钟启动脚本，**不会每轮调用全部六接口**。脚本按北京时间计算时段，并使用 `weather.json` 的 `layers.*.slot` 判断是否已尝试：

| 层 | 时段 | 仅调用的两个接口 |
|---|---|---|
| 快层 fast | 每10分钟 | 实况 `/v7/weather/now`、分钟降水 `/v7/minutely/5m` |
| 中层 medium | 每个自然小时首次运行 | 逐小时 `/v7/weather/24h`、空气质量 `/airquality/v1/current/{纬度}/{经度}` |
| 慢层 slow | 北京时间05:50、11:50、17:50、23:50后首次运行 | 逐日 `/v7/weather/3d`、生活指数 `/v7/indices/1d` |

调度延迟时在下一轮补当前时段，不追补已错过时段；首次启动或改坐标会建立三层基线（至多六接口）。同一时段重复执行、包括失败后重跑，都不重复请求该层；错误保留到下一时段再试。因此慢层失败不会导致每10分钟重试。`layers` 记录每层时段、检查时间、最后全部成功时间和失败字段；`fields` 进一步记录每个字段的成功时间和状态，部分成功也独立合并。快层更新绝不清空其他层。旧版本无分层元数据时首轮重新建立基线。

**用量计算（按每接口一次请求、无网络重试）：** 快层144×2=288次/天；中层24×2=48次/天；慢层4×2=8次/天，合计344次/天。30天 **10,320次**，31天 **10,664次**，约1万次/月。冷启动可额外增加至多6次，手动运行受同一时段去重；网络异常单次请求最多3次尝试，重试另计（极端全请求三次约31,992次/31天）。测试实际模拟31天的4464轮，断言各层请求量，而不是仅检查公式。

支持 Actions 页面手动运行和脚本/工作流推送触发；Secrets 仅注入抓取步骤，`GITHUB_TOKEN` 提交根目录天气文件和兼容提醒。任一字段失败会提交明确错误状态并使工作流标红。网页仍只读取根目录文件，每10分钟刷新并显示各层成功时间。提醒只采用成功且有效期内的实况、逐小时和分钟数据，不拿失败或过期预报产生新提醒。

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

## 大连生活数据站：频道整合

首页现为「天气 / 特价机票 / 招聘」三个频道，支持手机布局及 `#weather`、`#deals`、`#jobs` 直达链接。天气频道保留原有全部展示、立即刷新、10 分钟轮询、分层状态与过期提醒。**本次未修改 `weather.json`、`scripts/fetch_weather.py`、`.github/workflows/weather.yml` 或 `data/`**。上文“页面只读取 weather.json”特指天气频道；新增频道分别只读取自己的根目录 JSON，浏览器不抓取外站。

### 文件与免费数据源

| 路径 | 用途 |
|---|---|
| `index.html` | 原天气页面增加频道导航、独立频道容器与手机样式 |
| `life.js` | 新频道切换、读取、卡片、空状态、错误/历史状态；外部内容使用 textContent |
| `deals.json` | 大连出发参考起价、目的地、来源日期范围、购票深链及抓取状态 |
| `jobs.json` | 单位、岗位、学历、专业、截止说明、官方原文和岗位表链接 |
| `scripts/fetch_deals.py` | 春秋航空公开低价列表 `https://flights.ch.com/DLC-from.html`；仅读取原页面明确报价的大连出发航线 |
| `scripts/fetch_jobs.py` | 人社局 `https://rsj.dl.gov.cn/col/col4341/index.html`，国资委 `https://gzw.dl.gov.cn/` 的“通知公告”列表；读取招聘原文及 HTML/XLSX/XLS 岗位表 |
| `scripts/life_common.py` | 独立生活频道 IO、检查状态、原子写入与失败保留；不访问天气文件 |
| `scripts/life-requirements.txt` | 免费开源的 openpyxl / xlrd，用于 Excel 岗位表；静态网页无需安装依赖 |
| `.github/workflows/deals.yml` | 每天北京时间 06:25 检查机票，可手动运行 |
| `.github/workflows/jobs.yml` | 每周一北京时间 06:45 检查招聘，可手动运行 |
| `tests/test_life.py` | 出发地/深链/日期、岗位逐行筛选、合并格、失败保留与官方域名验证 |

不使用付费 API、账号、第三方收费抓取或新增 Secrets。GitHub Actions 是否可用仍受账号免费额度与仓库权限限制。新增工作流仅暂存对应的 `deals.json` / `jobs.json`，提交前 rebase，避免天气机器人并发提交造成覆盖；不会提交天气数据。定时只在默认分支生效，调度可能延迟。

### 数据语义与边界

- 两份 JSON 均含 `items`、`sources`、`status`、`updated_at`（最后完整成功时间）、`checked_at`（最近尝试）和 `message`。抓取失败保留旧条目及成功时间并标为 `error`；部分失败标为 `partial`，保留未重新核验条目并设置 `historical: true`。首次没有成功数据就保持空数组，绝不生成演示价格或虚构岗位。
- 机票为航空公司公开**起价**，不保证含税费或有余票。来源未公布出行日期时 `date_start/date_end` 为 null，卡片明确提示，绝不将抓取日期冒充出行日期。官网购票深链取自原页面，不构造无依据的订单链接。无法解析或出现验证页视为失败，保留旧数据。超过 48 小时提示历史信息。
- 招聘最多检查每个列表最近 30 篇招聘公告，排除标题中的拟聘公示、考试通知、编外及劳务派遣。只按**同一岗位行**的学历字段确认“大专/专科”；本科及以上不会因别的岗位允许大专而混入。“不限专业”只根据同岗位专业字段完整匹配，不按公告全文推断。保留原文学历条件（含全日制等），最终资格以原公告为准。
- 支持 HTML 合并格、XLS/XLSX 合并格。图片、PDF、Word 岗位表、多层复杂表头或正文散文要求无法可靠核验时不猜测，保留旧数据并给出部分失败说明，需到官方原文人工核对。截止时间仅提取报名语境的明确年月日说明；缺失时显示“原文未明确提取”，不将发布日期当截止日期。超过 8 天提示历史信息；旧招聘记录可能已截止，须核验原文。
- 初次开发环境的出站网络限制了上述数据源，仓库初始 JSON 记录真实失败检查、空条目和空成功时间。请在合入默认分支后运行两个 Actions 验证实际源站连通性；源站反爬、结构变更、无可识别岗位表也会明确标记异常，不用旧值伪装成功。

### 本地与 GitHub Pages 验证

仅打开页面无需安装依赖：

```sh
cd codex-sandbox
python3 -m http.server 8000 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8000/`，依次点三个频道；也可直达 `http://127.0.0.1:8000/#deals` 和 `http://127.0.0.1:8000/#jobs`。通过开发者工具切换 390px 手机宽度，检查导航、卡片及天气横向滚动表格。不能双击 `file://`，因为浏览器会限制 JSON fetch。

执行新增抓取（**不要为验证生活频道运行天气抓取脚本**）：

```sh
python3 -m venv work/venv
work/venv/bin/pip install -r scripts/life-requirements.txt
work/venv/bin/python scripts/fetch_deals.py
work/venv/bin/python scripts/fetch_jobs.py
work/venv/bin/python -m unittest discover -s tests -v
```

失败退出码为 1，但仍写入检查状态及保留旧数据。来源可访问时可在后台核验 JSON 报价、岗位行、深链与原文一致。模拟数据只存在测试夹具中，不写进公开 JSON。

提交进入默认分支后，在 **Settings → Pages → Deploy from a branch → main / (root)** 发布，访问 `https://pjq3243349811.github.io/codex-sandbox/`（前提为仓库已启用 Pages）。刷新并检查三个频道；在 Actions 手动运行“特价机票每日更新”与“招聘每周更新”，确认仅对应 JSON 改变。天气 Actions、Secrets 与分层调度沿用原配置。
