export type AuthRole = 'admin' | 'user'
export type AuthStatus = 'pending' | 'active' | 'disabled'

export type AuthUser = {
  id: number
  username: string
  role: AuthRole
  status: AuthStatus
  created_at: string
  approved_at: string | null
}

type AuthResponse = { user: AuthUser }
type RegisterResponse = AuthResponse & { message: string }

function authMessage(error: unknown, fallback: string) {
  const payload = (error as { data?: { detail?: string | { message?: string } } })?.data?.detail
  if (typeof payload === 'string') return payload
  return payload?.message || fallback
}

export function useAuth() {
  const config = useRuntimeConfig()
  const user = useState<AuthUser | null>('auth-user', () => null)
  const ready = useState('auth-ready', () => false)
  const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  const authFetch = globalThis.$fetch.create({ credentials: 'include', headers: requestHeaders })

  async function fetchMe() {
    try {
      const response = await authFetch<AuthResponse>(`${config.public.apiBase}/auth/me`)
      user.value = response.user
    } catch {
      user.value = null
    } finally {
      ready.value = true
    }
    return user.value
  }

  async function login(username: string, password: string) {
    try {
      const response = await authFetch<AuthResponse>(`${config.public.apiBase}/auth/login`, {
        method: 'POST',
        body: { username, password }
      })
      user.value = response.user
      ready.value = true
      return response.user
    } catch (error) {
      throw new Error(authMessage(error, 'Unable to sign in.'))
    }
  }

  async function register(username: string, password: string) {
    try {
      return await authFetch<RegisterResponse>(`${config.public.apiBase}/auth/register`, {
        method: 'POST',
        body: { username, password }
      })
    } catch (error) {
      throw new Error(authMessage(error, 'Unable to register this account.'))
    }
  }

  async function logout() {
    try {
      await authFetch(`${config.public.apiBase}/auth/logout`, { method: 'POST' })
    } finally {
      user.value = null
      ready.value = true
    }
  }

  async function listUsers() {
    const response = await authFetch<{ users: AuthUser[] }>(`${config.public.apiBase}/auth/users`)
    return response.users
  }

  async function setUserStatus(userId: number, status: 'active' | 'disabled') {
    const response = await authFetch<AuthResponse>(`${config.public.apiBase}/auth/users/${userId}`, {
      method: 'PATCH',
      body: { status }
    })
    return response.user
  }

  return { user, ready, fetchMe, login, register, logout, listUsers, setUserStatus }
}
