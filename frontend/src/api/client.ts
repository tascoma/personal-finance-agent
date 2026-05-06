const BASE = '/api/v1'

let _getToken: () => string | null = () => null
let _onUnauthorized: () => void = () => {}

export function configureClient(
  getToken: () => string | null,
  onUnauthorized: () => void,
): void {
  _getToken = getToken
  _onUnauthorized = onUnauthorized
}

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const isFormData = options.body instanceof FormData
  const token = _getToken()
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {}

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: isFormData
      ? { ...authHeaders, ...(options.headers as Record<string, string> ?? {}) }
      : {
          'Content-Type': 'application/json',
          ...authHeaders,
          ...(options.headers as Record<string, string> ?? {}),
        },
  })

  if (res.status === 401) {
    _onUnauthorized()
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  })
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

export { ApiError }
