'use client'

// Camera widget — MJPEG stream via a single persistent HTTP connection.
// The browser's native <img> element handles the multipart stream,
// so there are no React re-renders per frame and no polling overhead.
// Backend OpenCV owns the device; we never call getUserMedia().

import { useState, useCallback, useRef } from 'react'
import { Camera, CameraOff, Eye, Loader2 } from 'lucide-react'
import { HudPanel, HudButton } from '../hud-panel'
import { cn } from '@/lib/utils'

const API         = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const STREAM_URL  = `${API}/vision/camera/stream`

interface CameraWidgetProps {
  /** Passed from page.tsx — reflects backend camera_active from /status */
  isBackendCameraActive?: boolean
  /** Called after toggle so page.tsx can update its backendStatus state */
  onCameraToggle?: (active: boolean) => void
}

export function CameraWidget({ isBackendCameraActive = true, onCameraToggle }: CameraWidgetProps) {
  const [streamLoaded, setStreamLoaded]     = useState(false)
  const [streamError, setStreamError]       = useState(false)
  const [analysis, setAnalysis]             = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing]       = useState(false)
  const [analysisError, setAnalysisError]   = useState<string | null>(null)
  const [isToggling, setIsToggling]         = useState(false)

  // key forces <img> to remount when camera is re-enabled
  const streamKey = useRef(0)

  // ── Camera on/off toggle ────────────────────────────────────────────────
  const toggleCamera = useCallback(async () => {
    setIsToggling(true)
    try {
      const res = await fetch(`${API}/pause/camera`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paused: isBackendCameraActive }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      // If turning on, force stream img to remount with a fresh URL
      if (data.active) {
        streamKey.current += 1
        setStreamLoaded(false)
        setStreamError(false)
      }
      onCameraToggle?.(data.active)
    } catch (err) {
      console.error('Camera toggle failed:', err)
    } finally {
      setIsToggling(false)
    }
  }, [isBackendCameraActive, onCameraToggle])

  // ── AI analysis ──────────────────────────────────────────────────────────
  const askCamera = useCallback(async () => {
    setIsAnalyzing(true)
    setAnalysis(null)
    setAnalysisError(null)
    try {
      const res = await fetch(`${API}/vision/camera`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: 'What do you see? Describe everything in detail.',
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setAnalysis(data.analysis ?? 'No analysis returned.')
    } catch (err: unknown) {
      setAnalysisError(err instanceof Error ? err.message : 'Analysis failed.')
    } finally {
      setIsAnalyzing(false)
    }
  }, [])

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <HudPanel className="p-4" title="Camera Vision">
      <div className="space-y-3">

        {/* ── Status bar ── */}
        <div className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded border text-[10px] font-mono uppercase tracking-wider',
          isBackendCameraActive
            ? 'bg-cyan-950/30 border-cyan-500/30 text-cyan-400'
            : 'bg-slate-900/50 border-slate-700/50 text-slate-500'
        )}>
          {isBackendCameraActive ? (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              <span>Live feed · 15 fps</span>
            </>
          ) : (
            <>
              <CameraOff className="w-3 h-3" />
              <span>Camera paused</span>
            </>
          )}
        </div>

        {/* ── Video frame ── */}
        <div className={cn(
          'relative rounded-lg overflow-hidden border bg-slate-950',
          'aspect-[4/3]',
          isBackendCameraActive ? 'border-cyan-500/30' : 'border-slate-700/40'
        )}>

          {isBackendCameraActive ? (
            <>
              {/* MJPEG stream — browser handles multipart natively, no React updates */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={streamKey.current}
                src={STREAM_URL}
                alt="Live camera feed"
                className={cn(
                  'w-full h-full object-cover transition-opacity duration-300',
                  streamLoaded && !streamError ? 'opacity-100' : 'opacity-0'
                )}
                onLoad={() => { setStreamLoaded(true); setStreamError(false) }}
                onError={() => { setStreamLoaded(false); setStreamError(true) }}
              />

              {/* Loading overlay — shown until first frame arrives */}
              {!streamLoaded && !streamError && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                  <Loader2 className="w-6 h-6 text-cyan-500/50 animate-spin" />
                  <span className="text-[10px] font-mono text-slate-500">
                    Connecting…
                  </span>
                </div>
              )}

              {/* Error overlay */}
              {streamError && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                  <CameraOff className="w-6 h-6 text-red-500/60" />
                  <span className="text-[10px] font-mono text-red-400">
                    Stream unavailable
                  </span>
                </div>
              )}

              {/* HUD overlay — always on top of stream */}
              {streamLoaded && (
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute top-2 left-2 w-4 h-4 border-l-2 border-t-2 border-cyan-400/60" />
                  <div className="absolute top-2 right-2 w-4 h-4 border-r-2 border-t-2 border-cyan-400/60" />
                  <div className="absolute bottom-8 left-2 w-4 h-4 border-l-2 border-b-2 border-cyan-400/60" />
                  <div className="absolute bottom-8 right-2 w-4 h-4 border-r-2 border-b-2 border-cyan-400/60" />
                  <div className="absolute top-0 left-0 right-0 h-px bg-cyan-400/20 animate-pulse" />
                  <div className="absolute bottom-2 left-2 text-[9px] font-mono text-cyan-400/70">
                    ULTRON VISION · LIVE
                  </div>
                  <div className="absolute bottom-2 right-2 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-[9px] font-mono text-red-400">REC</span>
                  </div>
                </div>
              )}
            </>
          ) : (
            /* Camera inactive */
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
              <CameraOff className="w-7 h-7 text-slate-700" />
              <span className="text-[10px] font-mono text-slate-600">Camera inactive</span>
            </div>
          )}
        </div>

        {/* ── Buttons row ── */}
        <div className="flex gap-2">
          {/* What do you see */}
          <HudButton
            onClick={askCamera}
            disabled={isAnalyzing || !isBackendCameraActive || !streamLoaded}
            variant="primary"
            size="sm"
            icon={isAnalyzing
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <Eye className="w-3 h-3" />
            }
          >
            {isAnalyzing ? 'Analyzing…' : 'What do you see?'}
          </HudButton>

          {/* Camera on/off toggle */}
          <HudButton
            onClick={toggleCamera}
            disabled={isToggling}
            variant={isBackendCameraActive ? 'danger' : 'primary'}
            size="sm"
            icon={isToggling
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : isBackendCameraActive
                ? <CameraOff className="w-3 h-3" />
                : <Camera className="w-3 h-3" />
            }
          >
            {isToggling ? '…' : isBackendCameraActive ? 'Off' : 'On'}
          </HudButton>
        </div>

        {/* ── Analysis result ── */}
        {analysis && (
          <div className="bg-cyan-950/20 border border-cyan-500/20 rounded-lg p-3">
            <div className="text-[10px] font-mono text-cyan-400 mb-1 uppercase tracking-wider">
              Vision Analysis
            </div>
            <p className="text-xs text-cyan-100 leading-relaxed whitespace-pre-wrap">
              {analysis}
            </p>
          </div>
        )}

        {analysisError && (
          <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-2">
            <p className="text-[10px] text-red-400 font-mono">{analysisError}</p>
          </div>
        )}

      </div>
    </HudPanel>
  )
}
