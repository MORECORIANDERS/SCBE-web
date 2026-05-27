/**
 * 可转债周线数据初始化云函数
 * =================================
 * 功能：
 *   1. 从 bond_kline 读取所有历史日线数据（2018-09-04 ~ 2026-05-20）
 *   2. 按转债代码和周聚合为周线数据
 *   3. 写入 bond_weekly_kline 表
 *
 * 注意：此函数仅需运行一次，用于初始化历史周线数据
 */

const mysql = require('mysql2/promise');

const DB_CONFIG = {
  host: process.env.DB_HOST || 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: parseInt(process.env.DB_PORT || '27120'),
  user: process.env.DB_USER || 'cbreport',
  password: process.env.DB_PASSWORD || 'huo22QQQ',
  database: process.env.DB_NAME || 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 60000,
};

const BATCH_SIZE = 500;

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

async function fetchHistoricalDailyData(pool) {
  let conn;
  try {
    conn = await pool.getConnection();

    console.log('Fetching historical daily data from bond_kline...');

    const [rows] = await conn.query(`
      SELECT
        SUBSTRING(symbol, 3) AS bond_code,
        trade_date,
        \`open\`,
        high,
        low,
        \`close\`,
        volume
      FROM bond_kline
      WHERE trade_date IS NOT NULL
        AND SUBSTRING(symbol, 3) IS NOT NULL
      ORDER BY bond_code, trade_date
    `);

    console.log(`Fetched ${rows.length} historical daily records`);
    return rows;
  } finally {
    if (conn) conn.release();
  }
}

function aggregateToWeekly(dailyData) {
  const weeklyMap = new Map();

  for (const row of dailyData) {
    if (!row.open || !row.high || !row.low || !row.close) {
      continue;
    }

    const code = row.bond_code;
    if (!code) continue;

    const tradeDate = new Date(row.trade_date);
    const monday = getMondayOfWeek(tradeDate);
    const weekKey = formatDate(monday);

    const key = `${code}_${weekKey}`;

    if (!weeklyMap.has(key)) {
      weeklyMap.set(key, {
        bond_code: code,
        trade_week: weekKey,
        open_price: parseFloat(row.open),
        high_price: parseFloat(row.high),
        low_price: parseFloat(row.low),
        close_price: parseFloat(row.close),
        volume: BigInt(row.volume || 0),
      });
    } else {
      const existing = weeklyMap.get(key);
      existing.high_price = Math.max(existing.high_price, parseFloat(row.high));
      existing.low_price = Math.min(existing.low_price, parseFloat(row.low));
      existing.close_price = parseFloat(row.close);
      existing.volume += BigInt(row.volume || 0);
    }
  }

  return Array.from(weeklyMap.values());
}

async function upsertWeeklyBatch(pool, weeklyData) {
  if (weeklyData.length === 0) {
    return { inserted: 0, updated: 0 };
  }

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
  }
}

async function main() {
  const startTime = Date.now();
  console.log(`[${new Date().toISOString()}] Weekly K-line Initialization Started`);

  const pool = mysql.createPool(DB_CONFIG);

  try {
    const dailyData = await fetchHistoricalDailyData(pool);
    console.log(`Processing ${dailyData.length} daily records...`);

    const weeklyData = aggregateToWeekly(dailyData);
    console.log(`Aggregated to ${weeklyData.length} weekly records`);

    let totalInserted = 0;
    let totalUpdated = 0;

    for (let i = 0; i < weeklyData.length; i += BATCH_SIZE) {
      const batch = weeklyData.slice(i, i + BATCH_SIZE);
      const result = await upsertWeeklyBatch(pool, batch);
      totalInserted += result.inserted;
      totalUpdated += result.updated;

      console.log(`Progress: ${Math.min(i + BATCH_SIZE, weeklyData.length)}/${weeklyData.length}, Inserted: ${totalInserted}, Updated: ${totalUpdated}`);
    }

    const elapsed = Math.round((Date.now() - startTime) / 1000);

    console.log(`[${new Date().toISOString()}] Initialization completed`);
    console.log(`  Total weekly records: ${weeklyData.length}`);
    console.log(`  Inserted: ${totalInserted}`);
    console.log(`  Updated: ${totalUpdated}`);
    console.log(`  Elapsed: ${elapsed}s`);

    return {
      success: true,
      totalWeekly: weeklyData.length,
      inserted: totalInserted,
      updated: totalUpdated,
      elapsed: elapsed,
    };
  } finally {
    await pool.end();
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