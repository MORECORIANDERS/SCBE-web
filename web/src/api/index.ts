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
  market: string
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
