# 云函数总览 — 2026-05-29

## 全部云函数（按功能分类）

| 函数名 | 运行时 | 触发逻辑 | 核心功能 |
|--------|--------|----------|----------|
| `cb_snapshot_updater` | Node.js | **每天 15:10**（周一至周五） | 从新浪财经获取全量可转债当日行情，入库 bond_snapshot 表；检测新增/退市转债 |
| `cb_volume_filter` | Python3.10 | **每天 15:50（周一至周五）** | 筛选当日成交额 ≥ 前5日均值×2的可转债，按剩余规模升序，推送飞书 |
| `cb_oversold_detector` | Node.js | **每天 15:30（周一至周五）** | 计算CCI+WR双超卖指标（基于日K线），筛选CCI<-100且WR>80的可转债，推送飞书 |
| `cb_weekly_kline_mootdx` | Python3.10 | **每周五 16:00**（定时） | 通过mootdx获取全量可转债周线数据，upsert进bond_weekly_kline表 |
| `mootdx-test` | Python3.10 | **HTTP触发器**（手动） | 飞书机器人回调验证URL + 菜单点击事件处理 + mootdx行情查询测试 |
| `cb_oversold_detector_weekly` | Node.js | **每天 15:40（周一至周五）** | 基于周K线计算CCI+WR双超卖指标（与日频版互为补充），筛选双超卖可转债，推送飞书 |
| `cb_weekly_kline_init` | Node.js | **手动触发**（一次性） | 可转债周线数据初始化：建bond_weekly_kline表 + 全量历史日线聚合成周线入库 |
| `sina_bonds_detail_collector` | Node.js | **手动触发**（增量） | 从新浪财经采集可转债详细信息（如转债条款、评级等），入库bond_detail |
| `sina_stock_info_collector` | Python | **手动触发**（待确认） | 从新浪财经采集正股相关信息 |
| `sina_bonds_info_collector` | Python | **手动触发**（待确认） | 从新浪财经采集可转债基础信息 |

---

## 核心函数详解

### 1. cb_snapshot_updater（行情快照更新）

```json
{ "name": "cb_snapshot_updater", "runtime": "Node.js", "timeout": 300 }
```

- **触发**：每周一到周五 15:10（收盘后10分钟）
- **数据源**：新浪财经行情接口
- **目标表**：`bond_snapshot`（每日行情）、`bond_list`（转债列表）、`bond_detail`（转债详情）
- **逻辑**：
  1. 分页抓取全量可转债当日行情
  2. UPSERT 到 bond_snapshot
  3. 增量更新 bond_list（新增/退市标记 is_active=0/1）
  4. 检测新转债自动采集详情到 bond_detail
  5. 过滤"定01"可交换债，避免无效数据
- **推送**：完成后飞书通知（成功/失败）

### 2. cb_volume_filter（成交额异动筛选）

```json
{ "name": "cb_volume_filter", "runtime": "Python3.10", "timeout": 300, "memorySize": 512, "layers": ["pymysql:v4"] }
```

- **触发**：每天 15:50（收盘前10分钟）
- **数据源**：bond_snapshot（MySQL）
- **策略**：
  1. 获取最近6个交易日（含今天）
  2. 计算每只转债前5日日均成交额
  3. 筛选当日成交额 ≥ 日均×2 的转债
  4. 按剩余规模（latest_amount）升序排列
- **返回字段**：转债名称、债券代码、行业、到期日、剩余规模、最新价、成交额（亿元）
- **推送**：飞书卡片消息

### 3. cb_oversold_detector（CCI+WR 双超卖检测）

```json
{ "name": "cb_oversold_detector", "runtime": "Node.js", "timeout": 300, "memorySize": 512 }
```

- **触发**：每天 15:30（周一至周五，收盘后）
- **数据源**：`bond_kline`（历史截至2026-05-20）+ `bond_snapshot`（2026-05-21起）
- **指标计算**：
  - CCI(14) = (TYP - MA(TYP, 14)) / (0.015 × AVEDEV(TYP, 14))
  - WR(14) = (HHV(HIGH, 14) - CLOSE) / (HHV(HIGH, 14) - LLV(LOW, 14)) × 100
