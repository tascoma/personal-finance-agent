import { get, post } from './client'
import type { TokenResponse, UserRead } from '../types/auth'

export const loginUser = (email: string, password: string): Promise<TokenResponse> =>
  post<TokenResponse>('/auth/login', { email, password })

export const refreshToken = (): Promise<TokenResponse> =>
  post<TokenResponse>('/auth/refresh')

export const logoutUser = (): Promise<void> =>
  post<void>('/auth/logout')

export const getMe = (): Promise<UserRead> =>
  get<UserRead>('/auth/me')
