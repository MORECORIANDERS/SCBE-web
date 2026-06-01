# SCBE-web 

可转债市场行情监控与分析 Web 应用，采用 GitHub 极简风格，提供实时行情、双低筛选、行业热力图、技术指标分析等功能。

## 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 + TypeScript | 前端框架 |
| Vite 5 | 构建工具 |
| Ant Design Vue 4.x | UI 组件库 |
| ECharts 5 | 图表可视化 |
| Vue Router 4 | 路由管理 |
| GitHub Pages | 静态部署 |
| CloudBase | 云函数 + MySQL 后端 |

## 页面功能

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 市场核心指标、涨跌分布、可转债行情列表 |
| `/heatmap` | 行业热力图 | 按行业维度展示溢价率/双低数值分布 |
| `/scatter` | 双低散点分析 | 散点图展示转债价格与溢价率关系 |
| `/detail/:code` | 转债详情 | 单只可转债详细信息与历史走势 |
| `/control` | 系统控制面板 | 数据采集管理 |
| `/settings` | 系统参数配置 | 飞书推送、定时任务等配置 |
| `/login` | 登录页 | 用户认证 |

## 快速开始

```bash
# 安装依赖
cd web && npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build

# 本地预览构建结果
npm run preview
```

## 项目结构

```
SCBE-web/
├── .github/workflows/deploy.yml   # GitHub Pages CI/CD
├── cloudbaserc.json               # CloudBase 云函数配置
└── web/                           # 前端应用
    ├── src/
    │   ├── api/                   # API 请求层
    │   ├── components/            # 公共组件
    │   │   ├── charts/            # 图表组件
    │   │   └── common/            # 通用组件
    │   ├── composables/           # 组合式函数
    │   ├── lib/                   # 工具函数
    │   ├── pages/                 # 页面组件
    │   ├── router/                # 路由配置
    │   ├── styles/                # 全局样式
    │   └── views/                 # 业务页面
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── tsconfig.json
```

## 后端架构

数据采集与分析通过腾讯 CloudBase 云函数实现，详见 [cloudbaserc.json](./cloudbaserc.json)：

| 云函数 | 触发 | 功能 |
|--------|------|------|
<<<<<<< HEAD
| `cb_snapshot_updater` | 交易日下午 15:10 + 手动刷新 | 从新浪财经采集全量可转债行情，更新 bond_snapshot + bond_list |
=======
| `cb_snapshot_updater` | 交易日 15:10 | 采集全量可转债行情 |
>>>>>>> 65475ac4585d6bba2e99dc6a6f2e34936bc7df1e
| `cb_oversold_detector` | 交易日 15:30 | CCI + WR 双超卖检测（日K线） |
| `cb_oversold_detector_weekly` | 交易日 15:40 | CCI + WR 双超卖检测（周K线） |
| `cb_volume_filter` | 交易日 15:50 | 成交额异动筛选 |
| `cb_weekly_kline_mootdx` | 每周五 16:00 | 周线数据采集 |
| `api-bridge` | HTTP 触发（前端请求） | **API 网关**：查询数据库 + 转发手动刷新请求 |

### 数据刷新流程

点击前端"刷新数据"按钮时：

```
用户点击刷新
  → Home.vue → refreshData()
    → api-bridge (/api/refresh)
      → 远程调用 cb_snapshot_updater (action=refresh)
        → 新浪财经实时采集 → UPSERT 到 bond_snapshot
      → 返回采集结果
    → fetchAll() → 查询最新数据 → 渲染页面
```

数据库 `bond_snapshot` 表使用唯一键 `(trade_date, bond_code)`，**每天每只转债只保留一条最新记录**，新数据自动覆盖旧数据。

> ⚠️ **安全说明**：`cloudbaserc.json` 中的 `envVariables` 已移除。请通过 CloudBase 控制台 → 云函数 → 环境变量 配置以下凭据：
> - `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` — MySQL 连接信息
> - `FEISHU_WEBHOOK` — 飞书机器人 Webhook 地址
> - `API_TOKEN` — API 认证凭据（需与前端 `config.ts` 中的值一致）

### 本地部署云函数

本地修改云函数代码后，通过 CloudBase CLI 部署：

```bash
# 安装 CloudBase CLI
npm install -g @cloudbase/cli

# 部署单个云函数
tcb functions deploy cb_snapshot_updater --force
tcb functions deploy api-bridge --force
```

## CI/CD

推送到 `main` 分支会自动触发 GitHub Actions 构建并部署到 GitHub Pages。


