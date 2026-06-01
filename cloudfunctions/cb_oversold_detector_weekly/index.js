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

async function getBondList() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [rows] = await conn.query(`
        SELECT bl.bond_code, bl.bond_name,
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

async function loadWeeklyKlineData() {
  return queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [weeklyAll] = await conn.query(`
        SELECT bond_code, trade_week,
          high_price AS high,
          low_price AS low,
          close_price AS close
        FROM bond_weekly_kline
        ORDER BY bond_code, trade_week
      `);
      return { weeklyAll };
    } finally {
      if (conn) await conn.end();
    }
  });
}

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
    const high = parseFloat(k.high), low = parseFloat(k.low), close = parseFloat(k.close);
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

function sendFeishuNotification(bonds, elapsed) {
  return new Promise((resolve, reject) => {
    if (bonds.length === 0) {
      console.log('No weekly oversold bonds found, skipping notification');
      resolve(null);
      return;
    }
    const sortedBonds = [...bonds].sort((a, b) => parseFloat(a.latest_amount || 0) - parseFloat(b.latest_amount || 0));
    let elementsContent = '';
    sortedBonds.forEach((bond, index) => {
      elementsContent += `${index + 1}. **${bond.bond_name}**（${bond.bond_code}）\n`;
      elementsContent += `   行业: ${bond.industry || '-'} | 剩余规模: ${bond.latest_amount ? parseFloat(bond.latest_amount).toFixed(2) + '亿' : '-'} | 到期: ${bond.maturity_date || '-'}\n`;
      elementsContent += `   CCI: ${bond.cci.toFixed(2)} | WR: ${bond.wr.toFixed(2)} | 价格: ${bond.price}\n\n`;
    });
    const beijingTime = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: { title: { tag: 'plain_text', content: '可转债【周线】CCI+WR双超卖提醒' }, template: 'red' },
        elements: [
          { tag: 'div', text: { tag: 'lark_md', content: `**检测时间**：${beijingTime}\n**检测周期**：周线（14周）\n**检测条件**：CCI < -100 且 WR > 80\n**满足条件**：${sortedBonds.length} 只\n**执行耗时**：${elapsed} 秒` } },
          { tag: 'hr' },
          { tag: 'div', text: { tag: 'lark_md', content: elementsContent } },
          { tag: 'hr' },
          { tag: 'note', elements: [{ tag: 'plain_text', content: `CCI周期: ${CCI_PERIOD}周 | WR周期: ${WR_PERIOD}周 | 数据源: bond_weekly_kline` }] },
        ],
      },
    });
    const url = new URL(FEISHU_WEBHOOK);
    const options = {
      hostname: url.hostname, path: url.pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
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
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function groupKlineByBond(rows, dateField, highField, lowField, closeField) {
  const byBond = {};
  for (const row of rows) {
    const code = row.bond_code;
    if (!byBond[code]) byBond[code] = [];
    const dateStr = row[dateField] instanceof Date ? row[dateField].toISOString().slice(0, 10) : String(row[dateField]);
    byBond[code].push({ trade_date: dateStr, high: row[highField], low: row[lowField], close: row[closeField] });
  }
  for (const code of Object.keys(byBond)) {
    byBond[code].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    byBond[code] = byBond[code].slice(-30);
  }
  return byBond;
}

function detectOversold(bonds, klineByBond) {
  const oversoldBonds = [];
  const allResults = [];
  let processed = 0, failed = 0;
  for (const bond of bonds) {
    try {
      const klineData = klineByBond[bond.bond_code] || null;
      if (!klineData || klineData.length < Math.max(CCI_PERIOD, WR_PERIOD)) {
        allResults.push({ bond_code: bond.bond_code, bond_name: bond.bond_name, industry: bond.industry, latest_amount: bond.latest_amount, maturity_date: bond.maturity_date, price: '', cci: null, wr: null });
        failed++; continue;
      }
      const cci = calculateCCI(klineData);
      const wr = calculateWR(klineData);
      if (cci === null || wr === null) {
        allResults.push({ bond_code: bond.bond_code, bond_name: bond.bond_name, industry: bond.industry, latest_amount: bond.latest_amount, maturity_date: bond.maturity_date, price: '', cci: null, wr: null });
        failed++; continue;
      }
      const latestKline = klineData[klineData.length - 1];
      const price = parseFloat(latestKline.close).toFixed(3);
      const result = { bond_code: bond.bond_code, bond_name: bond.bond_name, industry: bond.industry, latest_amount: bond.latest_amount, maturity_date: bond.maturity_date, price, cci: +cci.toFixed(2), wr: +wr.toFixed(2), is_oversold: cci < -100 && wr > 80 };
      allResults.push(result);
      if (result.is_oversold) {
        oversoldBonds.push({ ...result, cci, wr });
      }
      processed++;
      if (processed % 50 === 0) console.log(`Progress: ${processed}/${bonds.length}, Oversold: ${oversoldBonds.length}`);
    } catch (e) {
      console.error(`Error processing ${bond.bond_code}: ${e.message}`);
      allResults.push({ bond_code: bond.bond_code, bond_name: bond.bond_name, industry: bond.industry, latest_amount: bond.latest_amount, maturity_date: bond.maturity_date, price: '', cci: null, wr: null });
      failed++;
    }
  }
  return { oversoldBonds, allResults, processed, failed };
}

async function saveStrategyResults(results, tradeDate) {
  if (!results || results.length === 0) return;
  let conn;
  try {
    conn = await mysql.createConnection(DB_CONFIG);
    const batchSize = 100;
    for (let i = 0; i < results.length; i += batchSize) {
      const batch = results.slice(i, i + batchSize);
      const placeholders = batch.map(() => '(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())').join(',\n');
      const values = [];
      for (const r of batch) {
        values.push(tradeDate);
        values.push('weekly');
        values.push(r.bond_code);
        values.push(r.bond_name || '');
        values.push(r.price ? parseFloat(r.price) : 0);
        values.push(null);
        values.push(r.industry || '');
        values.push(r.latest_amount ? parseFloat(r.latest_amount) : 0);
        values.push(r.maturity_date || '');
        values.push(r.cci);
        values.push(r.wr != null ? Math.round(r.wr * 100) / 100 : null);
        values.push(r.is_oversold ? 1 : 0);
      }
      const sql = `INSERT INTO daily_strategy
        (trade_date, strategy_type, bond_code, bond_name, price, change_pct, industry, remain_scale, maturity_date, cci, wr, is_oversold, created_at, updated_at)
        VALUES ${placeholders}
        ON DUPLICATE KEY UPDATE
          bond_name = VALUES(bond_name), price = VALUES(price), industry = VALUES(industry),
          remain_scale = VALUES(remain_scale), maturity_date = VALUES(maturity_date),
          cci = VALUES(cci), wr = VALUES(wr), is_oversold = VALUES(is_oversold), updated_at = NOW()`;
      await conn.query(sql, values);
      console.log(`Saved batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(results.length / batchSize)} (${batch.length} records)`);
    }
    console.log(`Successfully saved ${results.length} records to daily_strategy (weekly)`);
  } catch (e) {
    console.error('Error saving strategy results:', e.message);
  } finally {
    if (conn) await conn.end();
  }
}

let startTime;

exports.main = async (event, context) => {
  startTime = Date.now();
  try {
    console.log(`[${new Date().toISOString()}] Weekly CCI+WR Oversold Detection Started`);

    const bonds = await getBondList();
    console.log(`Found ${bonds.length} active bonds`);

    const { weeklyAll } = await loadWeeklyKlineData();
    const klineByBond = groupKlineByBond(weeklyAll, 'trade_week', 'high', 'low', 'close');

    const { oversoldBonds, allResults, processed, failed } = detectOversold(bonds, klineByBond);
    const elapsed = Math.round((Date.now() - startTime) / 1000);

    console.log(`Weekly Detection: Processed ${processed}, Failed ${failed}, Oversold ${oversoldBonds.length}`);

    const todayStr = new Date().toISOString().slice(0, 10);
    await saveStrategyResults(allResults, todayStr);

    try { await sendFeishuNotification(oversoldBonds, elapsed); } catch (e) { console.error('Feishu error:', e.message); }

    return {
      success: true, total: bonds.length, processed, failed,
      oversoldCount: oversoldBonds.length, oversoldBonds: oversoldBonds.slice(0, 20), elapsed,
    };
  } catch (e) {
    console.error('Function error:', e);
    return { code: -1, message: e.message };
  }
};
