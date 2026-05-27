/**
 * 可转债CCI+WR双超卖检测云函数（合并版：支持日线/周线）
 * =====================================================
 * 触发时间：
 *   daily  模式 — 每天 15:30 — 日线 K 线 + 当日快照
 *   weekly 模式 — 每天 15:40 — 周线 K 线
 * 功能：
 *   1. 加载对应周期的 K 线数据
 *   2. 计算 CCI(14) 和 WR(14) 指标
 *   3. 筛选满足双超卖条件的可转债（CCI < -100 且 WR > 80）
 *   4. 通过飞书机器人发送详细卡片
 *
 * 指标计算（参考通达信公式）：
 *   CCI = (TYP - MA(TYP, 14)) / (0.015 * AVEDEV(TYP, 14))
 *   WR  = (HHV(HIGH, 14) - CLOSE) / (HHV(HIGH, 14) - LLV(LOW, 14)) * 100
 */

const https = require('https');
const mysql = require('mysql2/promise');

const DB_CONFIG = {
  host: process.env.DB_HOST || 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: parseInt(process.env.DB_PORT || '27120'),
  user: process.env.DB_USER || 'cbreport',
  password: process.env.DB_PASSWORD || 'huo22QQQ',
  database: process.env.DB_NAME || 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 15000,
};

const FEISHU_WEBHOOK = process.env.FEISHU_WEBHOOK || 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';
const CCI_PERIOD = 14;
const WR_PERIOD = 14;
const RETRYABLE_ERROR_CODES = ['ER_MALFORMED_PACKET', 'PROTOCOL_CONNECTION_LOST', 'ECONNRESET', 'ETIMEDOUT', 'EPIPE'];

/**
 * 带自动重试的数据库查询
 */
async function queryWithRetry(queryFn, maxRetries = 2) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await queryFn();
    } catch (e) {
      const isRetryable = RETRYABLE_ERROR_CODES.includes(e.code);
      if (attempt < maxRetries && isRetryable) {
        console.warn(`[重试 ${attempt + 1}/${maxRetries}] 数据库错误: ${e.code} - ${e.message}`);
        await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
        continue;
      }
      throw e;
    }
  }
}

/**
 * 获取活跃可转债列表（含行业、剩余规模、到期日期）
 */
async function getBondList() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [rows] = await conn.query(`
        SELECT
          bl.bond_code,
          bl.bond_name,
          COALESCE(bs.industry_level1, '') AS industry,
          COALESCE(bs.latest_amount, 0) AS latest_amount,
          COALESCE(bs.maturity_date, '') AS maturity_date
        FROM bond_list bl
        LEFT JOIN bond_static bs ON bl.bond_code = bs.bond_code
        WHERE bl.is_active = 1
        ORDER BY bl.bond_code
      `);
      return rows;
    } finally {
      if (conn) await conn.end();
    }
  });
}

/**
 * 获取 bond_kline 表最新的截止日期（替代硬编码）
 */
async function getKlineCutoffDate() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [rows] = await conn.query(
        "SELECT MAX(trade_date) AS max_date FROM bond_kline"
      );
      if (rows && rows.length > 0 && rows[0].max_date) {
        const d = rows[0].max_date instanceof Date
          ? rows[0].max_date.toISOString().slice(0, 10)
          : String(rows[0].max_date);
        console.log(`Dynamic KLINE_CUTOFF_DATE: ${d}`);
        return d;
      }
      return '2026-05-20'; // fallback
    } finally {
      if (conn) await conn.end();
    }
  });
}

/**
 * 加载日线数据（bond_kline + bond_snapshot）
 */
async function loadDailyKlineData() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const cutoffDate = await getKlineCutoffDate();

      const [klineAll] = await conn.query(`
        SELECT SUBSTRING(symbol, 3) AS bond_code, trade_date, high, low, \`close\`
        FROM bond_kline
        WHERE trade_date >= DATE_SUB(?, INTERVAL 30 DAY)
          AND trade_date <= ?
      `, [cutoffDate, cutoffDate]);

      const [snapshotAll] = await conn.query(`
        SELECT bond_code, trade_date, high_price, low_price, price
        FROM bond_snapshot
        WHERE trade_date > ?
      `, [cutoffDate]);

      return { klineAll, snapshotAll };
    } finally {
      if (conn) await conn.end();
    }
  });
}

