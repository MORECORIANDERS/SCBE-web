const mysql = require('mysql2/promise')
const https = require('https')
const http = require('http')

const DB = {
  host: process.env.DB_HOST || 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: parseInt(process.env.DB_PORT || '27120'),
  user: process.env.DB_USER || 'cbreport',
  password: process.env.DB_PASSWORD || 'huo22QQQ',
  database: process.env.DB_NAME || 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 30000,
  insecureAuth: true,
}

const REQUEST_DELAY_MS = 1500
const SINA_API = 'https://quotes.sina.com.cn/bd/api/openapi.php/BondService2021.getBondInfo'

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http
    client.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn/',
      },
      timeout: 30000,
    }, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => resolve(data))
    }).on('error', reject).on('timeout', () => reject(new Error('Request timeout')))
  })
}

async function getDbConnection(config, retries = 3) {
  let lastError
  for (let i = 0; i < retries; i++) {
    try {
      return await mysql.createConnection(config)
    } catch (e) {
      lastError = e
      console.error(`DB connection attempt ${i + 1}/${retries} failed: ${e.message}`)
      if (i < retries - 1) await new Promise(r => setTimeout(r, 5000))
    }
  }
  throw lastError
}

async function getBondCodes(mode, bondCodes) {
  if (mode === 'single') {
    const code = Array.isArray(bondCodes) ? String(bondCodes[0]) : String(bondCodes)
    return [code]
  }
  if (mode === 'batch') {
    if (!Array.isArray(bondCodes) || bondCodes.length === 0) {
      throw new Error('batch mode need bond_codes array')
    }
    return bondCodes.map(String)
  }

  const conn = await getDbConnection(DB)
    try {
      let sql
      if (mode === 'full') {
        sql = 'SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 ORDER BY bond_code'
      } else if (mode === 'new') {
        sql = "SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 AND created_at = CURDATE() ORDER BY bond_code"
      } else {
        throw new Error(`unknown mode: ${mode}`)
      }
      const [rows] = await conn.query(sql)
      return rows
    } finally {
      await conn.end()
    }
}

function parseBondInfo(data, bondCode, bondName) {
  const conver = data.converInfo || {}
  const base = data.baseInfo || {}

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
  }
}

async function fetchBondInfo(bondCode, bondName) {
  try {
    const url = `${SINA_API}?symbol=sh${bondCode}&callback=hqccall_bondinfo`
    const text = await httpGet(url)
    if (!text || text.trim() === '') return null

    let data
    try {
      const jsonStr = text.replace(/^[a-zA-Z_]\w*\(/, '').replace(/\);?\s*$/, '').trim()
      data = JSON.parse(jsonStr)
    } catch (e) {
      const match = text.match(/\{[\s\S]*\}/)
      if (match) data = JSON.parse(match[0])
      else return null
    }

    if (!data || !data.result || !data.result.data) return null
    return parseBondInfo(data.result.data, bondCode, bondName)
  } catch (e) {
    console.error(`fetch ${bondCode} failed: ${e.message}`)
    return null
  }
}

const UPSERT_SQL = `
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
`

async function upsertBondDetail(conn, info) {
  await conn.query(UPSERT_SQL, [
    info.bond_code, info.name, info.stock_code, info.stock_name,
    info.conversion_start_date, info.conversion_end_date,
    info.force_redeem_price, info.redeem_lock_period, info.latest_redeem_price,
    info.put_option_price, info.put_option_lock, info.latest_put_price, info.latest_put_date,
    info.revise_price, info.conversion_price,
    info.issue_price, info.issue_amount, info.remain_scale,
    info.interest_start_date, info.maturity_date, info.interest_method,
    info.maturity_redeem_price, info.rating, info.full_name, info.short_name, info.bond_life,
    info.interest_note, JSON.stringify(info),
  ])
}

async function runCollector(mode, bondCodesParam) {
  const bonds = await getBondCodes(mode, bondCodesParam)
  if (!bonds || bonds.length === 0) {
    return { success: true, message: `[${mode}] no bonds to collect`, total: 0, successCount: 0, failedCount: 0 }
  }

  const conn = await getDbConnection(DB)
  let successCount = 0
  let failedCount = 0
  const total = bonds.length

  try {
    for (let i = 0; i < total; i++) {
      const bond = bonds[i]
      const code = typeof bond === 'string' ? bond : bond.bond_code
      const name = typeof bond === 'string' ? '' : (bond.bond_name || '')

      console.log(`  [${i + 1}/${total}] fetch ${code}...`)
      await new Promise(r => setTimeout(r, REQUEST_DELAY_MS))

      const info = await fetchBondInfo(code, name)
      if (info) {
        try {
          await upsertBondDetail(conn, info)
          successCount++
          console.log(`  [${i + 1}/${total}] ${code} OK`)
        } catch (e) {
          console.error(`  write ${code} failed: ${e.message}`)
          failedCount++
        }
      } else {
        failedCount++
        console.log(`  [${i + 1}/${total}] ${code} FAIL`)
      }
    }
  } finally {
    await conn.end()
  }

  return {
    success: true,
    message: `[${mode}] done: success ${successCount}, failed ${failedCount}, total ${total}`,
    total,
    successCount,
    failedCount,
  }
}

exports.main = async (event, context) => {
  const mode = event.mode || 'full'
  const bondCodes = event.bond_codes || event.bondCodes || null

  console.log(`[SinaBondsDetailCollector] mode=${mode}`)

  try {
    const result = await runCollector(mode, bondCodes)
    return { code: 0, success: true, data: result }
  } catch (e) {
    console.error(`exec failed: ${e.message}`)
    return { code: -1, success: false, message: e.message }
  }
}
