/**
 * 可转债日行情定时更新云函数
 * ============================
 * 触发时间：每天 15:10（周一至周五，±5分钟动态浮动，防止屏蔽）
 * 功能：
 *   1. 从新浪财经获取全量可转债当日行情
 *   2. 更新 bond_snapshot 表（当日行情）
 *   3. 更新 bond_list 表（可转债列表，增量更新）
 *   4. 检测新增可转债，自动采集详情报 bond_detail 表
 * 完成后通过飞书机器人通知
 *
 * v2.1 - 2026-05-26
 *   - 增加"定01"可交换债过滤，避免无效数据入库
 *   - 新增退市债券自动标记（is_active=0），基于新浪接口返回列表比对
 *   - 改用 CloudBase 官方推荐的 executeWithRetry 重试模式
 *     (每次操作独立获取/释放连接，连接错误自动重试，指数退避)
 *
 * v2.0 - 2026-05-23
 *   - 改用连接池，增加自动重连机制
 *   - 增加交易日判断（周末跳过执行）
 *   - 增加 bond_detail 采集
 */
const https = require('https');
const http = require('http');
const mysql = require('mysql2/promise');

const DB_CONFIG = {
  host: process.env.DB_HOST || 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: parseInt(process.env.DB_PORT || '27120'),
  user: process.env.DB_USER || 'cbreport',
  password: process.env.DB_PASSWORD || 'huo22QQQ',
  database: process.env.DB_NAME || 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 30000,
  insecureAuth: true,
};

// 使用连接池，保持心跳防止空闲断开
const pool = mysql.createPool({
  ...DB_CONFIG,
  connectionLimit: 3,
  waitForConnections: true,
  enableKeepAlive: true,
  keepAliveInitialDelay: 10000,
});

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

const FEISHU_WEBHOOK = process.env.FEISHU_WEBHOOK || 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5';

const SINA_BOND_DETAIL_API = 'https://quotes.sina.com.cn/bd/api/openapi.php/BondService2021.getBondInfo';

const INSERT_BOND_DETAIL_SQL = `
  INSERT INTO bond_detail (
    bond_code, name, stock_code, stock_name,
    conversion_start_date, conversion_end_date,
    force_redeem_price, redeem_lock_period, latest_redeem_price,
    put_option_price, put_option_lock, latest_put_price, latest_put_date,
    revise_price, conversion_price,
    issue_price, issue_amount, remain_scale,
    interest_start_date, maturity_date, interest_method,
    maturity_redeem_price, rating, full_name, short_name, bond_life,
    interest_note, raw_data
  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  ON DUPLICATE KEY UPDATE
    name = VALUES(name), stock_code = VALUES(stock_code), stock_name = VALUES(stock_name),
    conversion_start_date = VALUES(conversion_start_date), conversion_end_date = VALUES(conversion_end_date),
    force_redeem_price = VALUES(force_redeem_price), redeem_lock_period = VALUES(redeem_lock_period),
    latest_redeem_price = VALUES(latest_redeem_price),
    put_option_price = VALUES(put_option_price), put_option_lock = VALUES(put_option_lock),
    latest_put_price = VALUES(latest_put_price), latest_put_date = VALUES(latest_put_date),
    revise_price = VALUES(revise_price), conversion_price = VALUES(conversion_price),
    issue_price = VALUES(issue_price), issue_amount = VALUES(issue_amount),
    remain_scale = VALUES(remain_scale),
    interest_start_date = VALUES(interest_start_date), maturity_date = VALUES(maturity_date),
    interest_method = VALUES(interest_method), maturity_redeem_price = VALUES(maturity_redeem_price),
    rating = VALUES(rating), full_name = VALUES(full_name), short_name = VALUES(short_name),
    bond_life = VALUES(bond_life), interest_note = VALUES(interest_note), raw_data = VALUES(raw_data)
`;

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
    if (item.name && (item.name.includes('定转') || item.name.includes('定01'))) continue;

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

