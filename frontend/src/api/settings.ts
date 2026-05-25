import { apiRequest } from './client'

export type RuntimeSettings = {
  app_env: string
  library_login_url: string
  library_base_url: string
  allow_live_test: boolean
  allow_mutation_test: boolean
  enable_captcha_ocr: boolean
}

export function fetchRuntimeSettings() {
  return apiRequest<RuntimeSettings>('/api/settings/runtime')
}
