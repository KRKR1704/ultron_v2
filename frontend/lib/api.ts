import type {
  ChatResponse,
  VoiceResponse,
  VisionResponse,
  StatusResponse,
  ModeResponse,
  SmartHomeResponse,
  CalendarResponse,
  TaskResponse,
  PauseCameraResponse,
  PauseScreenResponse,
  WeatherResponse,
  UltronMode,
} from '@/types/ultron'

// ── Config ────────────────────────────────────────────────────────────────────

const BASE_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8000'

export const WS_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_WS_URL) ||
  'ws://localhost:8000/ws'

// ── Internal fetch helper ─────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`

  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.text().catch(() => 'Unknown error')
    throw new Error(`API ${response.status}: ${body}`)
  }

  return response.json() as Promise<T>
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

/**
 * Send a text message to ULTRON.
 * POST /chat → { response_text, audio_base64, language, mode }
 * Pass an AbortSignal to allow the caller to cancel mid-flight.
 */
export function sendTextMessage(
  message: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  })
}

/**
 * Send base64-encoded voice audio to ULTRON.
 * POST /voice → { transcript, response_text, audio_base64, language, mode }
 */
export function sendVoiceMessage(
  audioBase64: string,
  sessionId: string,
): Promise<VoiceResponse> {
  return request<VoiceResponse>('/voice', {
    method: 'POST',
    body: JSON.stringify({ audio_base64: audioBase64, session_id: sessionId }),
  })
}

/**
 * Analyze a camera frame and answer a question about it.
 * POST /vision/camera → { analysis, audio_base64, language, mode }
 */
export function analyzeCameraFeed(
  question: string,
  sessionId: string,
): Promise<VisionResponse> {
  return request<VisionResponse>('/vision/camera', {
    method: 'POST',
    body: JSON.stringify({ question, session_id: sessionId }),
  })
}

/**
 * Analyze the current screen and answer a question about it.
 * POST /vision/screen → { analysis, audio_base64, language, mode }
 */
export function analyzeScreen(
  question: string,
  sessionId: string,
): Promise<VisionResponse> {
  return request<VisionResponse>('/vision/screen', {
    method: 'POST',
    body: JSON.stringify({ question, session_id: sessionId }),
  })
}

/**
 * Switch ULTRON's personality mode.
 * POST /mode → { success, current_mode, confirmation_audio }
 */
export function switchMode(mode: UltronMode): Promise<ModeResponse> {
  return request<ModeResponse>('/mode', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

/**
 * Issue a smart-home command.
 * POST /smarthome → { action_taken, audio_base64, language, mode }
 */
export function controlSmartHome(
  command: string,
  sessionId: string,
): Promise<SmartHomeResponse> {
  return request<SmartHomeResponse>('/smarthome', {
    method: 'POST',
    body: JSON.stringify({ command, session_id: sessionId }),
  })
}

/**
 * Perform a calendar action.
 * POST /calendar → { result, audio_base64, language, mode }
 */
export function calendarAction(
  action: string,
  details: string,
  sessionId: string,
): Promise<CalendarResponse> {
  return request<CalendarResponse>('/calendar', {
    method: 'POST',
    body: JSON.stringify({ action, details, session_id: sessionId }),
  })
}

/**
 * Perform a task/todo action.
 * POST /tasks → { result, audio_base64, language, mode }
 */
export function taskAction(
  action: string,
  details: string,
  sessionId: string,
): Promise<TaskResponse> {
  return request<TaskResponse>('/tasks', {
    method: 'POST',
    body: JSON.stringify({ action, details, session_id: sessionId }),
  })
}

/**
 * Get the current ULTRON system status.
 * GET /status → { mode, language, camera_active, screen_active, wake_word_active }
 */
export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>('/status')
}

/**
 * Pause or resume the camera feed.
 * POST /pause/camera → { camera_active }
 */
export function pauseCamera(paused: boolean): Promise<PauseCameraResponse> {
  return request<PauseCameraResponse>('/pause/camera', {
    method: 'POST',
    body: JSON.stringify({ paused }),
  })
}

/**
 * Pause or resume the screen capture feed.
 * POST /pause/screen → { screen_active }
 */
export function pauseScreen(paused: boolean): Promise<PauseScreenResponse> {
  return request<PauseScreenResponse>('/pause/screen', {
    method: 'POST',
    body: JSON.stringify({ paused }),
  })
}

/**
 * Get real current weather for a coordinate.
 * GET /weather?lat=..&lon=.. → { temperature, condition, location_name, unit }
 */
export function getWeather(lat: number, lon: number): Promise<WeatherResponse> {
  return request<WeatherResponse>(`/weather?lat=${lat}&lon=${lon}`)
}