function isRetryableError(e) {
  const retryableCodes = [
    'ECONNRESET',
    'PROTOCOL_CONNECTION_LOST',
    'ETIMEDOUT',
  ];
  return retryableCodes.includes(e.code)
    || (e.message && (
      e.message.includes('closed state')
      || e.message.includes('Cannot enqueue')
      || e.message.includes('Malformed communication packet')
    ));
}

async function executeWithRetry(operation, maxRetries = 3) {
  let lastError;
  for (let i = 0; i < maxRetries; i++) {
    let conn;
    try {
      conn = await pool.getConnection();
      const result = await operation(conn);
      return result;
    } catch (e) {
      lastError = e;
      if (isRetryableError(e) && i < maxRetries - 1) {
        console.error(`Retryable error (attempt ${i + 1}/${maxRetries}): ${e.message}`);
        const delay = Math.pow(2, i) * 1000;
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw e;
    } finally {
      if (conn) {
        try { conn.release(); } catch (_) {}
      }
    }
  }
  throw lastError;
}

// 批量插入/更新 bond_snapshot 表（mysql2 VALUES ? 语法）
const SNAPSHOT_BATCH_SQL = `
  INSERT INTO bond_snapshot (
    trade_date, bond_code, bond_name, price, price_change, change_pct,
    volume, amount, settlement, open_price, high_price, low_price,
    buy_price, sell_price, trade_time
  ) VALUES ?
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

// 批量插入/更新 bond_list 表
const LIST_BATCH_SQL = `
  INSERT INTO bond_list (bond_code, bond_name, market, is_active)
  VALUES ?
  ON DUPLICATE KEY UPDATE
    bond_name = VALUES(bond_name),
    market = VALUES(market),
    is_active = VALUES(is_active),
    updated_at = CURRENT_DATE
`;

const BATCH_SIZE = 50;

function parseBondInfo(data, bondCode, bondName) {
  const conver = data.converInfo || {};
  const base = data.baseInfo || {};

  return {
    bond_code: bondCode,
    name: base.BondSName || bondName || '',
    stock_code: conver.SKCODE || '',
    stock_name: conver.SKSENAME || '',
    conversion_start_date: conver.ZGQSR || '',
    conversion_end_date: conver.ZGJZR || '',
    force_redeem_price: parseFloat(conver.QSCFPrice) || null,
    redeem_lock_period: conver.QSQSR || '',
    latest_redeem_price: conver.ZXSHPrice || null,
    put_option_price: parseFloat(conver.HSCFPrice) || null,
    put_option_lock: conver.HSQSR || '',
    latest_put_price: parseFloat(conver.ZXHSPrice) || null,
    latest_put_date: conver.ZXHSR || '',
    revise_price: parseFloat(conver.XZCFPrice) || null,
    conversion_price: parseFloat(conver.DQZGPrice) || null,
    issue_price: parseFloat(base.IssuePrice) || null,
    issue_amount: parseFloat(base.lenders) || null,
    remain_scale: conver.SYGM || '',
    interest_start_date: conver.QXSR || '',
    maturity_date: conver.DQR || '',
    interest_method: conver.FXFS || '',
    maturity_redeem_price: parseFloat(conver.DQSHPrice) || null,
    rating: base.BondRate || '',
    full_name: base.BondFullName || '',
    short_name: base.BondSName || '',
    bond_life: parseFloat(base.yearlimit) || null,
    interest_note: conver.lixiInfo || '',
  };
}

async function fetchBondDetail(bondCode, bondName) {
  const url = `${SINA_BOND_DETAIL_API}?symbol=sh${bondCode}&callback=hqccall_bondinfo`;
  const text = await httpGet(url, 'utf-8');
  if (!text || text.trim() === '') return null;

  let data;
  try {
    const jsonStr = text.replace(/^[a-zA-Z_]\w*\(/, '').replace(/\);?\s*$/, '').trim();
    data = JSON.parse(jsonStr);
  } catch (e) {
    const match = text.match(/\{[\s\S]*\}/);
    if (match) {
      try { data = JSON.parse(match[0]); } catch (e2) { return null; }
    } else {
      return null;
    }
  }

  if (!data || !data.result || !data.result.data) return null;
  return parseBondInfo(data.result.data, bondCode, bondName);
}

async function upsertBondDetail(conn, info) {
  await conn.query(INSERT_BOND_DETAIL_SQL, [
    info.bond_code, info.name, info.stock_code, info.stock_name,
    info.conversion_start_date, info.conversion_end_date,
    info.force_redeem_price, info.redeem_lock_period, info.latest_redeem_price,
    info.put_option_price, info.put_option_lock, info.latest_put_price, info.latest_put_date,
    info.revise_price, info.conversion_price,
    info.issue_price, info.issue_amount, info.remain_scale,
    info.interest_start_date, info.maturity_date, info.interest_method,
    info.maturity_redeem_price, info.rating, info.full_name, info.short_name, info.bond_life,
    info.interest_note, JSON.stringify(info),
  ]);
}

function sendFeishuNotification(
  totalCount,
  tradeDate,
  snapshotStats,
  listStats,
  elapsed,
  sampleError,
  newBondInfo,
  deactivatedBonds
) {
  return new Promise((resolve, reject) => {
    let errorInfo = '';
    if (sampleError) {
      errorInfo = `\n**失败原因**：${sampleError}`;
    }

    let newBondText = '';
    if (newBondInfo && newBondInfo.count > 0) {
      newBondText = `\n**新增可转债**：${newBondInfo.count} 只`;
      if (newBondInfo.success > 0) {
        newBondText += `，已采集详情 ${newBondInfo.success} 只`;
      }
      if (newBondInfo.failed > 0) {
        newBondText += `，采集失败 ${newBondInfo.failed} 只`;
      }
      if (newBondInfo.detailNames && newBondInfo.detailNames.length > 0) {
        newBondText += `\n**新增债券**：${newBondInfo.detailNames.join('、')}`;
      }
    }

    let deactivatedText = '';
    if (deactivatedBonds && deactivatedBonds.count > 0) {
      deactivatedText = `\n**退市标记**：${deactivatedBonds.count} 只`;
      if (deactivatedBonds.names && deactivatedBonds.names.length > 0) {
        deactivatedText += `\n**退市债券**：${deactivatedBonds.names.join('、')}`;
      }
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
              content: `**触发时间**：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}\n**交易日期**：${tradeDate}\n**获取数据**：${totalCount} 条${snapshotInfo}${listInfo}${newBondText}${deactivatedText}${errorInfo}\n**执行耗时**：${elapsed} 秒`,
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

async function collectNewBondDetails(conn) {
  const [newBonds] = await conn.query(
    "SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 AND created_at = CURRENT_DATE ORDER BY bond_code"
  );

  if (!newBonds || newBonds.length === 0) {
    console.log('No new bonds found today');
    return { count: 0, success: 0, failed: 0, detailNames: [] };
  }

  console.log(`Found ${newBonds.length} new bonds today, collecting details...`);

  let success = 0;
  let failed = 0;
  const detailNames = [];

  for (let i = 0; i < newBonds.length; i++) {
    const bond = newBonds[i];
    console.log(`  [${i + 1}/${newBonds.length}] Collecting detail for ${bond.bond_code} ${bond.bond_name}...`);

    await new Promise(r => setTimeout(r, 1500));

    try {
      const info = await fetchBondDetail(bond.bond_code, bond.bond_name);
      if (info) {
        await upsertBondDetail(conn, info);
        success++;
        detailNames.push(`${bond.bond_name}(${bond.bond_code})`);
        console.log(`  [${i + 1}/${newBonds.length}] ${bond.bond_code} OK`);
      } else {
        failed++;
        console.log(`  [${i + 1}/${newBonds.length}] ${bond.bond_code} FAIL (fetch failed)`);
      }
    } catch (e) {
      failed++;
      console.error(`  [${i + 1}/${newBonds.length}] ${bond.bond_code} FAIL: ${e.message}`);
    }
  }

  console.log(`New bond detail collection done: success ${success}, failed ${failed}`);
  return { count: newBonds.length, success, failed, detailNames };
}

/**
 * 标记已退市可转债（新浪接口不再返回的债券）
 * 将其 is_active 设为 0，后续查询自动忽略
 */
async function markDeactivatedBonds(activeCodes) {
  if (!activeCodes || activeCodes.length === 0) {
    return { count: 0, names: [] };
  }

  return await executeWithRetry(async (conn) => {
    const placeholders = activeCodes.map(() => '?').join(',');
    const [deactivatedList] = await conn.query(
      `SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 AND bond_code NOT IN (${placeholders})`,
      activeCodes
    );

    if (!deactivatedList || deactivatedList.length === 0) {
      console.log('No deactivated bonds found');
      return { count: 0, names: [] };
    }

    const names = deactivatedList.map(b => `${b.bond_name}(${b.bond_code})`);
    console.log(`Found ${deactivatedList.length} deactivated bonds: ${names.join(', ')}`);

    await conn.query(
      `UPDATE bond_list SET is_active = 0, updated_at = CURRENT_DATE WHERE is_active = 1 AND bond_code NOT IN (${placeholders})`,
      activeCodes
    );

    return { count: deactivatedList.length, names };
  });
}

/**
 * 发送触发通知（函数入口立即执行，轻量提示）
 * @param {'start'|'skip'} status - start=正执行, skip=已跳过
 */
async function sendFeishuTriggerNotification(status) {
  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  const dayNames = ['日', '一', '二', '三', '四', '五', '六'];
  const dayName = dayNames[new Date().getDay()];

  const payload = JSON.stringify({
    msg_type: 'interactive',
    card: {
      header: {
        title: {
          tag: 'plain_text',
          content: status === 'skip' ? '⏸️ 可转债行情更新跳过' : '🔔 可转债行情更新触发',
        },
        template: status === 'skip' ? 'grey' : 'indigo',
      },
      elements: [
        {
          tag: 'div',
          text: {
            tag: 'lark_md',
            content: `**函数**：cb_snapshot_updater\n**触发时间**：${now}\n**星期**：周${dayName}\n**状态**：${status === 'skip' ? '⏸️ 非交易日，跳过执行' : '🔄 正在抓取数据...'}`,
          },
        },
      ],
    },
  });

  return new Promise((resolve, reject) => {
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
            resolve(result);
          } else {
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

function isTradingDay() {
  const now = new Date();
  const day = now.getDay();
  return day >= 1 && day <= 5;
}

async function main() {
  const startTime = Date.now();

  // 立即发送触发通知
  try {
    await sendFeishuTriggerNotification(isTradingDay() ? 'start' : 'skip');
  } catch (e) {
    console.error('Trigger notification error:', e.message);
  }

  // 非交易日跳过执行
  if (!isTradingDay()) {
    console.log(`[${new Date().toISOString()}] Non-trading day (weekend), execution skipped`);
    return { success: true, skipped: true, reason: '非交易日' };
  }

  const randomDelay = Math.floor(Math.random() * 109) + 12;
  console.log(`[${new Date().toISOString()}] Cloud function started. Random delay: ${randomDelay}s`);

  await new Promise(r => setTimeout(r, randomDelay * 1000));

  console.log('Fetching convertible bond data from Sina...');
  const rawItems = await getAllBonds();
  console.log(`Raw data: ${rawItems.length} records`);

  const bonds = processData(rawItems);
  console.log(`Processed: ${bonds.length} bonds (after filtering "定转"/"定01")`);

  const snapshotStats = { inserted: 0, updated: 0, errors: 0 };
  const listStats = { inserted: 0, updated: 0, errors: 0 };
  let sampleError = '';
  const tradeDate = bonds.length > 0 ? bonds[0].trade_date : new Date().toISOString().slice(0, 10);

  // 批量处理：每批 BATCH_SIZE 条债券，共用一次连接
  for (let i = 0; i < bonds.length; i += BATCH_SIZE) {
    const batch = bonds.slice(i, i + BATCH_SIZE);

    await executeWithRetry(async (conn) => {
      // 1. 批量 upsert bond_snapshot
      const snapshotValues = batch.map(b => [
        b.trade_date, b.bond_code, b.bond_name, b.price, b.price_change,
        b.change_pct, b.volume, b.amount, b.settlement, b.open_price,
        b.high_price, b.low_price, b.buy_price, b.sell_price, b.trade_time
      ]);
      const [snapResult] = await conn.query(SNAPSHOT_BATCH_SQL, [snapshotValues]);
      // batch upsert: affectedRows = inserted * 1 + updated * 2
      const snapInserted = 2 * batch.length - snapResult.affectedRows;
      snapshotStats.inserted += snapInserted;
      snapshotStats.updated += batch.length - snapInserted;

      // 2. 批量 upsert bond_list
      const listValues = batch.map(b => [
        b.bond_code, b.bond_name, b.market, 1
      ]);
      const [listResult] = await conn.query(LIST_BATCH_SQL, [listValues]);
      const listInserted = 2 * batch.length - listResult.affectedRows;
      listStats.inserted += listInserted;
      listStats.updated += batch.length - listInserted;
    }).catch((e) => {
      snapshotStats.errors += batch.length;
      if (!sampleError) sampleError = `batch at ${i}: ${e.message}`;
      console.error(`Batch insert error at offset ${i} (${batch.length} bonds): ${e.message}`);
    });

    if ((i + BATCH_SIZE) % 200 === 0 || i + BATCH_SIZE >= bonds.length) {
      console.log(`Progress: ${Math.min(i + BATCH_SIZE, bonds.length)}/${bonds.length} - Snapshot: ${snapshotStats.inserted}/${snapshotStats.updated}/${snapshotStats.errors}, List: ${listStats.inserted}/${listStats.updated}/${listStats.errors}`);
    }
  }

  // 标记已退市债券（新浪接口不再返回的 = 已到期退市）
  let deactivatedBonds = null;
  if (bonds.length > 0) {
    const activeCodes = bonds.map(b => b.bond_code);
    deactivatedBonds = await markDeactivatedBonds(activeCodes);
  }

  // 检测新增可转债，采集详情
  console.log('Checking for new bonds to collect details...');
  const newBondInfo = await executeWithRetry((conn) => collectNewBondDetails(conn));

  const elapsed = Math.round((Date.now() - startTime) / 1000);
  console.log(`[${new Date().toISOString()}] Done!`);
  console.log(`  bond_snapshot: inserted=${snapshotStats.inserted}, updated=${snapshotStats.updated}, errors=${snapshotStats.errors}`);
  console.log(`  bond_list: inserted=${listStats.inserted}, updated=${listStats.updated}, errors=${listStats.errors}`);
  if (newBondInfo) {
    console.log(`  bond_detail: new=${newBondInfo.count}, success=${newBondInfo.success}, failed=${newBondInfo.failed}`);
  }
  if (deactivatedBonds && deactivatedBonds.count > 0) {
    console.log(`  bond_list deactivated: ${deactivatedBonds.count} bonds`);
  }
  console.log(`  Elapsed: ${elapsed}s`);

  try {
    await sendFeishuNotification(bonds.length, tradeDate, snapshotStats, listStats, elapsed, sampleError, newBondInfo, deactivatedBonds);
  } catch (e) {
    console.error('Feishu notification error:', e.message);
  }

  return {
    success: true,
    total: bonds.length,
    snapshotStats,
    listStats,
    newBondInfo,
    deactivatedBonds,
    elapsed
  };
}

/**
 * 可转债行情数据快速采集（被 api-bridge 远程调用）
 * 精简模式：跳过节假日判断、随机延迟、飞书通知，只做采集+入库+返回数据
 */
async function refreshCollect() {
  const startTime = Date.now();

  console.log('🔄 [refresh] 开始采集可转债行情...');
  const rawItems = await getAllBonds();
  console.log(`📊 [refresh] 新浪返回 ${rawItems.length} 条原始记录`);

  const bonds = processData(rawItems);
  console.log(`📋 [refresh] 处理后 ${bonds.length} 只转债（已过滤定转/定01）`);

  const snapshotStats = { inserted: 0, updated: 0, errors: 0 };
  const listStats = { inserted: 0, updated: 0, errors: 0 };
  const tradeDate = bonds.length > 0 ? bonds[0].trade_date : new Date().toISOString().slice(0, 10);

  for (let i = 0; i < bonds.length; i += BATCH_SIZE) {
    const batch = bonds.slice(i, i + BATCH_SIZE);

    await executeWithRetry(async (conn) => {
      const snapshotValues = batch.map(b => [
        b.trade_date, b.bond_code, b.bond_name, b.price, b.price_change,
        b.change_pct, b.volume, b.amount, b.settlement, b.open_price,
        b.high_price, b.low_price, b.buy_price, b.sell_price, b.trade_time
      ]);
      const [snapResult] = await conn.query(SNAPSHOT_BATCH_SQL, [snapshotValues]);
      const snapInserted = 2 * batch.length - snapResult.affectedRows;
      snapshotStats.inserted += snapInserted;
      snapshotStats.updated += batch.length - snapInserted;

      const listValues = batch.map(b => [
        b.bond_code, b.bond_name, b.market, 1
      ]);
      const [listResult] = await conn.query(LIST_BATCH_SQL, [listValues]);
      const listInserted = 2 * batch.length - listResult.affectedRows;
      listStats.inserted += listInserted;
      listStats.updated += batch.length - listInserted;
    }).catch((e) => {
      snapshotStats.errors += batch.length;
      console.error(`[refresh] Batch error at offset ${i}: ${e.message}`);
    });
  }

  // 标记退市债券
  let deactivatedBonds = null;
  if (bonds.length > 0) {
    deactivatedBonds = await markDeactivatedBonds(bonds.map(b => b.bond_code));
  }

  // 计算并更新聚合统计表（供前端首页展示）
  console.log('📊 [refresh] 计算聚合统计数据...');
  await executeWithRetry(async (conn) => {
    // 拉取原始快照数据，在 JS 中完成所有聚合（含正确的中位数计算）
    const [snapshots] = await conn.query(
      `SELECT s.bond_code, s.price, s.change_pct, s.amount,
              COALESCE(st.industry_level1, s.industry1, '未知') as industry
       FROM bond_snapshot s
       LEFT JOIN bond_static st ON s.bond_code = st.bond_code
       WHERE s.trade_date = ?`,
      [tradeDate]
    );

    const prices = snapshots.map(r => Number(r.price)).filter(p => !isNaN(p));
    const changePcts = snapshots.map(r => Number(r.change_pct)).filter(p => !isNaN(p));

    function median(arr) {
      if (arr.length === 0) return 0;
      const sorted = [...arr].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      if (sorted.length % 2 === 0) return (sorted[mid - 1] + sorted[mid]) / 2;
      return sorted[mid];
    }

    // 1. daily_reports — 市场概览
    const upCount = snapshots.filter(r => (r.change_pct || 0) > 0).length;
    const downCount = snapshots.filter(r => (r.change_pct || 0) < 0).length;
    const flatCount = snapshots.filter(r => (r.change_pct || 0) === 0).length;
    const totalAmount = snapshots.reduce((s, r) => s + Number(r.amount || 0), 0);

    await conn.query(
      `INSERT INTO daily_reports (trade_date, total_count, up_count, down_count, flat_count, total_amount, price_median, change_median, amount_median, generated_at, source)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), 'refresh')
       ON DUPLICATE KEY UPDATE
         total_count = VALUES(total_count), up_count = VALUES(up_count), down_count = VALUES(down_count),
         flat_count = VALUES(flat_count), total_amount = VALUES(total_amount),
         price_median = VALUES(price_median), change_median = VALUES(change_median),
         amount_median = VALUES(amount_median), generated_at = NOW(), source = 'refresh'`,
      [
        tradeDate,
        snapshots.length,
        upCount,
        downCount,
        flatCount,
        +(totalAmount / 100000000).toFixed(2),
        +median(prices).toFixed(3),
        +median(changePcts).toFixed(3),
        +median(snapshots.map(r => Number(r.amount || 0) / 100000000)).toFixed(3),
      ]
    );

    // 2. daily_industry_distribution — 行业分布
    await conn.query(`DELETE FROM daily_industry_distribution WHERE trade_date = ?`, [tradeDate]);

    const industryMap = new Map();
    for (const r of snapshots) {
      const ind = r.industry || '未知';
      if (!industryMap.has(ind)) industryMap.set(ind, []);
      industryMap.get(ind).push(r);
    }

    const industryInsertValues = [];
    for (const [industry, bonds] of industryMap.entries()) {
      const indUp = bonds.filter(b => Number(b.change_pct || 0) > 0).length;
      const indDown = bonds.filter(b => Number(b.change_pct || 0) < 0).length;
      const indChanges = bonds.map(b => Number(b.change_pct)).filter(c => !isNaN(c));
      const indAmounts = bonds.map(b => Number(b.amount || 0));
      const indAmountSum = indAmounts.reduce((s, v) => s + v, 0);

      industryInsertValues.push([
        tradeDate, industry, bonds.length, indUp, indDown,
        +median(indChanges).toFixed(3),
        +(indAmountSum / 100000000).toFixed(2),
        +median(indAmounts.map(a => a / 100000000)).toFixed(3),
      ]);
    }

    if (industryInsertValues.length > 0) {
      await conn.query(
        `INSERT INTO daily_industry_distribution (trade_date, industry, count, up_count, down_count, change_median, amount_sum, amount_median) VALUES ?`,
        [industryInsertValues]
      );
    }

    // 3. daily_price_distribution — 价格区间分布
    await conn.query(`DELETE FROM daily_price_distribution WHERE trade_date = ?`, [tradeDate]);

    function getPriceRange(price) {
      if (price < 100) return '<100';
      if (price < 110) return '100-110';
      if (price < 120) return '110-120';
      if (price < 130) return '120-130';
      if (price < 140) return '130-140';
      if (price < 150) return '140-150';
      if (price < 160) return '150-160';
      if (price < 200) return '160-200';
      return '200+';
    }

    const priceRangeMap = new Map();
    for (const r of snapshots) {
      if (r.price === null) continue;
      const pr = getPriceRange(r.price);
      if (!priceRangeMap.has(pr)) priceRangeMap.set(pr, []);
      priceRangeMap.get(pr).push(r);
    }

    const priceInsertValues = [];
    for (const [priceRange, bonds] of priceRangeMap.entries()) {
      const prUp = bonds.filter(b => Number(b.change_pct || 0) > 0).length;
      const prDown = bonds.filter(b => Number(b.change_pct || 0) < 0).length;
      const prChanges = bonds.map(b => Number(b.change_pct)).filter(c => !isNaN(c));
      const prAmounts = bonds.map(b => Number(b.amount || 0));
      const prAmountSum = prAmounts.reduce((s, v) => s + v, 0);

      priceInsertValues.push([
        tradeDate, priceRange, bonds.length, prUp, prDown,
        +median(prChanges).toFixed(3),
        +(prAmountSum / 100000000).toFixed(2),
        +median(prAmounts.map(a => a / 100000000)).toFixed(3),
      ]);
    }

    if (priceInsertValues.length > 0) {
      await conn.query(
        `INSERT INTO daily_price_distribution (trade_date, price_range, count, up_count, down_count, change_median, amount_sum, amount_median) VALUES ?`,
        [priceInsertValues]
      );
    }
  });
  console.log('✅ [refresh] 聚合统计表已更新');

  const elapsed = Math.round((Date.now() - startTime) / 1000);
  console.log(`✅ [refresh] 完成！耗时 ${elapsed}s`);

  return {
    success: true,
    total: bonds.length,
    trade_date: tradeDate,
    snapshotStats,
    listStats,
    deactivatedBonds: deactivatedBonds ? { count: deactivatedBonds.count } : null,
    elapsed,
  };
}

exports.main = async (event, context) => {
  try {
    // refresh 模式：被 api-bridge 远程调用，快速采集不通知
    if (event && event.action === 'refresh') {
      const result = await refreshCollect();
      return {
        code: 0,
        message: 'success',
        data: result,
      };
    }

    // 定时触发模式（原逻辑）
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
