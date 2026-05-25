import { apiRequest } from './client'

export type LoginResponse = {
  success: boolean
  message: string
  captcha_required: boolean
}

export type SessionStatus = {
  library_user_id: number
  logged_in: boolean
  sys_username: string | null
  user_info: Record<string, unknown> | null
  has_csrf: boolean
}

export type Room = {
  room_id: string
  name: string
}

export type SeatItem = {
  seat_id: number
  name: string
  room_name: string | null
  status: string
  title: string | null
}

export type SearchResult = {
  seats: SeatItem[]
  seat_num: number
  on_date: string | null
  next_offset: number
}

export type TimeOption = {
  raw_value: string
  label: string
}

export type StartTimesResult = {
  seat_id: number | null
  room_name: string | null
  building_name: string | null
  options: TimeOption[]
}

export type ReservationPayload = {
  seat_id: number
  start: string
  end: string
  date: string
}

export type MutationResponse = {
  success: boolean
  message: string
  raw: unknown
}

export type HistoryEntry = {
  reservation_id: string | null
  credential_no: string | null
  seat_name: string | null
  room_name: string | null
  date: string | null
  start_label: string | null
  end_label: string | null
  status: string | null
  raw_date_label: string | null
}

export type Announcement = {
  roll_text: string | null
}

export type ReservationDetail = {
  reservation_id: string | null
  credential_no: string | null
  date: string | null
  start_label: string | null
  end_label: string | null
  seat_name: string | null
  room_name: string | null
  status: string | null
  raw_text: string
}

export type SearchQuery = {
  on_date?: string
  building?: string
  room?: string
  hour?: string
  start_min?: string
  end_min?: string
  power?: string
  window?: string
  offset?: number
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    usp.set(k, String(v))
  }
  const search = usp.toString()
  return search ? `?${search}` : ''
}

export function loginLibrary(userId: number) {
  return apiRequest<LoginResponse>(`/api/library/${userId}/login`, {
    method: 'POST',
  })
}

export function logoutLibrary(userId: number) {
  return apiRequest<void>(`/api/library/${userId}/logout`, { method: 'POST' })
}

export function fetchSession(userId: number) {
  return apiRequest<SessionStatus>(`/api/library/${userId}/session`)
}

export function fetchRooms(userId: number, building: string) {
  return apiRequest<Room[]>(`/api/library/${userId}/rooms${buildQuery({ building })}`)
}

export function searchSeats(userId: number, query: SearchQuery) {
  return apiRequest<SearchResult>(`/api/library/${userId}/seats${buildQuery(query)}`)
}

export function fetchStartTimes(userId: number, seatId: number, date = '') {
  return apiRequest<StartTimesResult>(
    `/api/library/${userId}/seats/${seatId}/start-times${buildQuery({ date })}`,
  )
}

export function fetchEndTimes(userId: number, seatId: number, start: string, date = '') {
  return apiRequest<TimeOption[]>(
    `/api/library/${userId}/seats/${seatId}/end-times${buildQuery({ start, date })}`,
  )
}

export function submitReservation(userId: number, payload: ReservationPayload) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/reservations`, {
    method: 'POST',
    body: payload,
  })
}

export function cancelReservation(userId: number, reservationId: string) {
  return apiRequest<MutationResponse>(
    `/api/library/${userId}/reservations/${reservationId}/cancel`,
    { method: 'POST' },
  )
}

export function checkInLibrary(userId: number) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/check-in`, { method: 'POST' })
}

export function renewLibrary(userId: number) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/renew`, { method: 'POST' })
}

export function stopUsing(userId: number) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/stop-using`, { method: 'POST' })
}

export function leaveLibrary(userId: number) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/leave`, { method: 'POST' })
}

export function resumeLibrary(userId: number) {
  return apiRequest<MutationResponse>(`/api/library/${userId}/resume`, { method: 'POST' })
}

export function fetchReservationDetail(userId: number, reservationId: string) {
  return apiRequest<ReservationDetail>(
    `/api/library/${userId}/reservations/${encodeURIComponent(reservationId)}`,
  )
}

export function fetchHistory(userId: number) {
  return apiRequest<HistoryEntry[]>(`/api/library/${userId}/reservations`)
}

export function fetchAnnouncement(userId: number) {
  return apiRequest<Announcement>(`/api/library/${userId}/announcement`)
}
