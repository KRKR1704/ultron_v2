// ── Shared types for ULTRON desktop app ──────────────────────────────────────

export type UltronMode = 'professional' | 'casual'

/** BCP-47 language code, e.g. 'en', 'hi', 'ko' */
export type UltronLanguage = string

// ── API response shapes ───────────────────────────────────────────────────────

export interface ChatResponse {
  response_text: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface VoiceResponse {
  transcript: string
  response_text: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface VisionResponse {
  analysis: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface StatusResponse {
  mode: UltronMode
  language: UltronLanguage
  camera_active: boolean
  screen_active: boolean
  wake_word_active: boolean
}

export interface ModeResponse {
  success: boolean
  current_mode: UltronMode
  confirmation_audio: string
}

export interface SmartHomeResponse {
  action_taken: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface CalendarResponse {
  result: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface TaskResponse {
  result: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

export interface PauseCameraResponse {
  /** Backend returns { active: bool } — reflects new camera monitoring state */
  active: boolean
}

export interface PauseScreenResponse {
  /** Backend returns { active: bool } — reflects new screen monitoring state */
  active: boolean
}

// ── Weather ───────────────────────────────────────────────────────────────────

export type WeatherCondition = 'sunny' | 'cloudy' | 'rainy' | 'snowy' | 'windy'

export interface WeatherResponse {
  temperature: number
  condition: WeatherCondition
  location_name: string
  unit: string
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
// Discriminated union of every frame api/websocket.py actually sends over
// ws://.../ws (see backend/api/websocket.py module docstring for the
// authoritative list).

export type WebSocketMessage =
  | { type: 'transcript'; text: string }
  | { type: 'token'; text: string }
  | { type: 'audio_generating' }
  | { type: 'audio'; audio_base64: string }
  | { type: 'done'; language: UltronLanguage; mode: UltronMode }
  | { type: 'wake_word' }
  | { type: 'suggestion'; text: string; audio_base64?: string }
  | { type: 'camera_alert'; message: string }
  | { type: 'ping' }
  | { type: 'pong' }
  | { type: 'error'; message: string }

// ── API error ─────────────────────────────────────────────────────────────────

export interface ApiError {
  message: string
  status: number
}
