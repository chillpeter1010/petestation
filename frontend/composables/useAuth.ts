export type AuthRole = 'admin' | 'user'
export type AuthStatus = 'pending' | 'active' | 'disabled'

export type BallparkAvatarV1 = {
  avatar_version: 1
  body_id: 'tone_1' | 'tone_2' | 'tone_3' | 'tone_4'
  uniform_id: 'neutral_home' | 'neutral_away'
  palette_id: 'orange' | 'teal' | 'slate'
  number: number | null
  bats: 'R' | 'L' | 'S' | 'unknown'
  throws: 'R' | 'L' | 'S' | 'unknown'
}

export type AuthUser = {
  id: number
  username: string
  role: AuthRole
  status: AuthStatus
  created_at: string
  approved_at: string | null
  favorite_team_id: number | null
  favorite_team_code: string | null
  avatar_setup_status: 'pending' | 'default'
  avatar: BallparkAvatarV1
  avatar_recovery_needed: boolean
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
  const isBackstageAdmin = computed(() => user.value?.role === 'admin' && user.value.username === 'peter1010')
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

  async function register(username: string, password: string, favoriteTeamId: number | null = null) {
    try {
      return await authFetch<RegisterResponse>(`${config.public.apiBase}/auth/register`, {
        method: 'POST',
        body: { username, password, favorite_team_id: favoriteTeamId }
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

  async function updateProfile(profile: { favorite_team_id: number | null; avatar_setup_status: 'pending' | 'default' }) {
    try {
      const response = await authFetch<AuthResponse>(`${config.public.apiBase}/auth/profile`, {
        method: 'PATCH',
        body: profile
      })
      user.value = response.user
      return response.user
    } catch (error) {
      throw new Error(authMessage(error, 'Unable to update your Ballpark profile.'))
    }
  }

  async function updateAvatar(avatar: BallparkAvatarV1) {
    try {
      const response = await authFetch<AuthResponse>(`${config.public.apiBase}/auth/avatar`, {
        method: 'PATCH',
        body: { avatar }
      })
      user.value = response.user
      return response.user
    } catch (error) {
      throw new Error(authMessage(error, 'Unable to save your Ballpark character.'))
    }
  }

  return { user, ready, isBackstageAdmin, fetchMe, login, register, logout, listUsers, setUserStatus, updateProfile, updateAvatar }
}
