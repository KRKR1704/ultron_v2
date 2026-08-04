'use client'

// FIXED: Replaced useChat/@ai-sdk/react with direct backend API calls;
//        added crypto.randomUUID() session ID; backend audio playback via
//        playAudioBase64; mode switch calls POST /mode API; GET /status
//        polled every 5 seconds; WebSocket for real-time events.

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  Settings,
  Zap,
  Coffee,
  X,
  Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useVoice } from '@/hooks/use-voice'
import { useUltronSocket } from '@/hooks/useUltronSocket'
import { UltronRobot } from '@/components/ultron/ultron-robot'
import { VoiceWaveform } from '@/components/ultron/voice-waveform'
import { HudPanel, HudStatus, HudButton } from '@/components/ultron/hud-panel'
import { ChatMessage } from '@/components/ultron/chat-message'
import { SuggestedPrompts } from '@/components/ultron/quick-actions'
import { LocationWeatherWidget } from '@/components/ultron/widgets/location-weather'
import { CalendarWidget } from '@/components/ultron/widgets/calendar-widget'
import { CameraWidget } from '@/components/ultron/widgets/camera-widget'
import { TasksWidget } from '@/components/ultron/widgets/tasks-widget'
import {
  sendTextMessage,
  switchMode,
  getStatus,
} from '@/lib/api'
import { playAudioBase64, stopAudio, unlockAudioContext } from '@/lib/audio'
import type { UltronMode, WebSocketMessage } from '@/types/ultron'

// ── Local message type ────────────────────────────────────────────────────────

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

type FaceState = 'dormant' | 'waking' | 'listening' | 'thinking' | 'speaking' | 'idle'

// ── Component ─────────────────────────────────────────────────────────────────

