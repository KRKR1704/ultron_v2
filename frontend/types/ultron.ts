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

// ── WebSocket ─────────────────────────────────────────────────────────────────

export interface WebSocketMessage {
  transcript: string
  response_text: string
  audio_base64: string
  language: UltronLanguage
  mode: UltronMode
}

// ── API error ─────────────────────────────────────────────────────────────────

export interface ApiError {
  message: string
  status: number
}
