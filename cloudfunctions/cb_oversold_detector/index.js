/**
 * 可转债CCI+WR双超卖检测云函数
 * =================================
 * 触发时间：每天 19:00（收盘后）
 * 功能：
 *   1. 从数据库 bond_snapshot 表获取可转债历史行情
 *   2. 计算 CCI 和 WR 指标
 *   3. 筛选满足双超卖条件的可转债（CCI < -100 且 WR > 80）
 *   4. 通过飞书机器人通知
 * 
 * 指标计算（参考通达信公式）：
 *   CCI = (TYP - MA(TYP, 14)) / (0.015 * AVEDEV(TYP, 14))
 *   WR = (HHV(HIGH, 14) - CLOSE) / (HHV(HIGH, 14) - LLV(LOW, 14)) * 100
 * 
 * 超卖条件：
 *   CCI < -100 且 WR > 80
 */

const https = require('https');

// 配置
const DB_CONFIG = {
  host: 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: 27120,
  user: 'cbreport',
  password: 'huo22QQQ',
  database: 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 15000,
};

// 指标参数
const CCI_PERIOD = 14;
const WR_PERIOD = 14;

// 飞书Webhook
const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

/**
 * 从数据库获取可转债历史行情数据
 */
async function getBondKlineData(bondCode, days = 30) {
  const mysql = require('mysql2/promise');
  let conn;
  try {
    conn = await mysql.createConnection(DB_CONFIG);
    
    // 查询最近N天的行情数据
    const [rows] = await conn.execute(`
      SELECT trade_date, high_price, low_price, price 
      FROM bond_snapshot 
      WHERE bond_code = ? 
      ORDER BY trade_date DESC 
      LIMIT ?
    `, [bondCode, days]);

    if (!rows || rows.length === 0) {
      return null;
    }

    // 转换格式并按日期升序排列
    const klineData = rows.reverse().map(row => ({
      trade_date: row.trade_date,
      high: row.high_price,
      low: row.low_price,
      close: row.price,
    }));

    return klineData;
  } catch (e) {
    console.error(`Error fetching kline for ${bondCode}: ${e.message}`);
    return null;
  } finally {
    if (conn) await conn.end();
  }
}

/**
 * 从数据库获取可转债列表
 */
async function getBondList() {
  const mysql = require('mysql2/promise');
  let conn;
  try {
    conn = await mysql.createConnection(DB_CONFIG);
    const [rows] = await conn.execute(`
      SELECT bond_code, bond_name 
      FROM bond_list 
      WHERE is_active = 1 
      ORDER BY bond_code
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
 * 计算简单移动平均
 */
function calculateMA(data, period) {
  if (data.length < period) return null;
  const sum = data.slice(-period).reduce((acc, val) => acc + val, 0);
  return sum / period;
}

/**
 * 计算平均绝对偏差 (AVEDEV)
 */
function calculateAVEDEV(data, period, mean) {
  if (data.length < period) return null;
  const recentData = data.slice(-period);
  const sum = recentData.reduce((acc, val) => acc + Math.abs(val - mean), 0);
  return sum / period;
}

/**
 * 计算CCI指标
 * CCI = (TYP - MA(TYP, N)) / (0.015 * AVEDEV(TYP, N))
 */
function calculateCCI(klineData) {
  if (!klineData || klineData.length < CCI_PERIOD) return null;

  // 计算TYP = (HIGH + LOW + CLOSE) / 3
  const typValues = klineData.map(k => (parseFloat(k.high) + parseFloat(k.low) + parseFloat(k.close)) / 3);

  // 计算TYP的移动平均
  const maTyp = calculateMA(typValues, CCI_PERIOD);
  if (maTyp === null) return null;

  // 计算平均绝对偏差
  const avedevTyp = calculateAVEDEV(typValues, CCI_PERIOD, maTyp);
  if (avedevTyp === null || avedevTyp === 0) return null;

  // 计算CCI
  const latestTyp = typValues[typValues.length - 1];
  const cci = (latestTyp - maTyp) / (0.015 * avedevTyp);

  return cci;
}

/**
 * 计算WR指标
 * WR = (HHV(HIGH, N) - CLOSE) / (HHV(HIGH, N) - LLV(LOW, N)) * 100
 */
function calculateWR(klineData) {
  if (!klineData || klineData.length < WR_PERIOD) return null;

  const recentData = klineData.slice(-WR_PERIOD);
  const highPrices = recentData.map(k => parseFloat(k.high));
  const lowPrices = recentData.map(k => parseFloat(k.low));
  const closePrice = parseFloat(klineData[klineData.length - 1].close);

  const hhv = Math.max(...highPrices);
  const llv = Math.min(...lowPrices);

  if (hhv === llv) return null;

  const wr = ((hhv - closePrice) / (hhv - llv)) * 100;
  return wr;
}

/**
 * 发送飞书通知
 */
function sendFeishuNotification(bonds, elapsed) {
  return new Promise((resolve, reject) => {
    if (bonds.length === 0) {
      console.log('No oversold bonds found, skipping notification');
      resolve(null);
      return;
    }

    // 按CCI升序排序（最超卖的在前）
    const sortedBonds = [...bonds].sort((a, b) => a.cci - b.cci);

    // 构建飞书卡片消息
    let elementsContent = '';

    sortedBonds.forEach((bond, index) => {
      if (index < 20) {  // 最多显示20条
        elementsContent += `${index + 1}. **${bond.bond_name}** (${bond.bond_code})\n`;
        elementsContent += `   价格: ${bond.price} | CCI: ${bond.cci.toFixed(2)} | WR: ${bond.wr.toFixed(2)}\n\n`;
      }
    });

    if (sortedBonds.length > 20) {
      elementsContent += `... \n（共 ${sortedBonds.length} 只满足条件，仅显示前20只）\n`;
    }

    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: '📊 可转债CCI+WR双超卖提醒' },
          template: 'red',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**检测时间**：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}\n**检测条件**：CCI < -100 且 WR > 80\n**满足条件**：${sortedBonds.length} 只\n**执行耗时**：${elapsed} 秒`,
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
                content: `CCI周期: ${CCI_PERIOD}日 | WR周期: ${WR_PERIOD}日 | 数据来源: CloudBase bond_snapshot`,
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

  // 1. 获取可转债列表
  console.log('Fetching bond list from database...');
  const bonds = await getBondList();
  console.log(`Found ${bonds.length} active bonds`);

  const oversoldBonds = [];
  let processed = 0;
  let failed = 0;

  console.log('Calculating CCI and WR for each bond...');

  // 2. 遍历每只转债，计算CCI和WR
  for (const bond of bonds) {
    try {
      // 从数据库获取历史行情数据（最近30天）
      const klineData = await getBondKlineData(bond.bond_code, 30);

      if (!klineData || klineData.length < Math.max(CCI_PERIOD, WR_PERIOD)) {
        failed++;
        continue;
      }

      // 计算CCI和WR
      const cci = calculateCCI(klineData);
      const wr = calculateWR(klineData);

      if (cci === null || wr === null) {
        failed++;
        continue;
      }

      // 检查是否满足双超卖条件
      const isOversold = cci < -100 && wr > 80;

      if (isOversold) {
        const latestKline = klineData[klineData.length - 1];
        oversoldBonds.push({
          bond_code: bond.bond_code,
          bond_name: bond.bond_name,
          price: parseFloat(latestKline.close).toFixed(3),
          cci: cci,
          wr: wr,
        });
      }

      processed++;

      // 每50个打印一次进度
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

  // 3. 发送飞书通知
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
