/**
 * 可转债周线CCI+WR双超卖检测云函数
 * =================================
 * 触发时间：每天 15:40
 * 功能：
 *   1. 从 bond_weekly_kline 获取最近14周数据
 *   2. 计算周线 CCI 和 WR 指标
 *   3. 筛选满足双超卖条件的可转债（CCI < -100 且 WR > 80）
 *   4. 通过飞书机器人发送详细卡片
 *
 * 指标计算（参考通达信公式）：
 *   CCI = (TYP - MA(TYP, 14)) / (0.015 * AVEDEV(TYP, 14))
 *   WR = (HHV(HIGH, 14) - CLOSE) / (HHV(HIGH, 14) - LLV(LOW, 14)) * 100
 *
 * 超卖条件：
 *   CCI < -100 且 WR > 80
 */

const https = require('https');

const DB_CONFIG = {
  host: 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: 27120,
  user: 'cbreport',
  password: 'huo22QQQ',
  database: 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 30000,
};

const CCI_PERIOD = 14;
const WR_PERIOD = 14;

const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

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
    const mysql = require('mysql2/promise');
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

function calculateMA(data, period) {
  if (data.length < period) return null;
  const sum = data.slice(-period).reduce((acc, val) => acc + val, 0);
  return sum / period;
}

function calculateAVEDEV(data, period, mean) {
  if (data.length < period) return null;
  const recentData = data.slice(-period);
  const sum = recentData.reduce((acc, val) => acc + Math.abs(val - mean), 0);
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

    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: '可转债【周线】CCI+WR双超卖提醒' },
          template: 'red',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**检测时间**：${beijingTime}\n**检测周期**：周线（14周）\n**检测条件**：CCI < -100 且 WR > 80\n**满足条件**：${sortedBonds.length} 只\n**执行耗时**：${elapsed} 秒`,
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
                content: `CCI周期: ${CCI_PERIOD}周 | WR周期: ${WR_PERIOD}周 | 数据源: bond_weekly_kline`,
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

async function main() {
  const startTime = Date.now();
  console.log(`[${new Date().toISOString()}] Weekly CCI+WR Oversold Detection Started`);

  console.log('Fetching bond list from database...');
  const bonds = await getBondList();
  console.log(`Found ${bonds.length} active bonds`);

  const mysql = require('mysql2/promise');

  const { weeklyAll } = await queryWithRetry(async () => {
    let conn;
    try {
      conn = await mysql.createConnection(DB_CONFIG);
      const [weeklyAll] = await conn.query(`
        SELECT
          bond_code,
          trade_week,
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

    const weeklyByBond = {};
    for (const row of weeklyAll) {
      const code = row.bond_code;
      if (!weeklyByBond[code]) {
        weeklyByBond[code] = [];
      }
      const dateStr = row.trade_week instanceof Date
        ? row.trade_week.toISOString().slice(0, 10)
        : String(row.trade_week);
      weeklyByBond[code].push({
        trade_date: dateStr,
        high: row.high,
        low: row.low,
        close: row.close,
      });
    }

    for (const code of Object.keys(weeklyByBond)) {
      const sorted = weeklyByBond[code].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
      weeklyByBond[code] = sorted.slice(-30);
    }

    const oversoldBonds = [];
    let processed = 0;
    let failed = 0;

    for (const bond of bonds) {
      try {
        const klineData = weeklyByBond[bond.bond_code] || null;

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
            cci: cci,
            wr: wr,
          });
        }

        processed++;

        if (processed % 50 === 0) {
          console.log(`Progress: ${processed}/${bonds.length}, Weekly Oversold: ${oversoldBonds.length}`);
        }
      } catch (e) {
        console.error(`Error processing ${bond.bond_code}: ${e.message}`);
        failed++;
      }
    }

    const elapsed = Math.round((Date.now() - startTime) / 1000);

    console.log(`[${new Date().toISOString()}] Weekly Detection completed`);
    console.log(`  Processed: ${processed}, Failed: ${failed}`);
    console.log(`  Weekly oversold bonds found: ${oversoldBonds.length}`);
    console.log(`  Elapsed: ${elapsed}s`);

    try {
      await sendFeishuNotification(oversoldBonds, elapsed);
    } catch (e) {
      console.error('Feishu notification error:', e.message);
    }

    return {
      success: true,
      total: bonds.length,
      processed: processed,
      failed: failed,
      oversoldCount: oversoldBonds.length,
      oversoldBonds: oversoldBonds.slice(0, 20),
      elapsed: elapsed,
    };
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