/**
 * 加载周线数据（bond_weekly_kline）
 */
async function loadWeeklyKlineData() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [weeklyAll] = await conn.query(`
        SELECT bond_code, trade_week,
          COALESCE(high_price, high) AS high,
          COALESCE(low_price, low) AS low,
          COALESCE(close_price, \`close\`) AS close
        FROM bond_weekly_kline
        ORDER BY bond_code, trade_week
      `);
      return { weeklyAll };
    } finally {
      if (conn) await conn.end();
    }
  });
}

// ---- 指标计算 ----

function calculateMA(data, period) {
  if (data.length < period) return null;
  const sum = data.slice(-period).reduce((acc, val) => acc + val, 0);
  return sum / period;
}

function calculateAVEDEV(data, period, mean) {
  if (data.length < period) return null;
  const sum = data.slice(-period).reduce((acc, val) => acc + Math.abs(val - mean), 0);
  return sum / period;
}

function calculateCCI(klineData) {
  if (!klineData || klineData.length < CCI_PERIOD) return null;

  const typValues = klineData.map(k => {
    const high = parseFloat(k.high);
    const low = parseFloat(k.low);
    const close = parseFloat(k.close);
    const h = isNaN(high) ? close : high;
    const l = isNaN(low) ? close : low;
    return (h + l + close) / 3;
  });

  const maTyp = calculateMA(typValues, CCI_PERIOD);
  if (maTyp === null) return null;

  const avedevTyp = calculateAVEDEV(typValues, CCI_PERIOD, maTyp);
  if (avedevTyp === null || avedevTyp === 0) return null;

  const latestTyp = typValues[typValues.length - 1];
  return (latestTyp - maTyp) / (0.015 * avedevTyp);
}

function calculateWR(klineData) {
  if (!klineData || klineData.length < WR_PERIOD) return null;

  const recentData = klineData.slice(-WR_PERIOD);
  const highPrices = recentData.map(k => {
    const v = parseFloat(k.high);
    return isNaN(v) ? parseFloat(k.close) : v;
  });
  const lowPrices = recentData.map(k => {
    const v = parseFloat(k.low);
    return isNaN(v) ? parseFloat(k.close) : v;
  });
  const closePrice = parseFloat(klineData[klineData.length - 1].close);

  const hhv = Math.max(...highPrices);
  const llv = Math.min(...lowPrices);

  if (!isFinite(hhv) || !isFinite(llv) || hhv === llv) return null;

  return ((hhv - closePrice) / (hhv - llv)) * 100;
}

// ---- 飞书通知 ----

