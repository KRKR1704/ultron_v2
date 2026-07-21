'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL } from '@/lib/api'
import type { WebSocketMessage } from '@/types/ultron'

interface UseUltronSocketReturn {
  isConnected: boolean
  send: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => void
  lastMessage: WebSocketMessage | null
}

const INITIAL_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 30_000

/**
 * Connects to the ULTRON WebSocket at ws://localhost:8000/ws.
 *
 * - Automatically reconnects on disconnect with exponential back-off.
 * - Sends raw audio chunks (Blob / ArrayBuffer / base64 string).
 * - Exposes the last parsed { transcript, response_text, audio_base64, language, mode } message.
 */
export function useUltronSocket(): UseUltronSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(INITIAL_BACKOFF_MS)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    // Clean up any existing socket before reconnecting
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close()
      }
      wsRef.current = null
    }

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) return
        setIsConnected(true)
        backoffRef.current = INITIAL_BACKOFF_MS // reset back-off on successful connect
      }

      ws.onmessage = (event: MessageEvent) => {
        if (unmountedRef.current) return
        try {
          const data = JSON.parse(event.data as string) as WebSocketMessage
          setLastMessage(data)
        } catch {
          // Non-JSON frame — ignore
        }
      }

      ws.onclose = () => {
        if (unmountedRef.current) return
        setIsConnected(false)
        scheduleReconnect()
      }

      ws.onerror = () => {
        // onerror is always followed by onclose, so just log
        console.warn('[useUltronSocket] WebSocket error — will reconnect')
      }
    } catch (err) {
      console.error('[useUltronSocket] Failed to create WebSocket:', err)
      scheduleReconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return
    if (reconnectTimerRef.current) return // already scheduled

    const delay = backoffRef.current
    backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)

    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null
      connect()
    }, delay)
  }, [connect])

  useEffect(() => {
    unmountedRef.current = false
    connect()

    return () => {
      unmountedRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.onopen = null
        wsRef.current.onclose = null
        wsRef.current.onerror = null
        wsRef.current.onmessage = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  const send = useCallback(
    (data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data)
      } else {
        console.warn('[useUltronSocket] Cannot send — socket not open')
      }
    },
    [],
  )

  return { isConnected, send, lastMessage }
}