- **超卖条件**：CCI < -100 且 WR > 80
- **返回字段**：转债名称、行业、剩余规模、到期日、现价、CCI值、WR值
- **重试机制**：对 CynosDB 偶发 `ER_MALFORMED_PACKET`（errno 1835）等瞬态错误自动重试 2 次（1s / 2s 退避）
- **推送**：飞书卡片消息
- **典型结果**：330 只活跃转债，处理约 320 只，失败约 10 只（数据不足），双超卖约 100~140 只

### 4. cb_weekly_kline_mootdx（周线数据采集）

```json
{ "name": "cb_weekly_kline_mootdx", "runtime": "Python3.10", "timeout": 600, "memorySize": 512, "layers": ["mootdx310:v1"] }
```

- **触发**：每周五 16:00（收盘后）
- **数据源**：mootdx（通达信协议）
- **目标表**：`bond_weekly_kline`
- **模式**（通过 event 参数区分）：
  - `init`：手动触发一次，获取全量历史周线
  - `weekly`：定时触发，获取最近30交易日日线聚合为周线
  - `daily`：备用模式，从 bond_kline + bond_snapshot 聚合
- **字段**：周开/高/低/收、成交量、成交额、来源标记

### 5. mootdx-test（飞书机器人回调）

```json
{ "name": "mootdx-test", "runtime": "Python3.10", "timeout": 60, "layers": ["mootdx310:v1"] }
```

- **触发**：HTTP调用（公网 URL `/test`）
- **功能**：
  1. **URL验证**：响应飞书 `type=url_verification` 的 challenge
  2. **菜单回调**：处理 `application.bot.menu_v6` 事件
  3. **行情查询**：点击菜单时调用 mootdx 查询指定债券行情
- **注意**：package.json 中 `"main": "index.js"` 与实际 Python 代码不符，应为 `index.py`

### 6. cb_oversold_detector_weekly（周K线双超卖检测）

```json
{ "name": "cb_oversold_detector_weekly", "runtime": "Node.js", "timeout": 300, "dependencies": { "mysql2": "^3.6.0" } }
```

- **触发**：每天 15:40（周一至周五，定时）
- **数据源**：`bond_weekly_kline`（周线数据）
- **SQL 列名修复**：表列为 `high_price / low_price / close_price`，代码中用 `AS high / AS low / AS close` 别名映射（2026-05-29 修复此前 `COALESCE(high_price, high)` 引用不存在列导致的 `Unknown column 'high'` 错误）
- **指标**：与日频版相同（CCI + WR），但基于周K线计算
  - CCI(14) = (TYP - MA(TYP, 14)) / (0.015 × AVEDEV(TYP, 14))
  - WR(14) = (HHV(HIGH, 14) - CLOSE) / (HHV(HIGH, 14) - LLV(LOW, 14)) × 100
- **超卖条件**：CCI < -100 且 WR > 80
- **重试机制**：同 `cb_oversold_detector`，对 CynosDB 瞬态错误自动重试 2 次
- **推送**：飞书卡片消息
- **典型结果**：330 只活跃转债，处理约 320 只，失败约 10 只（数据不足14周），双超卖约 100~110 只

### 7. cb_weekly_kline_init（周线数据初始化）

```json
{ "name": "cb_weekly_kline_init", "runtime": "Node.js", "dependencies": { "mysql2": "^3.6.0" } }
```

- **触发**：手动一次性触发
- **功能**：
  1. 创建 `bond_weekly_kline` 表（如不存在）
  2. 从 `bond_kline` 历史日线数据聚合生成全量周线
  3. UPSERT 入库
- **用途**：首次建立周线数据集，与 `cb_weekly_kline_mootdx` 的 `init` 模式互为替代方案

### 8. sina_bonds_detail_collector（新浪债券详情采集）

```json
{ "name": "sina_bonds_detail_collector", "runtime": "Node.js", "dependencies": { "mysql2": "3.6.0" } }
```

- **触发**：手动触发（增量）
- **数据源**：新浪财经债券详情接口
- **目标表**：`bond_detail`
- **逻辑**：批量采集可转债详细信息（如条款、评级、规模等），支持增量更新

### 9. sina_bonds_info_collector / sina_stock_info_collector

- **运行时**：Python
- **触发**：手动触发（待确认具体触发方式）
- **数据源**：新浪财经
- **依赖**：`pymysql`、`db_config`（云端可能有共享配置）
- **注意**：两个函数均引用 `from db_config import DB_CONFIG`，但本地代码中 `db_config.py` 未随 zip 下载，云端可能通过环境变量或共享层提供

