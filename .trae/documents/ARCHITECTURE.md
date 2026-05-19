# 可转债投资系统 - 技术架构文档

## 1. 项目架构

```
/workspace
├── src/
│   ├── assets/              # 静态资源
│   ├── components/          # 公共组件
│   │   ├── common/          # 通用组件
│   │   └── charts/          # 图表组件
│   ├── composables/         # 组合式函数
│   ├── router/              # 路由配置
│   ├── stores/              # 状态管理（localStorage）
│   ├── styles/              # 全局样式
│   ├── utils/               # 工具函数
│   ├── views/               # 页面组件
│   │   ├── Login.vue        # 登录页
│   │   ├── Home.vue         # 首页
│   │   ├── Heatmap.vue       # 行业热力图
│   │   ├── Scatter.vue       # 双低散点分析
│   │   ├── Detail.vue        # 转债详情
│   │   ├── Control.vue       # 系统控制面板
│   │   └── Settings.vue      # 系统参数配置
│   ├── App.vue
│   └── main.ts
├── public/                  # 公共资源
├── mock/                    # 模拟数据
│   └── data.json            # 可转债数据
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 2. 技术选型

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4+ | 核心框架 |
| Vite | 5.x | 构建工具 |
| Ant Design Vue | 4.x | UI 组件库 |
| Vue Router | 4.x | 路由管理 |
| ECharts | 5.x | 图表库 |
| TypeScript | 5.x | 类型支持 |

## 3. 核心组件设计

### 3.1 布局组件

| 组件 | 职责 |
|------|------|
| MainLayout | 主布局容器，包含顶部导航/底部导航 |
| NavTabs | PC 端 Tab 导航栏 |
| BottomNav | 手机端底部导航栏 |

### 3.2 业务组件

| 组件 | 职责 |
|------|------|
| MetricCard | 指标卡片组件 |
| QuickEntry | 快捷功能入口组件 |
| RiseFallChart | 涨跌分布柱状图 |
| BondTable | 可转债行情表格 |
| BondMiniChart | 迷你趋势线组件 |

## 4. 路由配置

```typescript
// 路由守卫逻辑
- 未登录状态访问需要鉴权的页面 → 重定向到 /login
- 已登录状态访问 /login → 重定向到 /
- 登录验证基于 localStorage.getItem('isLoggedIn')
```

## 5. 状态管理

### 5.1 localStorage Keys

| Key | 类型 | 用途 |
|-----|------|------|
| isLoggedIn | boolean | 登录状态 |
| settings | object | 系统配置参数 |
| favorites | array | 自选转债列表 |

### 5.2 配置参数结构

```typescript
interface Settings {
  webhookUrl: string;      // 飞书 Webhook 地址
  pushEnabled: boolean;    // 推送开关
  scheduledEnabled: boolean; // 定时采集开关
  scheduledTime: string;   // 定时采集时间
  retentionDays: number;   // 数据保留天数
}
```

## 6. 模拟数据模型

### 6.1 可转债数据结构

```typescript
interface Bond {
  code: string;           // 转债代码
  name: string;           // 转债名称
  price: number;          // 转债价格
  changePercent: number;  // 涨跌幅
  stockPrice: number;     // 正股价格
  stockChangePercent: number; // 正股涨跌幅
  premium: number;        // 转股溢价率
  remainSize: number;     // 剩余规模（亿元）
  doubleLow: number;      // 双低数值
  industry: string;       // 所属行业
}
```

### 6.2 行情统计数据

```typescript
interface MarketStats {
  totalVolume: number;    // 总成交额
  riseCount: number;      // 上涨家数
  fallCount: number;      // 下跌家数
  flatCount: number;      // 平盘家数
  avgPrice: number;       // 平均价格
  avgPremium: number;     // 平均溢价率
  avgDoubleLow: number;   // 平均双低值
}
```

## 7. ECharts 配置规范

### 7.1 配色方案（GitHub 风格）

```javascript
// 图表主题色
const chartTheme = {
  colors: ['#0969da', '#1a7f37', '#cf222e', '#8250df', '#bf8700'],
  backgroundColor: '#ffffff',
  textColor: '#24292f',
  axisColor: '#d0d7de',
  splitLineColor: '#f6f8fa'
};

// 涨跌柱状图配色
const riseColor = '#1a7f37';  // 上涨（低饱和绿）
const fallColor = '#cf222e';  // 下跌（低饱和红）
```

### 7.2 图表交互规范

- 禁用所有动画效果
- 悬浮提示框使用简洁样式
- 坐标系使用浅色网格线
- 图例使用点击切换显示

## 8. 响应式适配策略

### 8.1 媒体查询断点

```css
/* 手机端 */
@media (max-width: 767px) {
  /* 隐藏 PC 端导航，显示底部导航 */
  /* 卡片纵向堆叠 */
  /* 功能入口横向滚动 */
}

/* PC 端 */
@media (min-width: 768px) {
  /* 显示顶部导航 */
  /* 卡片横向排列 */
}
```

### 8.2 组件适配原则

- 使用 `v-show` 和 CSS 媒体查询控制显示
- 表格组件添加 `x-scroll` 包装器
- 图表组件自动适应容器宽度
- 保持所有功能在双端可用

## 9. 开发规范

### 9.1 代码规范

- 使用 `<script setup lang="ts">` 语法糖
- 组件文件使用 PascalCase 命名
- 样式使用 CSS Variables 管理主题色
- 关键逻辑添加中文注释

### 9.2 GitHub 风格要点

- 无阴影卡片（使用细边框）
- 无渐变色
- 无圆角色标
- 纯色低饱和配色
- 功能优先，克制装饰
