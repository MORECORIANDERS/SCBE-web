/**
 * 可转债日行情定时更新云函数
 * ============================
 * 触发时间：每天 15:10（±5分钟动态浮动，防止屏蔽）
 * 功能：
 *   1. 从新浪财经获取全量可转债当日行情
 *   2. 更新 bond_snapshot 表（当日行情）
 *   3. 更新 bond_list 表（可转债列表，增量更新）
 * 完成后通过飞书机器人通知
 */
const https = require('https');
const http = require('http');
const mysql = require('mysql2/promise');

const DB_CONFIG = {
  host: 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: 27120,
  user: 'cbreport',
  password: 'huo22QQQ',
  database: 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 15000,
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
    
    // 解析市场代码
    let market = '';
    if (item.symbol) {
      const symbolPrefix = item.symbol.slice(0, 2).toLowerCase();
      if (symbolPrefix === 'sh') market = '沪市';
      else if (symbolPrefix === 'sz') market = '深市';
      else if (symbolPrefix === 'bj') market = '北交所';
    }

    bonds.push({
      trade_date: today,
      bond_code: item.code.padStart(6, '0'),
      bond_name: item.name,
      market: market,
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

async function getDbConnection(retries = 3) {
  let lastError;
  for (let i = 0; i < retries; i++) {
    try {
      const conn = await mysql.createConnection(DB_CONFIG);
      return conn;
    } catch (e) {
      lastError = e;
      console.error(`DB connection attempt ${i + 1}/${retries} failed: ${e.message}`);
      if (i < retries - 1) {
        await new Promise(r => setTimeout(r, 5000));
      }
    }
  }
  throw lastError;
}

// 插入/更新 bond_snapshot 表
const INSERT_SNAPSHOT_SQL = `
  INSERT INTO bond_snapshot (
    trade_date, bond_code, bond_name, price, price_change, change_pct,
    volume, amount, settlement, open_price, high_price, low_price,
    buy_price, sell_price, trade_time
  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  ON DUPLICATE KEY UPDATE
    bond_name = VALUES(bond_name),
    price = VALUES(price),
    price_change = VALUES(price_change),
    change_pct = VALUES(change_pct),
    volume = VALUES(volume),
    amount = VALUES(amount),
    settlement = VALUES(settlement),
    open_price = VALUES(open_price),
    high_price = VALUES(high_price),
    low_price = VALUES(low_price),
    buy_price = VALUES(buy_price),
    sell_price = VALUES(sell_price),
    trade_time = VALUES(trade_time)
`;

async function insertSnapshot(conn, bond) {
  const [result] = await conn.execute(INSERT_SNAPSHOT_SQL, [
    bond.trade_date, bond.bond_code, bond.bond_name, bond.price, bond.price_change,
    bond.change_pct, bond.volume, bond.amount, bond.settlement, bond.open_price,
    bond.high_price, bond.low_price, bond.buy_price, bond.sell_price, bond.trade_time
  ]);
  return result.affectedRows;
}

// 插入/更新 bond_list 表
const INSERT_LIST_SQL = `
  INSERT INTO bond_list (
    bond_code, bond_name, market, is_active
  ) VALUES (?, ?, ?, 1)
  ON DUPLICATE KEY UPDATE
    bond_name = VALUES(bond_name),
    market = VALUES(market),
    is_active = VALUES(is_active),
    updated_at = CURRENT_DATE
`;

async function insertBondList(conn, bond) {
  const [result] = await conn.execute(INSERT_LIST_SQL, [
    bond.bond_code, bond.bond_name, bond.market
  ]);
  return result.affectedRows;
}

function sendFeishuNotification(
  totalCount, 
  tradeDate, 
  snapshotStats, 
  listStats, 
  elapsed, 
  sampleError
) {
  return new Promise((resolve, reject) => {
    let errorInfo = '';
    if (sampleError) {
      errorInfo = `\n**失败原因**：${sampleError}`;
    }

    const snapshotInfo = snapshotStats
      ? `\n**bond_snapshot**：新增 ${snapshotStats.inserted}，更新 ${snapshotStats.updated}，失败 ${snapshotStats.errors}`
      : '';

    const listInfo = listStats
      ? `\n**bond_list**：新增 ${listStats.inserted}，更新 ${listStats.updated}，失败 ${listStats.errors}`
      : '';

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
              content: `**触发时间**：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}\n**交易日期**：${tradeDate}\n**获取数据**：${totalCount} 条${snapshotInfo}${listInfo}${errorInfo}\n**执行耗时**：${elapsed} 秒`,
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
  const randomDelay = Math.floor(Math.random() * 109) + 12;
  console.log(`[${new Date().toISOString()}] Cloud function started. Random delay: ${randomDelay}s`);

  await new Promise(r => setTimeout(r, randomDelay * 1000));

  console.log('Fetching convertible bond data from Sina...');
  const rawItems = await getAllBonds();
  console.log(`Raw data: ${rawItems.length} records`);

  const bonds = processData(rawItems);
  console.log(`Processed: ${bonds.length} bonds (after filtering "定转")`);

  const conn = await getDbConnection();
  
  const snapshotStats = { inserted: 0, updated: 0, errors: 0 };
  const listStats = { inserted: 0, updated: 0, errors: 0 };
  let sampleError = '';
  const tradeDate = bonds.length > 0 ? bonds[0].trade_date : new Date().toISOString().slice(0, 10);

  for (const bond of bonds) {
    // 更新 bond_snapshot
    try {
      const affectedRows = await insertSnapshot(conn, bond);
      if (affectedRows === 1) snapshotStats.inserted++;
      else snapshotStats.updated++;
    } catch (e) {
      snapshotStats.errors++;
      if (!sampleError) sampleError = `snapshot: ${e.message}`;
      console.error(`Snapshot insert error for ${bond.bond_code}: ${e.message}`);
    }

    // 更新 bond_list
    try {
      const affectedRows = await insertBondList(conn, bond);
      if (affectedRows === 1) listStats.inserted++;
      else listStats.updated++;
    } catch (e) {
      listStats.errors++;
      if (!sampleError) sampleError = `list: ${e.message}`;
      console.error(`Bond list insert error for ${bond.bond_code}: ${e.message}`);
    }

    const totalProcessed = snapshotStats.inserted + snapshotStats.updated + listStats.inserted + listStats.updated;
    if (totalProcessed % 100 === 0) {
      console.log(`Progress: ${bond.bond_code} - Snapshot: ${snapshotStats.inserted}/${snapshotStats.updated}/${snapshotStats.errors}, List: ${listStats.inserted}/${listStats.updated}/${listStats.errors}`);
    }
  }

  await conn.end();

  const elapsed = Math.round((Date.now() - startTime) / 1000);
  console.log(`[${new Date().toISOString()}] Done!`);
  console.log(`  bond_snapshot: inserted=${snapshotStats.inserted}, updated=${snapshotStats.updated}, errors=${snapshotStats.errors}`);
  console.log(`  bond_list: inserted=${listStats.inserted}, updated=${listStats.updated}, errors=${listStats.errors}`);
  console.log(`  Elapsed: ${elapsed}s`);

  try {
    await sendFeishuNotification(bonds.length, tradeDate, snapshotStats, listStats, elapsed, sampleError);
  } catch (e) {
    console.error('Feishu notification error:', e.message);
  }

  return { 
    success: true, 
    total: bonds.length, 
    snapshotStats, 
    listStats,
    elapsed 
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
