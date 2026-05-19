通达信数据读取接口
==================

[![image](https://badge.fury.io/py/mootdx.svg)](http://badge.fury.io/py/mootdx)
[![image](https://img.shields.io/travis/bopo/mootdx.svg)](https://travis-ci.org/mootdx/mootdx)
[![Documentation Status](https://readthedocs.org/projects/mootdx/badge/?version=latest)](https://mootdx.readthedocs.io/zh/latest/?badge=latest)
[![Updates](https://pyup.io/repos/github/mootdx/mootdx/shield.svg)](https://pyup.io/repos/github/mootdx/mootdx/)

如果喜欢本项目可以在右上角给颗⭐！你的支持是我最大的动力😎！

**郑重声明: 本项目只作学习交流, 不得用于任何商业目的.**

-   开源协议: MIT license
-   在线文档: <https://www.mootdx.com>
-   国内镜像: <https://gitee.com/ibopo/mootdx>
-   项目仓库: <https://github.com/mootdx/mootdx>
-   问题交流: <https://github.com/mootdx/mootdx/issues>

版本更新(倒序)
--------------

版本更新日志: <https://mootdx.readthedocs.io/zh_CN/latest/history/>

运行环境
--------

-   操作系统: Windows / MacOS / Linux 都可以运行.
-   Python: 3.8 以及以上版本.

安装方法
--------

> 新手建议使用 `pip install -U 'mootdx[all]'` 安装

### PIP 安装方法
```shell

# 包含核心依赖安装
pip install 'mootdx'

# 包含命令行依赖安装, 如果使用命令行工具可以使用这种方式安装
pip install 'mootdx[cli]'

# 包含所有扩展依赖安装, 如果不清楚各种依赖关系就用这个命令
pip install 'mootdx[all]'
```

### 升级安装

```shell
pip install -U tdxpy mootdx
```

> 如果不清楚各种依赖关系就用这个命令 `pip install -U 'mootdx[all]'`

使用说明
--------

> 以下只列举一些例子, 详细说明请查看在线文档: <https://www.mootdx.com>

通达信离线数据读取

```python
from mootdx.reader import Reader

# market 参数 std 为标准市场(就是股票), ext 为扩展市场(期货，黄金等)
# tdxdir 是通达信的数据目录, 根据自己的情况修改

reader = Reader.factory(market='std', tdxdir='C:/new_tdx')

# 读取日线数据
reader.daily(symbol='600036')

# 读取分钟数据
reader.minute(symbol='600036')

# 读取时间线数据
reader.fzline(symbol='600036')
```

通达信线上行情读取

```python
from mootdx.quotes import Quotes

# 标准市场
client = Quotes.factory(market='std', multithread=True, heartbeat=True)

# k 线数据
client.bars(symbol='600036', frequency=9, offset=10)

# 指数
client.index(symbol='000001', frequency=9)

# 分钟
client.minute(symbol='000001')
```

通达信财务数据读取

```python
from mootdx.affair import Affair

# 远程文件列表
files = Affair.files()

# 下载单个
Affair.fetch(downdir='tmp', filename='gpcw19960630.zip')

# 下载全部
Affair.parse(downdir='tmp')
```

加微信交流
----------
加微信交流
----------

![](docs/img/IMG_2851.JPG)

常见问题
--------

M1 mac 系统PyMiniRacer不能使用，访问:
<https://github.com/sqreen/PyMiniRacer/issues/143>


## Stargazers over time

[![Stargazers over time](https://starchart.cc/mootdx/mootdx.svg)](https://starchart.cc/mootdx/mootdx)

---

## 附：沪深可转债当日行情采集（新浪财经）

> mootdx 本身没有可转债专用接口，沪深全量可转债行情通过新浪财经 `hskzz_z` 节点获取。

### 1. 新浪可转债 API 接口

| 项目 | 说明 |
|------|------|
| 接口地址 | `https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData` |
| 板块节点 | `hskzz_z`（沪深可转债） |
| 返回格式 | JSON，GBK 编码 |
| 每页条数 | 50 条 |
| 总页数 | 7 页（动态） |

请求参数：

```
page=1           # 页码，从1开始
num=50           # 每页条数
sort=symbol      # 排序字段
asc=1            # 升序
node=hskzz_z     # 板块节点（可转债）
symbol=          # 留空
_s_r_a=page      # 分页标识
```

响应字段：

| 字段 | 说明 |
|------|------|
| symbol | 市场+代码，如 `sh110074` |
| code | 证券代码（6位） |
| name | 证券名称 |
| trade | 最新价 |
| pricechange | 涨跌额 |
| changepercent | 涨跌幅（%） |
| buy / sell | 买一价 / 卖一价 |
| settlement | 昨收价 |
| open | 开盘价 |
| high / low | 最高价 / 最低价 |
| volume | 成交量（股） |
| amount | 成交额（元） |
| ticktime | 成交时间 |

### 2. 代码示例

```python
import requests
import json

url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://vip.stock.finance.sina.com.cn/mkt/",
    "Accept-Charset": "gbk",
}

params = {
    "page": 1,
    "num": 50,
    "sort": "symbol",
    "asc": 1,
    "node": "hskzz_z",
    "symbol": "",
    "_s_r_a": "page",
}

r = requests.get(url, params=params, headers=headers, timeout=15)
r.encoding = "gbk"
data = json.loads(r.text)

for item in data:
    print(item["code"], item["name"], item["trade"], item["changepercent"])
```

### 3. 完整采集脚本

使用 `fetch_sina_cb_quotes.py` 即可一键采集并存为 CSV/Excel：

```bash
python fetch_sina_cb_quotes.py
```

输出文件（`convertible_bond/` 目录）：

| 文件 | 说明 |
|------|------|
| `all_convertible_bonds_sina_YYYYMMDD.csv` | UTF-8 CSV |
| `all_convertible_bonds_sina_YYYYMMDD.xlsx` | Excel |

数据量参考（2026-05-18）：

| 市场 | 数量 |
|------|------|
| 沪市 | 168 只 |
| 深市 | 178 只 |
| 合计 | **346 只** |

> 注意：新浪 API 返回的 349 条记录中有 3 条为北交所"定转"（定向转债，非公开募集），脚本会自动剔除名称含"定转"的记录。

### 4. 与 mootdx 对比

| 对比项 | mootdx 方案 | 新浪 API 方案 |
|--------|------------|--------------|
| 可转债数量 | 约 320 只（不完整） | **346 只（完整）** |
| 采集速度 | ~10 秒（全量扫描） | ~2 秒（直接定位） |
| 数据接口 | `stocks()` + `quotes()` | 新浪 `hskzz_z` 节点 |
| 五档行情 | 支持 | 不支持（仅有买一/卖一） |
| 备注 | 通达信服务器可能不稳定 | 新浪接口稳定免费 |

---

## 附：CloudBase MySQL 数据库

> 可转债的全部数据（基础信息 + 日行情）存储在腾讯云 CloudBase MySQL（CynosDB 8.0）中。

### 1. 连接信息

| 项目 | 说明 |
|------|------|
| 公网地址 | `sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com:27120` |
| 数据库名 | `python12-9guk780v324f024d` |
| 用户名 | `cbreport` |

### 2. 表结构

#### bond_static — 转债档案（341 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| `bond_code` | VARCHAR(20) | 转债代码（主键） |
| `bond_name` | VARCHAR(50) | 转债名称 |
| `market` | VARCHAR(10) | 沪市/深市 |
| `exchange` | VARCHAR(20) | 上交所/深交所 |
| `stock_code` | VARCHAR(20) | 带后缀正股代码 |
| `stock_code_full` | VARCHAR(20) | 正股全代码 |
| `stock_code_no_suffix` | VARCHAR(20) | 正股纯代码 |
| `stock_short_name` | VARCHAR(50) | 正股简称 |
| `industry_level1~3` | VARCHAR(50) | 行业三级分类 |
| `issue_amount` | DECIMAL(15,2) | 发行规模(亿) |
| `latest_amount` | DECIMAL(15,4) | 最新规模(亿) |
| `maturity_date` | DATE | 到期日期 |
| `convert_price` | DECIMAL(10,3) | 最新转股价 |
| `call_trigger_pct` | DECIMAL(5,2) | 条件赎回触发比例(%) |
| `rating_level` | VARCHAR(20) | 评级等级 |
| `rating_agency` | VARCHAR(100) | 评级机构 |
| `rating_date` | DATE | 评级日期 |
| `website` | VARCHAR(200) | 公司网址 |
| `business_main` | TEXT | 主营业务 |
| `office_address` | VARCHAR(200) | 办公地址 |
| `concepts_json` | JSON | 概念标签 |
| `themes_json` | JSON | 主题投资 |
| `announcements_json` | JSON | 最新公告 |
| `sector` | VARCHAR(50) | 板块 |

#### bond_snapshot — 日行情快照

| 字段 | 类型 | 说明 |
|------|------|------|
| `trade_date` | DATE | 交易日 |
| `bond_code` | VARCHAR(20) | 转债代码 |
| `bond_name` | VARCHAR(50) | 转债名称 |
| `price` | DECIMAL(10,2) | 最新价 |
| `price_change` | DECIMAL(10,2) | 涨跌额 |
| `change_pct` | DECIMAL(10,4) | 涨跌幅(%) |
| `volume` | BIGINT | 成交量(股) |
| `amount` | DECIMAL(15,4) | 成交额(元) |
| `settlement` | DECIMAL(10,2) | 昨收价 |
| `open_price` | DECIMAL(10,3) | 开盘价 |
| `high_price` | DECIMAL(10,3) | 最高价 |
| `low_price` | DECIMAL(10,3) | 最低价 |
| `buy_price` | DECIMAL(10,3) | 买一价 |
| `sell_price` | DECIMAL(10,3) | 卖一价 |
| `trade_time` | VARCHAR(10) | 成交时间 |

> 联合唯一索引 `(bond_code, trade_date)`，重复执行时自动覆盖更新。

### 3. 采集与入库

```bash
# 一键全量：采集 F10 + 写入数据库
python collect_and_import.py
```

脚本全局开关（文件顶部）：

```python
DO_COLLECT = True    # 是否采集 F10（首次运行开，后续可关）
DO_IMPORT = True     # 是否写入数据库
```

增量更新流程（每天盘后）：

```bash
# Step 1: 获取当日新浪行情
python fetch_sina_cb_quotes.py

# Step 2: 入库（跳过采集，仅写行情）
#   修改 collect_and_import.py 中 DO_COLLECT = False，然后运行：
python collect_and_import.py
```

### 4. 数据量参考（2026-05-18）

| 表 | 记录数 |
|------|--------|
| `bond_static` | 341 只 |
| `bond_snapshot` | 2,805 条（8 天历史） |
| `bond_kline` | 274,483 条 |

**bond_static 字段覆盖率：**

| 字段 | 覆盖率 |
|------|--------|
| 转股价 | 99% |
| 评级 | 100% |
| 概念 | 100% |
| 主题投资 | 100% |
| 最新公告 | 100% |
| 主营业务 | 99% |

**评级分布：** AA- 104 > AA 85 > A+ 57 > AA+ 34 > AAA 25

**转股价区间：** 1.40 ~ 364.43，均值 25.12

---

## 附：云函数 — 可转债日行情定时更新

> 使用 CloudBase 云函数（SCF）每天 15:10 自动抓取新浪可转债行情，增量追加到 `bond_snapshot` 表，完成后通过飞书机器人通知。

### 1. 云函数配置

| 项目 | 值 |
|------|-----|
| 函数名称 | `cb_snapshot_updater` |
| 运行时 | Node.js 18.15 |
| 内存 | 256 MB |
| 超时 | 300 秒 |
| 触发器 | `cb_daily_snapshot`（timer） |

### 2. 定时触发器

| 项目 | 值 |
|------|-----|
| Cron 表达式 | `0 10 15 * * * *`（每天 15:10:00） |
| 随机浮动 | 60~300 秒（代码内实现，防止接口屏蔽） |

### 3. 代码逻辑

```
1. 函数触发（15:10）
2. 等待 random(60~300) 秒（防屏蔽）
3. 调用新浪 hskzz_z 接口获取全量可转债行情
4. 遍历每条记录，INSERT INTO bond_snapshot（增量追加）
5. 通过飞书机器人发送执行结果通知
```

### 4. 飞书通知内容

执行完成后发送卡片消息，包含：

- **触发时间**：函数启动时间
- **交易日期**：行情对应的日期
- **获取数据**：从新浪获取的记录数
- **成功写入**：实际写入数据库的条数
- **失败数量**：写入失败的条数
- **目标表**：`bond_snapshot`
- **执行耗时**：总耗时（秒）

### 5. 本地代码

```
cloudfunctions/cb_snapshot_updater/
├── index.js        # 云函数入口
└── package.json    # 依赖（mysql2）
```

### 6. 手动测试

```bash
# 通过腾讯云控制台或 CLI 触发
tccli scf Invoke --FunctionName cb_snapshot_updater
```

### 7. 日志查看

```bash
# 查看最近执行日志
tccli scf GetFunctionLogs --FunctionName cb_snapshot_updater --Limit 10
```

### 8. 依赖

| 包 | 版本 | 用途 |
|-----|------|------|
| mysql2 | ^3.6.0 | CloudBase MySQL 连接 |


## 前端 Web 项目（monorepo）

前端项目位于 `web/` 目录，是基于 Vue 3 的可转债投资分析系统。

### 技术栈

| 技术 | 版本 / 说明 |
|------|------------|
| Vue 3 | Composition API + `<script setup>` |
| TypeScript | 全量类型覆盖 |
| Vite 5 | 构建工具 |
| Vue Router 4 | 路由管理 |
| Ant Design Vue 4 | UI 组件库 |
| ECharts 5 | 图表可视化 |

### 项目结构

```
web/
├── src/
│   ├── views/          # 页面组件（Home、Detail、Scatter 等）
│   ├── components/
│   │   ├── charts/     # ECharts 图表组件（RiseFallChart、Heatmap 等）
│   │   └── common/     # 通用组件（NavTabs、BottomNav、BondTable 等）
│   ├── assets/         # 静态资源
│   └── styles/         # 全局样式 / CSS 变量
├── mock/
│   └── data.json       # 模拟数据（市场统计、可转债列表等）
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### 近期开发要点

#### 市场核心指标卡片（2026-05-19）

三个指标卡水平均分排布（flex 布局），点击时蓝色高亮，联动下方图表：

| 指标卡 | 展示内容 | 点击联动图表 |
|-------|---------|-------------|
| **涨跌分布** | `156`：`12`：`89`（涨：平：跌，红：黑：绿） | 涨跌区间分布柱状图（红涨绿跌） |
| **成交额情况** | `856.34亿元` → 较上日 `+32.15亿元`（红涨绿跌） | 成交额区间分布（<50亿 / 50-100亿 / ... / 500亿+） |
| **中位数** | 价格 `118.72` / 涨幅 `0.45%` / 成交额 `0.38亿元` | 价格区间分布（<100 / 100-110 / ... / 200+） |

#### mock 数据结构

marketStats 扩展字段：
- `volumeChange` — 成交额较上日变化（亿元）
- `priceMedian` — 价格中位数
- `changeMedian` — 涨幅中位数（%）
- `volumeMedian` — 成交额中位数（亿元）

图表分发数据：
- `riseFallDistribution` — 涨跌区间分布（categories + values）
- `volumeDistribution` — 成交额区间分布
- `priceDistribution` — 价格区间分布（左开右闭）

### 开发命令

```bash
cd web
npm install          # 安装依赖
npm run dev          # 启动开发服务器
npm run build        # 构建生产版本
npm run typecheck    # TypeScript 类型检查
npm run lint         # ESLint 检查
```

