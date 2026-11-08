# 飞途 · 静态机票查询与路线灵感

所有应用文件位于 `flights/`，仅新增一个独立的 Actions 工作流；不修改根目录首页、weather.json 或天气管线。无构建、无运行依赖、无后端，不使用付费服务。

## 打开

在仓库根目录运行 `python3 -m http.server 8000`，访问 http://localhost:8000/flights/ 。不要双击 HTML 使用 file://，浏览器会限制 JSON fetch。

GitHub Pages 使用仓库根目录发布后，访问 https://pjq3243349811.github.io/codex-sandbox/flights/ 。如尚未开启 Pages，在 Settings → Pages 选择含本次提交的分支、`/ (root)`；本任务不修改已有发布设置。代码提交到其他分支时需先合入 Pages 发布分支才会上线。

## 功能与价格口径

- 城市、机场名、拼音、IATA 三字码输入，原生 datalist 联想；交换起终点、日期校验、1–6 位成人、舱位。
- 价格、时长、性价比（价格/最低价格 + 时长/最短时长，等权）及直飞优先排序；航司、出发时段、直飞筛选。
- JSON 初始提供大连至贵阳、天水、昆明、北京的 16 条人工示例，**不代表任何真实班次、日期、库存或实时价格**。仅填经济舱，其他舱位如无记录显示空态，不伪造加价。
- 示例票价是单人单程；多人合计是简单参考计算。选择返程不会编造返程报价，站内仍只展示去程，Google Flights 深链带往返日期、人数与舱位检索文字。携程深链带航线、出发日期、人数与舱位。平台可能要求重新确认参数，最终以平台实际页面为准。
- 直飞、中转、飞机加高铁三个方案都是**路线灵感与时间估算**，未核验航班或高铁运行。偏好改变推荐顺序。总时长含候机/衔接；页面说明行李、机场至铁路站衔接、跨日日期调整，并提供分段购票入口。铁路使用12306官方入口，站点和日期由用户核验。
- 首都/大兴、双流/天府、虹桥/浦东视为独立机场；城市名默认选列表第一机场。

## 自动更新（可选，无需购买）

`flights/scripts/fetch-flights.mjs` 使用 Travelpayouts / Aviasales Data API 的缓存票价接口 `https://api.travelpayouts.com/aviasales/v3/prices_for_dates`。这不是实时查票 API。须自行具备该服务免费数据接口访问资格；本应用不购买服务、不自动注册。国内部分航线可能无数据。

在仓库 Settings → Secrets and variables → Actions 添加 `FLIGHT_API_KEY`（Travelpayouts API token）。不要把密钥写入文件或前端。`.github/workflows/flights-data.yml` 每日北京时间 07:20（UTC 23:20）运行，也可手动触发。GitHub 定时任务可能延迟，并只在默认分支运行。

本地验证：

```sh
node flights/scripts/fetch-flights.mjs  # 未设置密钥：退出码0，文件逐字不变
node --test flights/scripts/fetch-flights.test.mjs
```

脚本查询七天后大连出发的四条示例目的地航线，限定人民币、经济舱单程、直飞；API 返回记录须有真实日期、时长、正数票价及合法航班标识才会写入。中转报价缺乏完整机场信息，故不导入。任一请求失败、全为空或数据无效均保留旧数据及更新时间；网络失败退出码1。缺少密钥安全退出码0。成功写入为 `kind: cached`，前端标明缓存来源、北京时间更新时间，只展示匹配日期和舱位的记录。成功抓取后不会把示例与 API 数据混合；缓存价也不保证当前库存或含全部税费。

工作流仅提交 `flights/flights-data.json`，需 Actions 有 contents 写权限；分支保护可能阻止自动提交，请按仓库策略配置。已有天气 workflow 完全独立。

## 图片与动效

免费 Unsplash 远程照片：

- 飞机云海：https://images.unsplash.com/photo-1436491865332-7a61a109cc05
- 铁路风景：图片资源 ID：photo-1474487548417-781cb71495f3，https://images.unsplash.com/photo-1474487548417-781cb71495f3

照片通过 images.unsplash.com 加载，需浏览器能访问该域名；不可达时保留深蓝渐变。Ken Burns 呼吸、SVG 航线弧光，系统减少动态设置下停用动效；无外部字体或 JS 依赖。

## 人工验收

1. 默认大连→贵阳有4张示例卡，检查价格与来源标记；切换四种排序。
2. 航司、时段、直飞筛选和重置；切换商务舱应为空态。
3. 切换天水/昆明/北京、交换出发地，检查空态及深链参数。
4. 校验过去日期、返程早于出发，改变人数；打开携程和Google Flights核验参数。
5. 行程页签有3种方案，偏好改变顺序，查看衔接说明与分段购票链接。
6. 在390px、768px、1440px宽度检查，无横向溢出；键盘可访问，页签支持左右方向键及Home/End。
