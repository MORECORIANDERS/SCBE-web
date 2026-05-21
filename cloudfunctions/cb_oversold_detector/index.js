/**
 * 可转债CCI+WR双超卖检测云函数
 * =================================
 * 触发时间：每天 15:30（收盘后）
 * 功能：
 *   1. 从 bond_kline（静态历史库，截至2026-05-20）获取历史K线
 *   2. 从 bond_snapshot（每日新增，2026-05-21起）获取最新行情
 *   3. 两者按 trade_date 去重合并，取最近30天
 *   4. 计算 CCI 和 WR 指标
 *   5. 筛选满足双超卖条件的可转债（CCI < -100 且 WR > 80）
 *   6. 通过飞书机器人发送详细卡片（含行业、剩余规模、到期日期）
 *
 * 数据源策略：
 *   bond_kline.symbol 格式为 'sh110072'，截取后6位匹配 bond_code
 *   - bond_kline：2018-09-04 ~ 2026-05-20（静态历史库，基本不更新）
 *   - bond_snapshot：2026-05-21 起（每日新增行情快照）
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
  connectTimeout: 15000,
};

const CCI_PERIOD = 14;
const WR_PERIOD = 14;
const KLINE_CUTOFF_DATE = '2026-05-20';

const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

/**
 * 获取活跃可转债列表（含行业、剩余规模、到期日期）
 */
async function getBondList() {
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
  } catch (e) {
    console.error('Database query error:', e.message);
    return [];
  } finally {
    if (conn) await conn.end();
  }
}

/**
 * 数据来源说明：
 * bond_kline.symbol 格式为 'sh110072'，截取后6位匹配 bond_code
 * - bond_kline: 静态历史库（2018-09-04 ~ 2026-05-20），27万条
 * - bond_snapshot: 每日新增快照（2026-05-21起），覆盖当日数据
 * - 两者按 trade_date 去重合并，取最近30天
 */

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
      console.log('No oversold bonds found, skipping notification');
      resolve(null);
      return;
    }

    const sortedBonds = [...bonds].sort((a, b) => a.cci - b.cci);

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
          title: { tag: 'plain_text', content: '可转债CCI+WR双超卖提醒' },
          template: 'red',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**检测时间**：${beijingTime}\n**检测条件**：CCI < -100 且 WR > 80\n**满足条件**：${sortedBonds.length} 只\n**执行耗时**：${elapsed} 秒`,
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
                content: `CCI周期: ${CCI_PERIOD}日 | WR周期: ${WR_PERIOD}日 | 数据源: bond_kline + bond_snapshot + bond_static`,
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
  console.log(`[${new Date().toISOString()}] CCI+WR Oversold Detection Started`);

  console.log('Fetching bond list from database...');
  const bonds = await getBondList();
  console.log(`Found ${bonds.length} active bonds`);

  console.log('Batch loading kline data from bond_kline...');
  const mysql = require('mysql2/promise');
  let conn;
  try {
    conn = await mysql.createConnection(DB_CONFIG);

    const [klineAll] = await conn.query(`
      SELECT SUBSTRING(symbol, 3) AS bond_code, trade_date, high, low, \`close\`
      FROM bond_kline
      WHERE trade_date >= DATE_SUB('${KLINE_CUTOFF_DATE}', INTERVAL 30 DAY)
        AND trade_date <= '${KLINE_CUTOFF_DATE}'
    `);

    const [snapshotAll] = await conn.query(`
      SELECT bond_code, trade_date, high_price, low_price, price
      FROM bond_snapshot
      WHERE trade_date > '${KLINE_CUTOFF_DATE}'
    `);

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

    for (const code of Object.keys(rawByBond)) {
      const dayMap = rawByBond[code];
      const sorted = Object.values(dayMap).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
      rawByBond[code] = sorted.slice(-30);
    }

    const oversoldBonds = [];
    let processed = 0;
    let failed = 0;

    for (const bond of bonds) {
      try {
        const klineData = rawByBond[bond.bond_code] || null;

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
          console.log(`Progress: ${processed}/${bonds.length}, Oversold: ${oversoldBonds.length}`);
        }
      } catch (e) {
        console.error(`Error processing ${bond.bond_code}: ${e.message}`);
        failed++;
      }
    }

    const elapsed = Math.round((Date.now() - startTime) / 1000);

    console.log(`[${new Date().toISOString()}] Detection completed`);
    console.log(`  Processed: ${processed}, Failed: ${failed}`);
    console.log(`  Oversold bonds found: ${oversoldBonds.length}`);
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
  } finally {
    if (conn) await conn.end();
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
