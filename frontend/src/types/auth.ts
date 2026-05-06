export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UserRead {
  user_id: string
  email: string
  is_active: boolean
  created_at: string
}