---

## 数据库表结构

| 表名 | 用途 | 主要字段 |
|------|------|----------|
| `bond_list` | 可转债基础列表 | bond_code, bond_name, market, is_active, created_at, updated_at |
| `bond_static` | 可转债静态信息 | bond_code, maturity_date, remaining_scale, latest_amount 等 |
| `bond_snapshot` | 每日行情快照 | trade_date, bond_code, bond_name, price, price_change, change_pct, volume, amount, settlement, open_price, high_price, low_price, buy_price, sell_price, trade_time |
| `bond_kline` | 历史日线数据 | symbol, trade_date, high, low, `close`, open, volume, amount |
| `bond_weekly_kline` | 周线数据 | bond_code, trade_week, open/high/low/close, volume, amount, source, updated_at |
| `bond_detail` | 可转债详细信息 | bond_code, name, stock_code, stock_name, conversion_start_date, conversion_end_date, 评级/规模/条款等扩展字段 |

---

## 数据库表与云函数对应关系

| 表名 | 记录内容 | 写入（来源） | 读取（消费方） |
|------|----------|-------------|---------------|
| `bond_list` | 可转债基础列表：代码、名称、市场、是否活跃、创建/更新时间 | `cb_snapshot_updater`（每日增量：新增/退市标记） | `cb_oversold_detector`（关联 static 信息）<br>`cb_oversold_detector_weekly`（关联 static 信息）<br>`cb_weekly_kline_mootdx`（获取活跃转债列表）<br>`sina_bonds_detail_collector`（获取待采集详情的转债） |
| `bond_snapshot` | 每日行情快照：开盘价/高/低/收、涨跌、成交量、成交额、买卖盘等 | `cb_snapshot_updater`（每日15:10，新浪财经全量行情） | `cb_volume_filter`（计算5日均成交额，筛选异动）<br>`cb_oversold_detector`（2026-05-21起日K线数据源）<br>`cb_weekly_kline_aggregator`（聚合本周日线为周线）<br>`cb_weekly_kline_mootdx`（daily模式补充最新周线） |
| `bond_kline` | 历史日线数据：symbol、trade_date、high/low/close/open/volume/amount | **外部已有数据**（截至2026-05-20，无云函数维护写入） | `cb_oversold_detector`（2026-05-20前历史日K线）<br>`cb_weekly_kline_init`（聚合全量历史周线）<br>`cb_weekly_kline_mootdx`（daily模式聚合周线） |
| `bond_weekly_kline` | 周线数据：周开/高/低/收、成交量、成交额、数据来源标记 | `cb_weekly_kline_mootdx`（每周五16:00 mootdx采集）<br>`cb_weekly_kline_init`（一次性初始化：从 bond_kline 聚合）<br>`cb_weekly_kline_aggregator`（从 bond_snapshot 聚合本周周线） | `cb_oversold_detector_weekly`（计算周线 CCI+WR 指标） |
| `bond_detail` | 可转债详细信息：转股信息、评级、规模、利率、赎回/回售条款等 | `cb_snapshot_updater`（检测新债时自动采集）<br>`sina_bonds_detail_collector`（手动触发，批量采集/更新） | `cb_snapshot_updater`（检测新债时判断是否需要采集） |
| `bond_static` | 静态信息：到期日、剩余规模、最新规模等 | **未找到写入云函数**（可能手动维护或由外部系统写入） | `cb_volume_filter`（关联获取到期日、剩余规模用于展示）<br>`cb_oversold_detector`（关联获取到期日）<br>`cb_oversold_detector_weekly`（关联获取到期日） |

### 说明

- `sina_bonds_info_collector` 和 `sina_stock_info_collector` 目前**只输出 JSON 文件到本地目录**，未写入数据库（代码引用了 `db_config` 但 zip 包中未包含该模块）。
- `bond_static` 表在多只云函数中被**读取**，但在现有代码中**未找到创建或更新它的云函数**，推测是手动创建或由其他系统维护。
- `bond_kline` 是历史遗留日线数据表，数据截至 2026-05-20，目前无云函数负责维护写入，仅被读取使用。
- `bond_weekly_kline` 存在两种列命名风格：
  - `cb_weekly_kline_mootdx` 创建时使用 `open/high/low/close`
  - `cb_weekly_kline_init` / `cb_weekly_kline_aggregator` 使用 `open_price/high_price/low_price/close_price`
  - `cb_oversold_detector_weekly` 通过 `AS` 别名做了兼容映射