export default function UltronPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [personalityMode, setPersonalityMode] = useState<UltronMode>('professional')
  const [voiceEnabled, setVoiceEnabled] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [faceState, setFaceState] = useState<FaceState>('idle')
  const [wakeActive, setWakeActive] = useState(false)
  const [backendStatus, setBackendStatus] = useState<{
    camera: boolean; screen: boolean; wakeWord: boolean
  }>({ camera: false, screen: false, wakeWord: false })

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const wakeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Stable session ID for this app launch
  const sessionId = useRef<string>(
    typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(36).slice(2)
  )

  // Keep startListening in a ref to access inside callbacks
  const startListeningRef = useRef<(() => void) | null>(null)

  // ── Abort / stop helper ─────────────────────────────────────────────────────

  const stopProcessing = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    stopAudio()
    setIsLoading(false)
    setFaceState('idle')
  }, [])

  // ── Voice hook ──────────────────────────────────────────────────────────────

  const {
    isListening,
    isSpeaking,
    transcript,
    startListening,
    stopListening,
    startWakeWordListening,
    stopWakeWordListening,
    isSupported: voiceSupported,
    audioLevel,
  } = useVoice({
    onTranscript: (text) => setInput(text),
    wakeWord: 'ultron',
    onWakeWord: () => {
      if (wakeTimeoutRef.current) clearTimeout(wakeTimeoutRef.current)
      setWakeActive(true)
      setFaceState('waking')
      setTimeout(() => {
        setFaceState('listening')
        startListeningRef.current?.()
      }, 1200)
      wakeTimeoutRef.current = setTimeout(() => {
        setWakeActive(false)
        setFaceState('idle')
      }, 12000)
    },
  })

  useEffect(() => {
    startListeningRef.current = startListening
  }, [startListening])

  // ── Unlock audio playback on the first real user gesture ───────────────────
  // Electron's main process disables the autoplay policy outright (see
  // electron/main.ts), but this is a defense-in-depth fallback for running
  // the Next.js dev server directly in a plain browser tab, where that
  // override doesn't apply — without it, the FIRST wake-word follow-up
  // response (if it's the very first audio played all session, with no
  // prior click/keypress) can be silently blocked by the browser's
  // autoplay policy: no error, the response text appears, but nothing
  // plays. One-time listener, removes itself after firing once.

  useEffect(() => {
    const unlock = () => {
      unlockAudioContext()
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
    window.addEventListener('pointerdown', unlock)
    window.addEventListener('keydown', unlock)
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  // ── Auto-scroll ─────────────────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Face state sync ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (isListening) setFaceState('listening')
    else if (isLoading) setFaceState('thinking')
    else if (isSpeaking) setFaceState('speaking')
    else if (!wakeActive) setFaceState('idle')
  }, [isListening, isLoading, isSpeaking, wakeActive])

  // ── ESC key — abort current request + stop audio ───────────────────────────

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isLoading) {
        e.preventDefault()
        stopProcessing()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isLoading, stopProcessing])

  // ── WebSocket connection ─────────────────────────────────────────────────────
  // useUltronSocket owns the actual connection lifecycle (connect, parse,
  // exponential-backoff reconnect). Frames are handled here synchronously,
  // one call per frame, NOT via a `useEffect` reacting to a "last message"
  // state slot — a single overwritable state slot silently dropped frames
  // whenever several arrived close enough together to land in the same
  // React 18 auto-batched update, which the wake-word follow-up pipeline
  // does by construction (`audio_generating`/`audio`/`done` are broadcast
  // back to back with no real async work between them, since the audio was
  // already fully synthesized before any of the three is sent) — only the
  // LAST frame of that burst was ever actually seen, so 'audio' (and the
  // playback it triggers) was being silently discarded every time,
  // regardless of intent. See useUltronSocket.ts for the full writeup.

  const handleWsMessage = useCallback((msg: WebSocketMessage) => {
    switch (msg.type) {
      case 'wake_word':
        // Backend detected "ultron" and is already capturing the
        // follow-up command by the time this arrives — go straight to
        // 'listening' rather than a fake delay, since capture is real.
        if (wakeTimeoutRef.current) clearTimeout(wakeTimeoutRef.current)
        setWakeActive(true)
        setFaceState('listening')
        break

      case 'transcript':
        // Backend finished transcribing the wake-word follow-up command.
        // An empty transcript means nothing was heard (silence/timeout) —
        // the fallback "I didn't catch that" response still arrives via
        // the 'token'/'audio' frames below, so no separate message here.
        if (msg.text) addMessage('user', msg.text)
        setFaceState('thinking')
        break

      case 'token':
        // Full response text for the wake-word follow-up turn.
        addMessage('assistant', msg.text)
        break

      case 'audio': {
        // Wake-word follow-up response audio, real backend TTS.
        const b64 = msg.audio_base64 ?? ''
        console.log(
          `[wake-word] 'audio' frame received: ${b64.length} base64 chars, ` +
          `voiceEnabled=${voiceEnabled}`
        )
        setFaceState('speaking')
        if (voiceEnabled && b64) {
          playAudioBase64(b64).catch((err) =>
            console.error('[wake-word] playAudioBase64 rejected:', err)
          )
        } else if (!b64) {
          console.warn('[wake-word] \'audio\' frame had an empty audio_base64 — nothing to play.')
        }
        break
      }

      case 'done':
        // Wake-word follow-up turn complete — return to idle and let
        // passive "ultron" detection (already resumed server-side) show
        // as such again.
        setWakeActive(false)
        setFaceState('idle')
        break

      case 'suggestion':
        // Proactive screen suggestion
        addMessage('assistant', msg.text)
        if (voiceEnabled) {
          playAudioBase64(msg.audio_base64 ?? '').catch((err) =>
            console.error('[suggestion] playAudioBase64 rejected:', err)
          )
        }
        break

      case 'camera_alert':
        addMessage('assistant', msg.message)
        break

      default:
        // audio_generating / ping / pong / error — no UI action needed
        // beyond what the surrounding frames already set.
        break
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceEnabled])

  useUltronSocket(handleWsMessage)

  // ── Status polling every 5 seconds ─────────────────────────────────────────

  useEffect(() => {
    const pollStatus = async () => {
      try {
        const status = await getStatus()
        setPersonalityMode(status.mode as UltronMode)
        setBackendStatus({
          camera: status.camera_active,
          screen: status.screen_active,
          wakeWord: status.wake_word_active,
        })
      } catch {
        // Backend offline — silently ignore
      }
    }

    pollStatus()
    const interval = setInterval(pollStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  // ── Message helpers ─────────────────────────────────────────────────────────

  const addMessage = (role: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role,
        content,
        timestamp: new Date(),
      },
    ])
  }

  // ── Send text message ───────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text) return

    // Abort any in-flight request so new message takes over immediately
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    stopAudio()
    addMessage('user', text)
    setInput('')
    setIsLoading(true)
    setFaceState('thinking')

    try {
      const res = await sendTextMessage(text, sessionId.current, controller.signal)

      if (controller.signal.aborted) return

      if (res.mode && res.mode !== personalityMode) {
        setPersonalityMode(res.mode as UltronMode)
      }

      addMessage('assistant', res.response_text)

      if (voiceEnabled && res.audio_base64) {
        setFaceState('speaking')
        await playAudioBase64(res.audio_base64)
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      addMessage('assistant', 'I encountered a connection error. Is the backend running?')
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false)
        setFaceState('idle')
      }
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
      }
    }
  }, [input, personalityMode, voiceEnabled])

  // Submit after voice stops
  const prevListeningRef = useRef(false)
  useEffect(() => {
    if (prevListeningRef.current && !isListening && transcript?.trim()) {
      handleSubmit()
      if (wakeTimeoutRef.current) clearTimeout(wakeTimeoutRef.current)
      setWakeActive(false)
    }
    prevListeningRef.current = isListening
  }, [isListening, transcript, handleSubmit])

  // ── Mode toggle ─────────────────────────────────────────────────────────────

  const togglePersonalityMode = async () => {
    const newMode: UltronMode = personalityMode === 'professional' ? 'casual' : 'professional'
    stopAudio()               // cut any current/queued audio so confirmation plays first
    setPersonalityMode(newMode) // optimistic update

    try {
      const res = await switchMode(newMode)
      if (res.success) {
        setPersonalityMode(res.current_mode as UltronMode)
        if (voiceEnabled && res.confirmation_audio) {
          await playAudioBase64(res.confirmation_audio)
        }
      }
    } catch {
      setPersonalityMode(personalityMode) // revert on failure
    }
  }

  // ── Voice toggle ─────────────────────────────────────────────────────────────

  const toggleVoice = () => {
    if (isListening) stopListening()
    else startListening()
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen bg-background hud-grid relative overflow-hidden flex flex-col">
      {/* Scanline */}
      <div className="hud-scanline" />

      {/* Background ambient glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] bg-cyan-500/5 rounded-full blur-3xl hud-glow" />
      </div>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="flex-shrink-0 px-4 pt-3 pb-2 z-50">
        <HudPanel className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-mono font-bold text-cyan-400 tracking-[0.25em]">
                ULTRON
              </h1>
              <HudStatus label="Status" value="Online" status="online" />
              <HudStatus
                label="Mode"
                value={personalityMode === 'professional' ? 'Pro' : 'Casual'}
                status="online"
              />
              {backendStatus.camera && (
                <HudStatus label="Camera" value="Active" status="online" />
              )}
              {backendStatus.wakeWord && (
                <HudStatus label="Wake" value="Listening" status="online" />
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Wake word toggle */}
              {voiceSupported && (
                <HudButton
                  onClick={() => {
                    if (wakeActive) {
                      stopWakeWordListening()
                      setWakeActive(false)
                      setFaceState('idle')
                    } else {
                      startWakeWordListening()
                    }
                  }}
                  variant={wakeActive ? 'primary' : 'default'}
                  size="sm"
                  icon={<Radio className="w-3 h-3" />}
                >
                  Wake Word
                </HudButton>
              )}

              <HudButton
                onClick={togglePersonalityMode}
                variant="default"
                size="sm"
                icon={
                  personalityMode === 'professional' ? (
                    <Zap className="w-3 h-3" />
                  ) : (
                    <Coffee className="w-3 h-3" />
                  )
                }
              >
                {personalityMode === 'professional' ? 'Professional' : 'Casual'}
              </HudButton>

              <HudButton
                onClick={() => setVoiceEnabled((v) => !v)}
                variant={voiceEnabled ? 'primary' : 'default'}
                size="sm"
                icon={voiceEnabled ? <Volume2 className="w-3 h-3" /> : <VolumeX className="w-3 h-3" />}
              >
                Voice
              </HudButton>

              <HudButton
                onClick={() => setShowSettings((s) => !s)}
                size="sm"
                icon={<Settings className="w-3 h-3" />}
              />
            </div>
          </div>
        </HudPanel>
      </header>

      {/* Settings Panel */}
      {showSettings && (
        <div className="fixed top-20 right-4 z-50">
          <HudPanel className="p-4 w-72" title="Settings">
            <button
              onClick={() => setShowSettings(false)}
              className="absolute top-2 right-2 text-slate-400 hover:text-cyan-400"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="space-y-4 pt-4">
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Session ID</p>
                <p className="text-xs text-slate-600 mt-1 font-mono break-all">
                  {sessionId.current}
                </p>
              </div>
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Wake Word</p>
                <p className="text-sm text-cyan-300 mt-1">Say &quot;ULTRON&quot; to activate hands-free</p>
              </div>
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Voice Synthesis</p>
                <p className="text-sm text-cyan-300 mt-1">{voiceEnabled ? 'Backend TTS Enabled' : 'Disabled'}</p>
              </div>
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Personality Mode</p>
                <p className="text-sm text-cyan-300 mt-1">
                  {personalityMode === 'professional'
                    ? 'Professional & Witty'
                    : 'Friendly & Casual'}
                </p>
              </div>
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Camera Monitor</p>
                <p className="text-sm text-cyan-300 mt-1">
                  {backendStatus.camera ? 'Active' : 'Inactive'}
                </p>
              </div>
              <div>
                <p className="text-xs font-mono text-slate-400 uppercase">Screen Monitor</p>
                <p className="text-sm text-cyan-300 mt-1">
                  {backendStatus.screen ? 'Active' : 'Inactive'}
                </p>
              </div>
            </div>
          </HudPanel>
        </div>
      )}

      {/* ── Main 3-Column Layout ─────────────────────────────────────── */}
      <main className="flex-1 flex gap-3 px-4 pb-4 overflow-hidden min-h-0">

        {/* ── LEFT SIDEBAR: Widgets ─────────────────────────────── */}
        <aside className="w-72 flex-shrink-0 flex flex-col gap-3 overflow-y-auto">
          <LocationWeatherWidget />
          <CalendarWidget sessionId={sessionId.current} />
          <CameraWidget
            isBackendCameraActive={backendStatus.camera}
            onCameraToggle={(active) =>
              setBackendStatus(prev => ({ ...prev, camera: active }))
            }
          />
          <TasksWidget sessionId={sessionId.current} />
        </aside>

        {/* ── CENTER: ULTRON Face ───────────────────────────────── */}
        <div className="w-80 flex-shrink-0 flex flex-col gap-3">
          <HudPanel
            className="flex-1 flex flex-col items-center justify-between py-4 px-2"
            title="Neural Interface"
          >
            <div className="flex-1 flex items-center justify-center w-full">
              <UltronRobot
                state={faceState}
                audioLevel={audioLevel}
                className="w-full h-64"
              />
            </div>

            <div className="w-full px-2">
              {(isListening || isSpeaking) && (
                <div className="mt-2">
                  <VoiceWaveform
                    isActive={isListening || isSpeaking}
                    audioLevel={audioLevel}
                    mode={isListening ? 'listening' : 'speaking'}
                  />
                </div>
              )}

              <div className="mt-3 flex items-center justify-center gap-2">
                <div
                  className={cn(
                    'w-2 h-2 rounded-full transition-colors duration-300',
                    faceState === 'idle'      && 'bg-cyan-400 animate-pulse',
                    faceState === 'waking'    && 'bg-blue-400 animate-ping',
                    faceState === 'listening' && 'bg-green-400 animate-pulse',
                    faceState === 'thinking'  && 'bg-orange-400 animate-bounce',
                    faceState === 'speaking'  && 'bg-cyan-400 animate-pulse',
                    faceState === 'dormant'   && 'bg-slate-600',
                  )}
                />
                <span className="text-xs font-mono text-slate-400 tracking-widest uppercase">
                  {faceState === 'dormant'   && 'Say "ULTRON" to wake'}
                  {faceState === 'waking'    && 'Initializing...'}
                  {faceState === 'idle'      && 'Ready'}
                  {faceState === 'listening' && 'Listening...'}
                  {faceState === 'thinking'  && 'Processing...'}
                  {faceState === 'speaking'  && 'Responding...'}
                </span>
              </div>
            </div>
          </HudPanel>

          {messages.length === 0 && (
            <HudPanel className="p-3" title="Quick Commands">
              <SuggestedPrompts
                onPrompt={(p) => {
                  setInput(p)
                  inputRef.current?.focus()
                }}
                personality={personalityMode}
              />
            </HudPanel>
          )}
        </div>

        {/* ── RIGHT: Chat Area ──────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0">
          <HudPanel
            className="flex-1 flex flex-col overflow-hidden"
            title="Communication Interface"
          >
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                  <p className="text-slate-500 text-sm font-mono">
                    {personalityMode === 'professional'
                      ? 'Awaiting your command, sir.'
                      : "Hey! What's on your mind?"}
                  </p>
                  <p className="text-slate-600 text-xs font-mono">
                    Type below or say &quot;ULTRON&quot; to speak
                  </p>
                </div>
              ) : (
                <>
                  {messages.map((message) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      isStreaming={false}
                    />
                  ))}

                  {isLoading && (
                    <div className="flex items-center gap-2 text-cyan-400 text-sm font-mono pl-2">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0ms]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:150ms]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:300ms]" />
                      </div>
                      Processing request...
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Bar */}
            <div className="flex-shrink-0 p-4 border-t border-cyan-500/20">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSubmit()
                }}
                className="flex items-center gap-3"
              >
                {voiceSupported && (
                  <HudButton
                    type="button"
                    onClick={toggleVoice}
                    variant={isListening ? 'danger' : 'default'}
                    className={cn('flex-shrink-0', isListening && 'animate-pulse')}
                    icon={isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  />
                )}

                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={isListening ? 'Listening...' : isLoading ? 'Processing… press Esc to stop' : 'Enter command...'}
                  disabled={isListening}
                  className={cn(
                    'flex-1 bg-slate-900/50 border border-cyan-500/30 rounded px-4 py-3',
                    'text-cyan-100 placeholder:text-slate-500 font-mono text-sm',
                    'focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50',
                    'disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200',
                    isLoading && 'border-orange-500/40',
                  )}
                />

                {isLoading ? (
                  <HudButton
                    type="button"
                    variant="danger"
                    onClick={stopProcessing}
                    icon={<X className="w-4 h-4" />}
                    title="Stop (Esc)"
                  >
                    Stop
                  </HudButton>
                ) : (
                  <HudButton
                    type="submit"
                    variant="primary"
                    disabled={!input.trim()}
                    icon={<Send className="w-4 h-4" />}
                  >
                    Send
                  </HudButton>
                )}
              </form>

              {isListening && (
                <div className="mt-3">
                  <VoiceWaveform isActive audioLevel={audioLevel} mode="listening" />
                </div>
              )}
            </div>
          </HudPanel>
        </div>
      </main>
    </div>
  )
}
