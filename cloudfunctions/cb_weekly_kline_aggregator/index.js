/**
 * 可转债周线聚合云函数
 * =================================
 * 触发时间：每天 15:36（收盘后）
 * 功能：
 *   1. 从 bond_snapshot 获取本周所有日线数据
 *   2. 按转债代码聚合为周线数据
 *   3. 写入 bond_weekly_kline 表
 *
 * 周线聚合规则：
 *   trade_week = 本周周一日期
 *   open_price = 本周第一天开盘价
 *   high_price = 本周最高价
 *   low_price = 本周最低价
 *   close_price = 本周最后一天收盘价
 *   volume = 本周总成交量
 */

const mysql = require('mysql2/promise');

const DB_CONFIG = {
  host: 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: 27120,
  user: 'cbreport',
  password: 'huo22QQQ',
  database: 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 30000,
  enableKeepAlive: true,
  keepAliveInitialDelay: 10000,
};

const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

function getMondayOfWeek(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function isTradingDay(date) {
  const day = date.getDay();
  return day >= 1 && day <= 5;
}

async function getCurrentWeekDailyData() {
  const pool = mysql.createPool(DB_CONFIG);
  let conn;
  try {
    conn = await pool.getConnection();

    const today = new Date();
    const monday = getMondayOfWeek(today);

    const todayStr = formatDate(today);
    const mondayStr = formatDate(monday);

    console.log(`Aggregating weekly data: ${mondayStr} to ${todayStr}`);

    const [rows] = await conn.query(`
      SELECT
        bond_code,
        trade_date,
        open_price,
        high_price,
        low_price,
        price AS close_price,
        volume
      FROM bond_snapshot
      WHERE trade_date >= ? AND trade_date <= ?
      ORDER BY bond_code, trade_date
    `, [mondayStr, todayStr]);

    return rows;
  } finally {
    if (conn) conn.release();
    await pool.end();
  }
}

async function aggregateWeeklyData(dailyData) {
  const weeklyMap = new Map();

  for (const row of dailyData) {
    if (!row.open_price || !row.high_price || !row.low_price || !row.close_price) {
      continue;
    }

    const code = row.bond_code;
    const tradeDate = new Date(row.trade_date);
    const monday = getMondayOfWeek(tradeDate);
    const weekKey = formatDate(monday);

    const key = `${code}_${weekKey}`;

    if (!weeklyMap.has(key)) {
      weeklyMap.set(key, {
        bond_code: code,
        trade_week: weekKey,
        open_price: row.open_price,
        high_price: row.high_price,
        low_price: row.low_price,
        close_price: row.close_price,
        volume: BigInt(row.volume || 0),
      });
    } else {
      const existing = weeklyMap.get(key);
      existing.high_price = Math.max(existing.high_price, row.high_price);
      existing.low_price = Math.min(existing.low_price, row.low_price);
      existing.close_price = row.close_price;
      existing.volume += BigInt(row.volume || 0);
    }
  }

  return Array.from(weeklyMap.values());
}

async function upsertWeeklyData(weeklyData) {
  if (weeklyData.length === 0) {
    console.log('No weekly data to upsert');
    return { inserted: 0, updated: 0 };
  }

  const pool = mysql.createPool(DB_CONFIG);
  let conn;
  try {
    conn = await pool.getConnection();

    let inserted = 0;
    let updated = 0;

    for (const week of weeklyData) {
      const [result] = await conn.query(`
        INSERT INTO bond_weekly_kline
          (bond_code, trade_week, open_price, high_price, low_price, close_price, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
          open_price = VALUES(open_price),
          high_price = VALUES(high_price),
          low_price = VALUES(low_price),
          close_price = VALUES(close_price),
          volume = VALUES(volume)
      `, [
        week.bond_code,
        week.trade_week,
        week.open_price,
        week.high_price,
        week.low_price,
        week.close_price,
        Number(week.volume)
      ]);

      if (result.affectedRows === 1) {
        inserted++;
      } else if (result.affectedRows === 2) {
        updated++;
      }
    }

    return { inserted, updated };
  } finally {
    if (conn) conn.release();
    await pool.end();
  }
}

function sendFeishuNotification(result, elapsed) {
  return new Promise((resolve, reject) => {
    const now = new Date();
    const beijingTime = now.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: '可转债周线聚合完成' },
          template: 'blue',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**执行时间**：${beijingTime}\n**聚合记录**：${result.total} 只转债\n**新增周线**：${result.inserted} 条\n**更新周线**：${result.updated} 条\n**执行耗时**：${elapsed} 秒`,
            },
          },
          { tag: 'hr' },
          {
            tag: 'note',
            elements: [
              { tag: 'plain_text', content: `数据来源: bond_snapshot → bond_weekly_kline` },
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

    const req = require('https').request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const resp = JSON.parse(data);
          if (resp.code === 0 || resp.StatusCode === 0) {
            console.log('Feishu notification sent');
            resolve(resp);
          } else {
            console.error('Feishu notification failed:', resp);
            reject(new Error(resp.msg || 'Feishu API error'));
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

async function main() {
  const startTime = Date.now();
  console.log(`[${new Date().toISOString()}] Weekly K-line Aggregation Started`);

  try {
    const dailyData = await getCurrentWeekDailyData();
    console.log(`Fetched ${dailyData.length} daily records`);

    if (dailyData.length === 0) {
      return { success: true, message: 'No data to aggregate' };
    }

    const weeklyData = await aggregateWeeklyData(dailyData);
    console.log(`Aggregated to ${weeklyData.length} weekly records`);

    const result = await upsertWeeklyData(weeklyData);
    console.log(`Upsert result: inserted=${result.inserted}, updated=${result.updated}`);

    const elapsed = Math.round((Date.now() - startTime) / 1000);
    console.log(`Elapsed: ${elapsed}s`);

    result.total = weeklyData.length;
    result.elapsed = elapsed;

    try {
      await sendFeishuNotification(result, elapsed);
    } catch (e) {
      console.error('Feishu notification error:', e.message);
    }

    return {
      success: true,
      ...result,
    };
  } catch (e) {
    console.error('Aggregation error:', e);
    throw e;
  }
}

exports.main = async (event, context) => {
  try {
    const result = await main();
    return {
      code: 0,
      message: 'success',
      data: result,
    };
  } catch (e) {
    console.error('Function error:', e);
    return {
      code: -1,
      message: e.message,
    };
  }
};