---

## 定时触发器汇总

| Cron 表达式 | 函数 | 说明 |
|-------------|------|------|
| `0 10 15 * * 1-5 *` | cb_snapshot_updater | 每天 15:10（周一至周五） |
| `0 30 15 * * 1-5 *` | cb_oversold_detector | 每天 15:30（周一至周五，日K线双超卖） |
| `0 40 15 * * 1-5 *` | cb_oversold_detector_weekly | 每天 15:40（周一至周五，周K线双超卖） |
| `0 50 15 * * 1-5 *` | cb_volume_filter | 每天 15:50（周一至周五，成交额异动筛选） |
| `0 0 16 * * 5 *` | cb_weekly_kline_mootdx | 每周五 16:00（mootdx周线采集） |

---

## 层依赖管理

| 层名 | 版本 | 用途 | 关联函数 |
|------|------|------|----------|
| `mootdx310` | v1 | mootdx 通达信协议库 | cb_weekly_kline_mootdx, mootdx-test |
| `pymysql` | v3 | MySQL 连接驱动 | cb_volume_filter |

---

## 本地已补充代码的函数（共6个）

> 以下函数之前在云端存在但本地无代码，现已通过 `tcb fn code download` 全部下载到本地 `cloudfunctions/` 目录。

| 函数名 | 运行时 | 依赖 | 核心功能 |
|--------|--------|------|----------|
| `cb_oversold_detector_weekly` | Node.js | mysql2 | 基于周K线的CCI+WR双超卖检测（每天15:40），与日频版互为补充 |
| `cb_weekly_kline_init` | Node.js | mysql2 | 周线数据一次性初始化：建bond_weekly_kline表 + 全量历史日线聚合成周线入库 |
| `sina_bonds_detail_collector` | Node.js | mysql2 | 新浪债券详情采集，入库bond_detail |
| `sina_stock_info_collector` | Python | pymysql | 新浪股票信息采集 |
| `sina_bonds_info_collector` | Python | pymysql | 新浪可转债基础信息采集 |

> ⚠️ `sina_stock_info_collector` 和 `sina_bonds_info_collector` 引用了 `db_config` 模块，但下载的 zip 包中未包含该文件，云端可能以其他方式提供（如环境变量或共享层）

---

# akshare 层部署进度记录 — 2026-05-22

## 今天做了什么

1. 创建了测试云函数 `test_akshare_layer`（Python3.11），代码在 `cloudfunctions/test_akshare_layer/index.py`
2. 构建了 Linux 兼容的 akshare 本地依赖目录 `cloudfunctions/layer_build/python/`（包含 akshare + pandas + numpy + lxml 等全部依赖）
3. 打包并上传到云存储：`akshare-layer-v2.zip`（45MB），存储地址 `7079-python12-9guk780v324f024d-1304734787.tcb.qcloud.la`
4. 已验证 akshare 层 v1 可绑定到函数，但调用时报 `ModuleNotFoundError: No module named 'akshare'`

## 当前状态

| 项目 | 状态 |
|------|------|
| 函数 `test_akshare_layer` | ✅ Python3.11，正常运行 |
| 层 `akshare` v1 | ✅ Active，Python3.11，已绑定到函数但模块找不到 |
| 层 `test-layer` v1 | ✅ 测试用，173 字节 |
| 本地 `layer_build/python/` | ✅ Linux 兼容的完整依赖 |
| 云存储 `akshare-layer-v2.zip` | ✅ 45MB 已上传 |
| 代码 `index.py` | ✅ 测试逻辑完整 |

## 根因找到

**旧 zip（akshare-layer-v2-py.zip）没有 `python/` 根目录**，所有文件散落在 zip 顶层。
SCF 层要求 zip 内必须有 `python/` 目录，解压后才映射到 `/opt/python/` 加入 sys.path。
之前绑定到函数找不到模块就是这个原因。

## 已准备好的正确文件

✅ `cloudfunctions/layer_build/akshare-layer-py311.zip`
- 结构正确：`python/akshare/`, `python/numpy/`, `python/pandas/` ...
- 4907 个文件，47.9 MB
- Linux 兼容（已替换 Windows .dll/.pyd 为 .so）

## 明天操作