function sendFeishuNotification(bonds, elapsed, mode) {
  return new Promise((resolve, reject) => {
    if (bonds.length === 0) {
      console.log(`No ${mode} oversold bonds found, skipping notification`);
      resolve(null);
      return;
    }

    const sortedBonds = [...bonds].sort((a, b) => parseFloat(a.latest_amount || 0) - parseFloat(b.latest_amount || 0));

    let elementsContent = '';
    sortedBonds.forEach((bond, index) => {
      const industry = bond.industry || '-';
      const remainScale = bond.latest_amount
        ? `${parseFloat(bond.latest_amount).toFixed(2)}亿`
        : '-';
      const maturity = bond.maturity_date || '-';

      elementsContent += `${index + 1}. **${bond.bond_name}**（${bond.bond_code}）\n`;
      elementsContent += `   行业: ${industry} | 剩余规模: ${remainScale} | 到期: ${maturity}\n`;
      elementsContent += `   CCI: ${bond.cci.toFixed(2)} | WR: ${bond.wr.toFixed(2)} | 价格: ${bond.price}\n\n`;
    });

    const now = new Date();
    const beijingTime = now.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

    const isWeekly = mode === 'weekly';
    const title = isWeekly ? '可转债【周线】CCI+WR双超卖提醒' : '可转债CCI+WR双超卖提醒';
    const periodLabel = isWeekly ? '周' : '日';
    const dataNote = isWeekly
      ? `CCI周期: ${CCI_PERIOD}周 | WR周期: ${WR_PERIOD}周 | 数据源: bond_weekly_kline`
      : `CCI周期: ${CCI_PERIOD}日 | WR周期: ${WR_PERIOD}日 | 数据源: bond_kline + bond_snapshot + bond_static`;

    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: title },
          template: 'red',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**检测时间**：${beijingTime}\n**检测周期**：${periodLabel}线（${CCI_PERIOD}${periodLabel}）\n**检测条件**：CCI < -100 且 WR > 80\n**满足条件**：${sortedBonds.length} 只\n**执行耗时**：${elapsed} 秒`,
            },
          },
          { tag: 'hr' },
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: elementsContent,
            },
          },
          { tag: 'hr' },
          {
            tag: 'note',
            elements: [
              {
                tag: 'plain_text',
                content: dataNote,
              },
            ],
          },
        ],
      },
    });

    const url = new URL(FEISHU_WEBHOOK);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.code === 0 || result.StatusCode === 0) {
            console.log('Feishu notification sent successfully');
            resolve(result);
          } else {
            console.error('Feishu notification failed:', result);
            reject(new Error(result.msg || 'Feishu API error'));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// ---- 核心检测逻辑 ----

/**
 * 基于 K 线数据 + 债券列表，计算指标并筛选超卖
 */
function detectOversold(bonds, klineByBond) {
  const oversoldBonds = [];
  let processed = 0;
  let failed = 0;

  for (const bond of bonds) {
    try {
      const klineData = klineByBond[bond.bond_code] || null;

      if (!klineData || klineData.length < Math.max(CCI_PERIOD, WR_PERIOD)) {
        failed++;
        continue;
      }

      const cci = calculateCCI(klineData);
      const wr = calculateWR(klineData);

      if (cci === null || wr === null) {
        failed++;
        continue;
      }

      if (cci < -100 && wr > 80) {
        const latestKline = klineData[klineData.length - 1];
        oversoldBonds.push({
          bond_code: bond.bond_code,
          bond_name: bond.bond_name,
          industry: bond.industry,
          latest_amount: bond.latest_amount,
          maturity_date: bond.maturity_date,
          price: parseFloat(latestKline.close).toFixed(3),
          cci, wr,
        });
      }

      processed++;
      if (processed % 50 === 0) {
        console.log(`Progress: ${processed}/${bonds.length}, Oversold: ${oversoldBonds.length}`);
      }
    } catch (e) {
      console.error(`Error processing ${bond.bond_code}: ${e.message}`);
      failed++;
    }
  }

  return { oversoldBonds, processed, failed };
}

/**
 * 将原始 K 线行数据按 bond_code 分组为 { trade_date, high, low, close }[] 数组
 */
function groupKlineByBond(rows, dateField, highField, lowField, closeField) {
  const byBond = {};
  for (const row of rows) {
    const code = row.bond_code;
    if (!byBond[code]) byBond[code] = [];
    const dateStr = row[dateField] instanceof Date
      ? row[dateField].toISOString().slice(0, 10)
      : String(row[dateField]);
    byBond[code].push({
      trade_date: dateStr,
      high: row[highField],
      low: row[lowField],
      close: row[closeField],
    });
  }
  // 按日期排序，取最近 30 条
  for (const code of Object.keys(byBond)) {
    byBond[code].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    byBond[code] = byBond[code].slice(-30);
  }
  return byBond;
}

// ---- Mode 入口 ----

async function runDailyMode() {
  console.log(`[${new Date().toISOString()}] CCI+WR Oversold Detection (Daily) Started`);

  console.log('Fetching bond list...');
  const bonds = await getBondList();
  console.log(`Found ${bonds.length} active bonds`);

  console.log('Loading kline data (bond_kline + bond_snapshot)...');
  const { klineAll, snapshotAll } = await loadDailyKlineData();

  // 合并 kline 与 snapshot：snapshot 覆盖最新数据
  const rawByBond = {};
  for (const row of klineAll) {
    const code = row.bond_code;
    if (!rawByBond[code]) rawByBond[code] = {};
    const dateStr = row.trade_date instanceof Date
      ? row.trade_date.toISOString().slice(0, 10)
      : String(row.trade_date);
    if (!rawByBond[code][dateStr]) {
      rawByBond[code][dateStr] = { trade_date: dateStr, high: row.high, low: row.low, close: row.close };
    }
  }
  for (const row of snapshotAll) {
    const code = row.bond_code;
    if (!rawByBond[code]) rawByBond[code] = {};
    const dateStr = row.trade_date instanceof Date
      ? row.trade_date.toISOString().slice(0, 10)
      : String(row.trade_date);
    rawByBond[code][dateStr] = {
      trade_date: dateStr,
      high: row.high_price != null ? row.high_price : row.price,
      low: row.low_price != null ? row.low_price : row.price,
      close: row.price,
    };
  }

  // 排序 + 截取最近 30 天
  for (const code of Object.keys(rawByBond)) {
    const sorted = Object.values(rawByBond[code]).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    rawByBond[code] = sorted.slice(-30);
  }

  const { oversoldBonds, processed, failed } = detectOversold(bonds, rawByBond);
  const elapsed = Math.round((Date.now() - startTime) / 1000);

  console.log(`[${new Date().toISOString()}] Daily Detection completed`);
  console.log(`  Processed: ${processed}, Failed: ${failed}`);
  console.log(`  Oversold bonds found: ${oversoldBonds.length}`);

  try {
    await sendFeishuNotification(oversoldBonds, elapsed, 'daily');
  } catch (e) {
    console.error('Feishu notification error:', e.message);
  }

  return {
    success: true, total: bonds.length, processed, failed,
    oversoldCount: oversoldBonds.length,
    oversoldBonds: oversoldBonds.slice(0, 20), elapsed,
  };
}

async function runWeeklyMode() {
  console.log(`[${new Date().toISOString()}] CCI+WR Oversold Detection (Weekly) Started`);

  console.log('Fetching bond list...');
  const bonds = await getBondList();
  console.log(`Found ${bonds.length} active bonds`);

  console.log('Loading weekly kline data...');
  const { weeklyAll } = await loadWeeklyKlineData();

  const klineByBond = groupKlineByBond(weeklyAll, 'trade_week', 'high', 'low', 'close');

  const { oversoldBonds, processed, failed } = detectOversold(bonds, klineByBond);
  const elapsed = Math.round((Date.now() - startTime) / 1000);

  console.log(`[${new Date().toISOString()}] Weekly Detection completed`);
  console.log(`  Processed: ${processed}, Failed: ${failed}`);
  console.log(`  Weekly oversold bonds found: ${oversoldBonds.length}`);

  try {
    await sendFeishuNotification(oversoldBonds, elapsed, 'weekly');
  } catch (e) {
    console.error('Feishu notification error:', e.message);
  }

  return {
    success: true, total: bonds.length, processed, failed,
    oversoldCount: oversoldBonds.length,
    oversoldBonds: oversoldBonds.slice(0, 20), elapsed,
  };
}

// ---- 主入口 ----

let startTime;

exports.main = async (event, context) => {
  startTime = Date.now();

  // 支持 mode 参数：daily（默认）/ weekly
  const mode = (event && event.mode === 'weekly') ? 'weekly' : 'daily';

  try {
    console.log(`[${new Date().toISOString()}] Mode: ${mode}`);
    const result = mode === 'weekly' ? await runWeeklyMode() : await runDailyMode();
    return { code: 0, message: 'success', data: result };
  } catch (e) {
    console.error('Function error:', e);
    return { code: -1, message: e.message };
  }
};
