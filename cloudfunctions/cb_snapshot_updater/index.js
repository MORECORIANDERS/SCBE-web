/**
 * 可转债日行情定时更新云函数
 * ============================
 * 触发时间：每天 15:10（±5分钟动态浮动，防止屏蔽）
 * 功能：从新浪财经获取全量可转债当日行情，增量追加到 bond_snapshot 表
 * 完成后通过飞书机器人通知
 */
const https = require('https');
const http = require('http');
const mysql = require('mysql2');

const DB_CONFIG = {
  host: 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: 27120,
  user: 'cbreport',
  password: 'huo22QQQ',
  database: 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
};

const API_URL = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData';

const PARAMS = {
  page: 1,
  num: 50,
  sort: 'symbol',
  asc: 1,
  node: 'hskzz_z',
  symbol: '',
  _s_r_a: 'page',
};

const FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

function httpGet(url, encoding = 'gbk') {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const options = {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://vip.stock.finance.sina.com.cn/mkt/',
        'Accept-Charset': encoding,
      },
      timeout: 30000,
    };
    client.get(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject).on('timeout', () => reject(new Error('Request timeout')));
  });
}

function fetchSinaData(page) {
  const qs = new URLSearchParams({ ...PARAMS, page });
  return httpGet(`${API_URL}?${qs}`, 'gbk');
}

async function getAllBonds() {
  const allData = [];
  let page = 1;
  while (true) {
    console.log(`Fetching page ${page}...`);
    const text = await fetchSinaData(page);
    if (!text || text.trim() === '') break;
    try {
      const items = JSON.parse(text);
      if (!items || items.length === 0) break;
      allData.push(...items);
      page++;
      await new Promise(r => setTimeout(r, 300));
    } catch (e) {
      console.error(`Parse error on page ${page}:`, e.message);
      break;
    }
  }
  return allData;
}

function processData(items) {
  const today = new Date().toISOString().slice(0, 10);
  const bonds = [];

  for (const item of items) {
    if (item.name && item.name.includes('定转')) continue;
    bonds.push({
      trade_date: today,
      bond_code: item.code.padStart(6, '0'),
      bond_name: item.name,
      price: parseFloat(item.trade) || null,
      price_change: parseFloat(item.pricechange) || null,
      change_pct: parseFloat(item.changepercent) || null,
      volume: parseInt(item.volume) || null,
      amount: parseFloat(item.amount) || null,
      settlement: parseFloat(item.settlement) || null,
      open_price: parseFloat(item.open) || null,
      high_price: parseFloat(item.high) || null,
      low_price: parseFloat(item.low) || null,
      buy_price: parseFloat(item.buy) || null,
      sell_price: parseFloat(item.sell) || null,
      trade_time: item.ticktime || null,
    });
  }
  return bonds;
}

function getDbConnection() {
  return mysql.createConnection(DB_CONFIG);
}

async function insertSnapshot(conn, bond) {
  const sql = `
    INSERT INTO bond_snapshot (
      trade_date, bond_code, bond_name, price, price_change, change_pct,
      volume, amount, settlement, open_price, high_price, low_price,
      buy_price, sell_price, trade_time
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `;
  return new Promise((resolve, reject) => {
    conn.query(sql, [
      bond.trade_date, bond.bond_code, bond.bond_name, bond.price, bond.price_change,
      bond.change_pct, bond.volume, bond.amount, bond.settlement, bond.open_price,
      bond.high_price, bond.low_price, bond.buy_price, bond.sell_price, bond.trade_time
    ], (err, result) => {
      if (err) reject(err);
      else resolve(result);
    });
  });
}

function sendFeishuNotification(count, tradeDate, tableName, successCount, errorCount, elapsed, sampleError) {
  return new Promise((resolve, reject) => {
    let errorInfo = '';
    if (errorCount > 0 && sampleError) {
      errorInfo = `\n**失败原因**：${sampleError}`;
    }
    const payload = JSON.stringify({
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: '📈 可转债行情更新完成' },
          template: 'blue',
        },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**触发时间**：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}\n**交易日期**：${tradeDate}\n**获取数据**：${count} 条\n**成功写入**：${successCount} 条\n**失败数量**：${errorCount} 条${errorInfo}\n**目标表**：${tableName}\n**执行耗时**：${elapsed} 秒`,
            },
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
  const randomDelay = Math.floor(Math.random() * 241) + 60;
  console.log(`[${new Date().toISOString()}] Cloud function started. Random delay: ${randomDelay}s`);

  await new Promise(r => setTimeout(r, randomDelay * 1000));

  console.log('Fetching convertible bond data from Sina...');
  const rawItems = await getAllBonds();
  console.log(`Raw data: ${rawItems.length} records`);

  const bonds = processData(rawItems);
  console.log(`Processed: ${bonds.length} bonds (after filtering "定转")`);

  const conn = getDbConnection();
  let successCount = 0;
  let errorCount = 0;
  let sampleError = '';
  const tradeDate = bonds.length > 0 ? bonds[0].trade_date : new Date().toISOString().slice(0, 10);

  for (const bond of bonds) {
    try {
      await insertSnapshot(conn, bond);
      successCount++;
      if (successCount % 50 === 0) {
        console.log(`Progress: ${successCount}/${bonds.length}`);
      }
    } catch (e) {
      errorCount++;
      if (!sampleError) sampleError = e.message;
      console.error(`Insert error for ${bond.bond_code}: ${e.message}`);
    }
  }

  conn.end();

  const elapsed = Math.round((Date.now() - startTime) / 1000);
  console.log(`[${new Date().toISOString()}] Done! Success: ${successCount}, Errors: ${errorCount}, Elapsed: ${elapsed}s`);

  try {
    await sendFeishuNotification(bonds.length, tradeDate, 'bond_snapshot', successCount, errorCount, elapsed, sampleError);
  } catch (e) {
    console.error('Feishu notification error:', e.message);
  }

  return { success: true, total: bonds.length, successCount, errorCount, elapsed };
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