打开控制台手工上传：
https://console.cloud.tencent.com/tcb/scf/layer?envId=python12-9guk780v324f024d
→ 选 akshare 层 → 创建新版本 → 上传 `akshare-layer-py311.zip` → 选运行时 Python3.11

上传后在 CLI：
```bash
tcb fn layer unbind test_akshare_layer --layer akshare
tcb fn layer bind test_akshare_layer --layer akshare --layer-version 2
tcb fn invoke test_akshare_layer
```

## 关键文件

---

# 飞书机器人菜单回调集成 — 2026-05-25

## 今天做了什么

1. 创建云函数 `mootdx-test`（Python3.10），绑定 `mootdx310` 层
2. 实现飞书事件回调处理，支持：
   - **URL验证**：识别 `type=url_verification` 并返回 challenge
   - **菜单点击事件**：接收 `application.bot.menu_v6` 事件
   - **mootdx行情查询**：点击 `test` 菜单获取 `113678` 当日行情
3. 配置HTTP触发器路径：`/test`
4. 验证通过：飞书URL验证 ✅，菜单点击回调 ✅，行情数据已成功返回

## 云函数配置

| 项目 | 值 |
|------|-----|
| 函数名 | `mootdx-test` |
| 运行时 | Python3.10 |
| Handler | `index.main` |
| 超时 | 60s |
| 绑定层 | `mootdx310:1` |
| HTTP触发器URL | `https://python12-9guk780v324f024d-1304734787.ap-shanghai.app.tcloudbase.com/test` |

## 飞书配置

1. 飞书开放平台 → 应用 → 事件订阅
2. 订阅方式：**发送回调到开发者服务器**
3. 请求地址：`https://python12-9guk780v324f024d-1304734787.ap-shanghai.app.tcloudbase.com/test`
4. 添加事件：`application.bot.menu_v6`（机器人菜单点击）
5. 机器人菜单配置：`event_key` 设为 `test`

## 代码要点

### URL验证处理（飞书发POST不是GET）

```python
if body.get('type') == 'url_verification':
    challenge = body.get('challenge', '')
    return {'challenge': challenge}
```

### 菜单事件处理

```python
if event_type == 'application.bot.menu_v6':
    return handle_bot_menu(event_data)
```

### 腾讯云函数事件格式

```python
http_method = event.get('httpMethod', 'GET')
body = event.get('body', '{}')
query_string = event.get('queryString', event.get('queryStringParameters', ''))
```

## 注意事项

1. **飞书URL验证是POST不是GET**：飞书发送POST请求带 `{"type":"url_verification","challenge":"..."}`，需要解析body中的type字段
2. **Handler名称必须匹配**：创建云函数时默认Handler可能是 `index.main`，如果代码入口函数名不同需同步修改
3. **腾讯云函数API网关路由**：`/test` 路径是用户手动配置的HTTP触发器，需要将域名和函数关联
4. **层绑定用CLI**：`tcb fn layer bind <function> --layer <name> --layer-version <n>`
5. **冷启动时间**：Python云函数冷启动约2.7s，但飞书要求URL验证在1s内响应，实测1ms即可返回，但总超时要考虑

## 踩过的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| `handler not found` | Handler配置为 `index.main_handler`，但系统默认用 `index.main` | 统一函数名为 `main` |
| Challenge code没有返回 | 以为URL验证是GET请求传query参数，实际是POST传JSON body | 检查 `type=url_verification` 再返回challenge |
| `{"status": "ok", "event_type": ""}` | POST请求走了回调分支，未识别验证请求 | 添加 `url_verification` 判断优先于事件分发 |

## 当前状态

| 项目 | 状态 |
|------|------|
| 云函数 `mootdx-test` | ✅ Python3.10，正常运行 |
| 层 `mootdx310` 绑定 | ✅ 已绑定到函数 |
| HTTP触发器 `/test` | ✅ 公网可访问 |
| 飞书URL验证 | ✅ 通过 |
| 飞书菜单回调 | ✅ `test` 菜单点击 → 获取113678行情数据成功 |
| mootdx行情查询 | ✅ 返回最新价173.96，成交量250651，成交额4.45亿 |

