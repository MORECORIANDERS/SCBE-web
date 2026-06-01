const mysql = require('mysql2/promise')
const cloudbase = require('@cloudbase/node-sdk')

const DB_CONFIG = {
  host: process.env.DB_HOST || 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
  port: parseInt(process.env.DB_PORT || '27120'),
  user: process.env.DB_USER || 'cbreport',
  password: process.env.DB_PASSWORD || 'huo22QQQ',
  database: process.env.DB_NAME || 'python12-9guk780v324f024d',
  charset: 'utf8mb4',
  connectTimeout: 15000,
}

const AUTH_TOKEN = process.env.API_TOKEN || 'scbe2024'

const tcbApp = cloudbase.init({
  env: process.env.TCB_ENV_ID || 'python12-9guk780v324f024d',
})

const pool = mysql.createPool({
  ...DB_CONFIG,
  connectionLimit: 2,
  waitForConnections: true,
  enableKeepAlive: true,
  keepAliveInitialDelay: 10000,
})

const ALLOWED_ORIGINS = [
  'https://morecorianders.github.io',
  'http://localhost:5173',
  'http://localhost:4173',
]

function getCorsHeaders(origin) {
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : 'https://morecorianders.github.io'
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    'Content-Type': 'application/json; charset=utf-8',
  }
}

function unauthorized(corsHeaders) {
  return {
    isBase64Encoded: false,
    statusCode: 401,
    headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ error: 'Unauthorized', message: '无效的 Token' }),
  }
}

function errorResponse(message, corsHeaders) {
  return {
    isBase64Encoded: false,
    statusCode: 500,
    headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ error: 'Internal Server Error', message }),
  }
}

function successResponse(data, corsHeaders) {
  return {
    isBase64Encoded: false,
    statusCode: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify(data),
  }
}

async function queryLatestDate(table, dateColumn = 'trade_date') {
  const [rows] = await pool.query(`SELECT MAX(${dateColumn}) as latest FROM ${table}`)
  return rows[0].latest
}

async function getMarketStats() {
  const latestDate = await queryLatestDate('daily_reports')
  if (!latestDate) return null

  const [rows] = await pool.query(
    'SELECT total_count, up_count, down_count, flat_count, total_amount, price_median, change_median, amount_median FROM daily_reports WHERE trade_date = ?',
    [latestDate]
  )
  if (rows.length === 0) return null

  const r = rows[0]
  return {
    totalBonds: r.total_count,
    upCount: r.up_count,
    downCount: r.down_count,
    flatCount: r.flat_count,
    totalVolume: parseFloat(r.total_amount) || 0,
    priceMedian: parseFloat(r.price_median) || 0,
    changeMedian: parseFloat(r.change_median) || 0,
    volumeMedian: parseFloat(r.amount_median) || 0,
  }
}

async function getBonds() {
  const latestDate = await queryLatestDate('bond_snapshot')
  if (!latestDate) return []

  const [rows] = await pool.query(
    `SELECT s.bond_code, s.bond_name, s.price, s.change_pct, s.amount,
            COALESCE(st.industry_level1, s.industry1, '') as industry1,
            COALESCE(st.industry_level2, '') as industry2,
            COALESCE(st.sector, s.sector, '') as sector,
            COALESCE(st.maturity_date, '') as maturity_date,
            COALESCE(st.latest_amount, 0) as latest_amount
     FROM bond_snapshot s
     LEFT JOIN bond_static st ON s.bond_code = st.bond_code
     WHERE s.trade_date = ?
     ORDER BY s.amount DESC`,
    [latestDate]
  )

  return rows.map(r => ({
    code: r.bond_code,
    name: r.bond_name,
    price: parseFloat(r.price) || 0,
    change_pct: parseFloat(r.change_pct) || 0,
    amount: parseFloat(r.amount) ? +(parseFloat(r.amount) / 1e8).toFixed(2) : 0,
    industry: r.industry1 || '',
    industry2: r.industry2 || '',
    market: r.sector || '',
    maturity_date: r.maturity_date || '',
    latest_amount: parseFloat(r.latest_amount) ? +parseFloat(r.latest_amount).toFixed(2) : 0,
  }))
}

async function getIndustryStats() {
  const latestDate = await queryLatestDate('daily_industry_distribution')
  if (!latestDate) return []

  const [rows] = await pool.query(
    `SELECT industry, count, up_count, down_count, change_median, amount_sum, amount_median
     FROM daily_industry_distribution
     WHERE trade_date = ?
     ORDER BY count DESC`,
    [latestDate]
  )

  return rows.map(r => ({
    industry: r.industry,
    total: r.count,
    up_count: r.up_count,
    down_count: r.down_count,
    flat_count: r.count - (r.up_count || 0) - (r.down_count || 0),
    avg_change: parseFloat(r.change_median) || 0,
    total_amount: parseFloat(r.amount_sum) || 0,
    avg_amount: parseFloat(r.amount_median) || 0,
    change_median: parseFloat(r.change_median) || 0,
  }))
}

