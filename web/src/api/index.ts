import { API_BASE_URL, API_TOKEN } from '@/config'

export interface MarketStats {
  totalBonds: number
  upCount: number
  downCount: number
  flatCount: number
  totalVolume: number
  priceMedian: number
  changeMedian: number
  volumeMedian: number
  volumeChange?: number
}

export interface BondItem {
  code: string
  name: string
  price: number
  change_pct: number
  amount: number
  industry: string
  industry2: string
  market: string
  maturity_date: string
  latest_amount: number
  premium?: number
  stock_price?: number
  stock_change_pct?: number
  remain_size?: number
  double_low?: number
}

export interface IndustryStat {
  industry: string
  total: number
  up_count: number
  down_count: number
  flat_count: number
  avg_change: number
  total_amount: number
  avg_amount: number
  change_median: number
}

export interface PriceDistribution {
  price_range: string
  count: number
  up_count: number
  down_count: number
  change_median: number
  amount_sum: number
  amount_median: number
}

export interface OversoldBond {
  bond_code: string
  bond_name: string
  price: number
  change_percent: number
  is_oversold: boolean
  industry: string
  industry_level1: string
  industry_level2: string
  industry_level3: string
  remain_scale: number
  maturity_date: string
  cci: number
  wr: number
  amount_yi: number
  avg_amount_yi: number
  volume_ratio: number
}

export interface AllData {
  marketStats: MarketStats | null
  bonds: BondItem[]
  industryStats: IndustryStat[]
  priceDistribution: PriceDistribution[]
}

const ORIGIN = typeof window !== 'undefined' ? window.location.origin : ''

async function request<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}${endpoint.includes('?') ? '&' : '?'}token=${API_TOKEN}`
  const res = await fetch(url, {
    headers: { Origin: ORIGIN },
  })
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`)
  }
  const json = await res.json()
  if (!json.success) {
    throw new Error(json.message || 'API Error')
  }
  return json.data as T
}

export async function fetchMarketStats(): Promise<MarketStats | null> {
  return request<MarketStats | null>('/api/market-stats')
}

export async function fetchBonds(): Promise<BondItem[]> {
  return request<BondItem[]>('/api/bonds')
}

export async function fetchIndustryStats(): Promise<IndustryStat[]> {
  return request<IndustryStat[]>('/api/industry-stats')
}

export async function fetchPriceDistribution(): Promise<PriceDistribution[]> {
  return request<PriceDistribution[]>('/api/price-distribution')
}

export async function fetchAll(): Promise<AllData> {
  return request<AllData>('/api/all')
}

export async function refreshData(): Promise<any> {
  return request<any>('/api/refresh')
}

export async function triggerDailyOversold(): Promise<any> {
  return request<any>('/api/trigger-daily-oversold')
}

export async function triggerWeeklyOversold(): Promise<any> {
  return request<any>('/api/trigger-weekly-oversold')
}

export async function triggerVolumeFilter(): Promise<any> {
  return request<any>('/api/trigger-volume-filter')
}

export async function fetchOversold(): Promise<OversoldBond[]> {
  return request<OversoldBond[]>('/api/oversold')
}

export async function fetchStrategyWeekly(): Promise<OversoldBond[]> {
  return request<OversoldBond[]>('/api/strategy-weekly')
}

export async function fetchStrategyVolume(): Promise<OversoldBond[]> {
  return request<OversoldBond[]>('/api/strategy-volume')
}