```
cloudfunctions/
├── test_akshare_layer/
│   ├── index.py           # 测试函数
│   ├── requirements.txt   # akshare>=1.16.72
│   └── func.zip
├── layer_build/
│   ├── python/            # Linux 兼容的依赖目录
│   ├── akshare-layer-v2-py.zip   # 压缩包
│   ├── akshare-layer-v2.zip      # 同上
│   └── publish_layer.py  # SCF API 创建层脚本
└── Dockerfile
cloudbaserc.json           # 环境: python12-9guk780v324f024d
```

---

# PyMySQL 层部署实战 — 2026-05-26

## 背景

`cb_volume_filter` 云函数需要 `pymysql` 连接 MySQL 数据库。通过层方式管理依赖，实现依赖复用和代码分离。

## 部署过程

1. **代码适配层路径**：`index.py` 中使用 `sys.path.insert(0, '/opt/python')` 引入层中的模块
2. **构建 zip 包**：用 Python `zipfile` 模块打包，确保内部结构为 `python/pymysql/...`
3. **手动上传到控制台**：CloudBase 控制台 → 云函数 → 层管理 → pymysql → 新建版本
4. **绑定到函数**：`tcb fn layer bind cb_volume_filter --layer pymysql --layer-version 4`
5. **手动触发验证**：`tcb fn invoke cb_volume_filter` → 成功筛选 12 只转债并推送飞书

## zip 包构建（正确做法）

```python
import os, shutil, zipfile, subprocess

base = 'tmp_layer'
python_dir = os.path.join(base, 'python')
out_zip = 'pymysql-layer.zip'

os.makedirs(python_dir)
subprocess.run(['pip', 'install', 'pymysql==1.1.1', '-t', python_dir, '--no-compile', '--no-deps'], check=True)

# 删除无用文件
for root, dirs, files in os.walk(python_dir, topdown=False):
    for d in dirs:
        if d == '__pycache__' or d.endswith('.dist-info'):
            shutil.rmtree(os.path.join(root, d))

# 用 Python zipfile，不要用 PowerShell Compress-Archive
with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(python_dir):
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, base)
            zf.write(full_path, arcname)
```

## 部署要点

| 要点 | 说明 |
|------|------|
| zip 根目录必须是 `python/` | SCF 解压后映射到 `/opt/python/`，代码里 `sys.path.insert(0, '/opt/python')` |
| 用 Python `zipfile` 打包 | **不要用** PowerShell `Compress-Archive`，产生的 zip 可能不兼容云平台 |
| `--no-compile` | 不生成 `.pyc` 缓存文件，减少包体积，避免运行时兼容问题 |
| 删除 `.dist-info` | pip 元数据目录可删除，不影响运行 |
| 层绑定后等几秒 | 绑定操作是异步的，等函数状态变为 `Active` 再触发 |
| 先解绑再删除重建 | 如果绑定失败导致 `UpdateFailed`，先 `unbind` 所有层再操作 |

## 踩过的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| `No module named 'pymysql'` | 初始未使用层，云端未安装依赖 | 创建 pymysql 层并绑定 |
| `InternalError` 绑定层失败 | 旧 zip 用 PowerShell `Compress-Archive` 打包，云平台不兼容 | 改用 Python `zipfile` 模块重新打包 |
| 函数反复 `UpdateFailed` | 绑定有问题的层后函数进入错误状态 | 先解绑所有层 → 删除函数 → 重建 → 用正确 zip 重新绑定 |
| mootdx310 层可以绑定、pymysql 不行 | 不是绑定机制问题，而是 pymysql 层的 zip 格式有问题 | 确认是 zip 打包工具导致的不兼容 |
| CLI 返回 `InternalError`，无法定位原因 | 腾讯云内部错误信息不明确 | 对比测试（绑定 mootdx310 成功 → 确认是 pymysql 层 zip 问题） |

## cloudbaserc.json 层配置

```json
{
  "envId": "python12-9guk780v324f024d",
  "functionRoot": "cloudfunctions",
  "functions": [
    {
      "name": "cb_volume_filter",
      "timeout": 300,
      "memorySize": 512,
      "runtime": "Python3.10",
      "layers": [
        { "name": "pymysql", "version": 4 }
      ]
    }
  ]
}
```

## CLI 常用命令

```bash
tcb fn layer list                          # 查看层列表
tcb fn layer bind <fn> --layer <name> --layer-version <n>   # 绑定层
tcb fn layer unbind <fn> --layer <name>    # 解绑层
tcb fn detail <fn>                         # 查看函数详情（含层绑定状态）
tcb fn invoke <fn>                         # 手动触发函数
```