async function getPriceDistribution() {
  const latestDate = await queryLatestDate('daily_price_distribution')
  if (!latestDate) return []

  const [rows] = await pool.query(
    `SELECT price_range, count, up_count, down_count, change_median, amount_sum, amount_median
     FROM daily_price_distribution
     WHERE trade_date = ?
     ORDER BY id ASC`,
    [latestDate]
  )

  return rows.map(r => ({
    price_range: r.price_range,
    count: r.count,
    up_count: r.up_count,
    down_count: r.down_count,
    change_median: parseFloat(r.change_median) || 0,
    amount_sum: parseFloat(r.amount_sum) || 0,
    amount_median: parseFloat(r.amount_median) || 0,
  }))
}

async function getOversold() {
  return getStrategyBonds('daily')
}

async function getStrategyBonds(strategyType) {
  const latestDate = await queryLatestDate('daily_strategy')
  if (!latestDate) return []

  const [rows] = await pool.query(
    `SELECT bond_code, bond_name, price, change_pct, industry,
            remain_scale, maturity_date, cci, wr, is_oversold, amount_yi
     FROM daily_strategy
     WHERE trade_date = ? AND strategy_type = ?
     ORDER BY is_oversold DESC, wr DESC`,
    [latestDate, strategyType]
  )

  return rows.map(r => ({
    bond_code: r.bond_code,
    bond_name: r.bond_name,
    price: parseFloat(r.price) || 0,
    change_percent: parseFloat(r.change_pct) || 0,
    is_oversold: r.is_oversold === 1,
    industry: r.industry || '',
    remain_scale: parseFloat(r.remain_scale) || 0,
    maturity_date: r.maturity_date || '',
    cci: r.cci !== null ? parseFloat(r.cci) : 0,
    wr: r.wr !== null ? parseFloat(r.wr) : 0,
    amount_yi: parseFloat(r.amount_yi) || 0,
  }))
}

exports.main = async function (event) {
  const { path, httpMethod, queryStringParameters, headers } = event
  const origin = headers?.origin || headers?.Origin || ''
  const corsHeaders = getCorsHeaders(origin)

  if (httpMethod === 'OPTIONS') {
    return {
      isBase64Encoded: false,
      statusCode: 204,
      headers: corsHeaders,
      body: '',
    }
  }

  const token = queryStringParameters?.token
  if (!token || token !== AUTH_TOKEN) {
    return unauthorized(corsHeaders)
  }

  try {
    switch (path) {
      case '/api/market-stats': {
        const data = await getMarketStats()
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/bonds': {
        const data = await getBonds()
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/industry-stats': {
        const data = await getIndustryStats()
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/price-distribution': {
        const data = await getPriceDistribution()
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/oversold': {
        const data = await getOversold()
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/strategy-weekly': {
        const data = await getStrategyBonds('weekly')
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/strategy-volume': {
        const data = await getStrategyBonds('volume')
        return successResponse({ success: true, data }, corsHeaders)
      }

      case '/api/refresh': {
        console.log('🔄 [api-bridge] Calling cb_snapshot_updater with action=refresh...')
        const funcResult = await tcbApp.callFunction({
          name: 'cb_snapshot_updater',
          data: { action: 'refresh' },
        })
        console.log('✅ [api-bridge] cb_snapshot_updater result:', JSON.stringify(funcResult).slice(0, 200))
        return successResponse({
          success: true,
          data: funcResult,
        }, corsHeaders)
      }

      case '/api/trigger-daily-oversold': {
        console.log('🔄 [api-bridge] Calling cb_oversold_detector (daily)...')
        const dailyResult = await tcbApp.callFunction({
          name: 'cb_oversold_detector',
          data: { mode: 'daily' },
        })
        console.log('✅ [api-bridge] cb_oversold_detector result:', JSON.stringify(dailyResult).slice(0, 200))
        return successResponse({ success: true, data: dailyResult }, corsHeaders)
      }

      case '/api/trigger-weekly-oversold': {
        console.log('🔄 [api-bridge] Calling cb_oversold_detector_weekly...')
        const weeklyResult = await tcbApp.callFunction({
          name: 'cb_oversold_detector_weekly',
        })
        console.log('✅ [api-bridge] cb_oversold_detector_weekly result:', JSON.stringify(weeklyResult).slice(0, 200))
        return successResponse({ success: true, data: weeklyResult }, corsHeaders)
      }

      case '/api/trigger-volume-filter': {
        console.log('🔄 [api-bridge] Calling cb_volume_filter...')
        const volResult = await tcbApp.callFunction({
          name: 'cb_volume_filter',
        })
        console.log('✅ [api-bridge] cb_volume_filter result:', JSON.stringify(volResult).slice(0, 200))
        return successResponse({ success: true, data: volResult }, corsHeaders)
      }

      case '/api/all': {
        const [marketStats, bonds, industryStats, priceDistribution] = await Promise.all([
          getMarketStats(),
          getBonds(),
          getIndustryStats(),
          getPriceDistribution(),
        ])
        return successResponse({
          success: true,
          data: { marketStats, bonds, industryStats, priceDistribution },
        }, corsHeaders)
      }

      default:
        return {
          isBase64Encoded: false,
          statusCode: 404,
          headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify({ error: 'Not Found', message: `未知路径: ${path}` }),
        }
    }
  } catch (e) {
    console.error('API Error:', e)
    return errorResponse(e.message, corsHeaders)
  }
}
