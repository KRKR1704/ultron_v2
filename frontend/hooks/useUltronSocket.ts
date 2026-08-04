'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL } from '@/lib/api'
import type { WebSocketMessage } from '@/types/ultron'

interface UseUltronSocketReturn {
  isConnected: boolean
  send: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => void
}

const INITIAL_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 10_000

/**
 * Module-level connection singleton — there is exactly one physical
 * WebSocket for the whole app, and it must survive React remounts
 * (Strict Mode's dev-mode double-invoke, Next.js Fast Refresh) instead
 * of being torn down and reconnected on every one. Each unnecessary
 * reconnect is itself a window in which a backend broadcast (e.g. the
 * wake-word follow-up's "audio" frame) can arrive and be silently
 * missed, so avoiding gratuitous churn here directly shrinks that
 * window on top of the backoff fix below.
 */
let sharedWs: WebSocket | null = null
let backoff = INITIAL_BACKOFF_MS
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

interface Listener {
  onOpen: () => void
  onClose: () => void
  onMessage: (msg: WebSocketMessage) => void
}
const listeners = new Set<Listener>()

function log(...args: unknown[]): void {
  console.log('[useUltronSocket]', ...args)
}

function connect(): void {
  if (sharedWs && (sharedWs.readyState === WebSocket.OPEN || sharedWs.readyState === WebSocket.CONNECTING)) {
    return // already connected/connecting — nothing to do
  }
  if (reconnectTimer) return // a reconnect is already scheduled

  try {
    const ws = new WebSocket(WS_URL)
    sharedWs = ws

    ws.onopen = () => {
      log('connected —', WS_URL)
      backoff = INITIAL_BACKOFF_MS // reset back-off on successful connect
      listeners.forEach((l) => l.onOpen())
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as WebSocketMessage
        listeners.forEach((l) => l.onMessage(data))
      } catch {
        // Non-JSON frame — ignore
      }
    }

    ws.onclose = (event: CloseEvent) => {
      // The WebSocket 'error' event carries no usable detail by spec —
      // MDN: it "does not contain any information about what
      // specifically went wrong". The real diagnostic signal is the
      // close code: 1000/1001 = normal / going-away (clean); 1006 =
      // abnormal closure, no close frame received at all — e.g. the
      // backend process was killed outright rather than closing the
      // socket itself. In dev, `uvicorn --reload` restarts the entire
      // backend process (uvicorn/supervisors/basereload.py: `restart()`
      // kills the whole worker and spawns a fresh one) on ANY watched
      // .py file save, taking every open WebSocket down with it — code
      // 1006 here during an active dev session is that, not a network
      // fault.
      const upcomingDelay = backoff
      log(
        `closed — code=${event.code} reason="${event.reason || '(none)'}" ` +
        `wasClean=${event.wasClean} — reconnecting in ${upcomingDelay}ms`,
      )
      sharedWs = null
      listeners.forEach((l) => l.onClose())
      scheduleReconnect()
    }

    ws.onerror = () => {
      // Always followed by onclose (per spec), which logs the actual
      // diagnostic detail above — this just marks that an error, not a
      // clean close, is what's about to be reported there.
      log(`error event (readyState=${ws.readyState}) — see the following 'closed' log for the real cause`)
    }
  } catch (err) {
    log('failed to create WebSocket:', err)
    scheduleReconnect()
  }
}

function scheduleReconnect(): void {
  if (reconnectTimer) return // already scheduled

  const delay = backoff
  backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connect()
  }, delay)
}

/**
 * Connects to the ULTRON WebSocket at ws://localhost:8000/ws.
 *
 * - One shared connection for the whole app (see module-level singleton
 *   above) — automatically reconnects on disconnect with exponential
 *   back-off, and survives component remounts without churning.
 * - Sends raw audio chunks (Blob / ArrayBuffer / base64 string).
 * - *Every* incoming frame is delivered to `onMessage` synchronously, one
 *   call per frame, in arrival order — this does NOT go through React
 *   state. It used to: a single `lastMessage` state slot updated via
 *   `setLastMessage(msg)` on each frame, read back out via a `useEffect`
 *   keyed on that state. That silently dropped frames whenever several
 *   arrived close enough together to land in the same React 18
 *   auto-batched update — which the wake-word follow-up pipeline does by
 *   construction: `audio_generating`/`audio`/`done` are broadcast back
 *   to back with no real async work between them (the audio was already
 *   fully synthesized before any of the three is sent), so all three
 *   routinely batch into one render and only the LAST one
 *   (`setLastMessage` is a plain overwrite, not functional) ever reached
 *   a consumer — `audio_generating` and `audio` were being discarded
 *   before anything ever read them, every single time, regardless of
 *   intent. Confirmed directly: instrumenting `WebSocket.onmessage`
 *   itself showed all 5 frames arriving individually every time, while
 *   the old React-state-driven consumer only ever observed `done`.
 *   Dispatching straight to a callback sidesteps the batching entirely —
 *   there is no shared state for concurrent updates to collapse.
 */
export function useUltronSocket(
  onMessage?: (msg: WebSocketMessage) => void,
): UseUltronSocketReturn {
  const [isConnected, setIsConnected] = useState(
    () => sharedWs?.readyState === WebSocket.OPEN,
  )

  // Always call the latest onMessage without re-subscribing the listener
  // on every render (the caller's callback identity may change often,
  // e.g. it closes over other state like `voiceEnabled`).
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    const listener: Listener = {
      onOpen: () => setIsConnected(true),
      onClose: () => setIsConnected(false),
      onMessage: (msg) => onMessageRef.current?.(msg),
    }
    listeners.add(listener)
    // Re-sync in case readyState changed between initial render and commit.
    setIsConnected(sharedWs?.readyState === WebSocket.OPEN)
    connect()

    return () => {
      listeners.delete(listener)
      // Intentionally does NOT close sharedWs — the connection is
      // app-global and must outlive this component instance.
    }
  }, [])

  const send = useCallback(
    (data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
      if (sharedWs?.readyState === WebSocket.OPEN) {
        sharedWs.send(data)
      } else {
        log('cannot send — socket not open')
      }
    },
    [],
  )

  return { isConnected, send }
}
