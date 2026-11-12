const API_BASE = '/api/v1'
let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null

export function setAccessToken(token: string) {
  accessToken = token
}

export function getAccessToken() {
  return accessToken
}

export function clearAccessToken() {
  accessToken = null
}

type ApiOptions = RequestInit & { retryAuth?: boolean }

export async function api<T = void>(path: string, options: ApiOptions = {}): Promise<T> {
  const { retryAuth = true, ...init } = options
  const response = await send(path, init)
  const authNoRetry = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']
  if (response.status === 401 && retryAuth && !authNoRetry.includes(path)) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      const retried = await send(path, init)
      return parseResponse<T>(retried)
    }
  }
  return parseResponse<T>(response)
}

async function send(path: string, init: RequestInit) {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (isCookieMutation(path, init.method)) {
    const csrf = getCookie('csrf_token')
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include'
  })
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  const csrf = getCookie('csrf_token')
  if (!csrf) return false

  refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrf }
  })
    .then(async (response) => {
      if (!response.ok) return false
      const data = await response.json() as { access_token?: string }
      if (!data.access_token) return false
      setAccessToken(data.access_token)
      return true
    })
    .catch(() => false)
    .finally(() => { refreshInFlight = null })

  return refreshInFlight
}

function isCookieMutation(path: string, method?: string) {
  return path.startsWith('/auth/') && ['POST', 'PATCH', 'PUT', 'DELETE'].includes((method ?? 'GET').toUpperCase())
}

function getCookie(name: string) {
  if (typeof document === 'undefined') return ''
  const prefix = `${name}=`
  return document.cookie.split(';').map((cookie) => cookie.trim()).find((cookie) => cookie.startsWith(prefix))?.slice(prefix.length) ?? ''
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null) as unknown
  if (!response.ok) throw new Error(readError(data, response.status))
  return data as T
}

function readError(data: unknown, status: number) {
  if (data && typeof data === 'object' && 'error' in data) {
    const error = (data as { error: unknown }).error
    if (error && typeof error === 'object' && 'message' in error) {
      return String((error as { message: unknown }).message)
    }
  }
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item)).join('; ')
  }
  if (data && typeof data === 'object' && 'message' in data) return String((data as { message: unknown }).message)
  return `Request failed (${status}). Please try again.`
}
