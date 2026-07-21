'use client'

import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

type FaceState = 'dormant' | 'waking' | 'listening' | 'thinking' | 'speaking' | 'idle'

interface UltronFaceProps {
  state: FaceState
  audioLevel?: number
  className?: string
}

export function UltronFace({ state, audioLevel = 0, className }: UltronFaceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number | null>(null)
  const timeRef = useRef(0)
  const wakeProgressRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = 320
    const H = 400
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr
    canvas.height = H * dpr
    ctx.scale(dpr, dpr)

    const cx = W / 2
    const cy = H / 2

    // Color palettes per state
    const palette = {
      dormant:  { primary: '#1a2a3a', eye: '#003344', glow: 'rgba(0,80,100,0.1)',  scan: 'rgba(0,100,130,0.15)' },
      waking:   { primary: '#00aacc', eye: '#00d4ff', glow: 'rgba(0,180,220,0.4)', scan: 'rgba(0,200,255,0.3)' },
      idle:     { primary: '#00d4ff', eye: '#00eeff', glow: 'rgba(0,212,255,0.3)', scan: 'rgba(0,212,255,0.2)' },
      listening:{ primary: '#00ff99', eye: '#00ffcc', glow: 'rgba(0,255,150,0.4)', scan: 'rgba(0,255,150,0.25)' },
      thinking: { primary: '#ff9900', eye: '#ffcc00', glow: 'rgba(255,150,0,0.4)', scan: 'rgba(255,150,0,0.25)' },
      speaking: { primary: '#00ccff', eye: '#88eeff', glow: 'rgba(0,200,255,0.45)', scan: 'rgba(0,200,255,0.3)' },
    }

    const col = palette[state] ?? palette.idle

    // Track wake-up animation
    if (state === 'waking') {
      wakeProgressRef.current = Math.min(1, wakeProgressRef.current + 0.015)
    } else if (state === 'dormant') {
      wakeProgressRef.current = Math.max(0, wakeProgressRef.current - 0.05)
    } else {
      wakeProgressRef.current = 1
    }

    const draw = () => {
      const t = timeRef.current
      const wp = wakeProgressRef.current // 0=dormant, 1=fully awake
      ctx.clearRect(0, 0, W, H)

      // ── Background ambient glow ──────────────────────────────────────
      const bgGrad = ctx.createRadialGradient(cx, cy, 20, cx, cy, 200)
      bgGrad.addColorStop(0, col.glow)
      bgGrad.addColorStop(1, 'transparent')
      ctx.fillStyle = bgGrad
      ctx.fillRect(0, 0, W, H)

      // ── Outer head silhouette ───────────────────────────────────────
      const headW = 160
      const headH = 200
      const headY = cy - 20
      ctx.save()
      ctx.globalAlpha = 0.15 + wp * 0.2
      ctx.beginPath()
      ctx.ellipse(cx, headY, headW / 2, headH / 2, 0, 0, Math.PI * 2)
      ctx.strokeStyle = col.primary
      ctx.lineWidth = 2
      ctx.shadowBlur = 20
      ctx.shadowColor = col.primary
      ctx.stroke()
      ctx.restore()

      // ── Hexagonal face plate segments ──────────────────────────────
      const drawHexPlate = (x: number, y: number, r: number, alpha: number, rotation = 0) => {
        ctx.save()
        ctx.globalAlpha = alpha * wp
        ctx.translate(x, y)
        ctx.rotate(rotation)
        ctx.beginPath()
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2 - Math.PI / 6
          i === 0 ? ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r)
                  : ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r)
        }
        ctx.closePath()
        ctx.strokeStyle = col.primary
        ctx.lineWidth = 1
        ctx.shadowBlur = 8
        ctx.shadowColor = col.primary
        ctx.stroke()
        ctx.restore()
      }

      drawHexPlate(cx, headY - 50, 30, 0.25 + Math.sin(t) * 0.05, t * 0.3)
      drawHexPlate(cx - 55, headY - 10, 20, 0.2 + Math.sin(t + 1) * 0.04, -t * 0.4)
      drawHexPlate(cx + 55, headY - 10, 20, 0.2 + Math.sin(t + 2) * 0.04, t * 0.4)
      drawHexPlate(cx, headY + 60, 25, 0.2 + Math.sin(t + 3) * 0.04, -t * 0.3)

      // ── Scanning line ────────────────────────────────────────────────
      if (state !== 'dormant') {
        const scanY = headY - 90 + ((t * 60) % 180)
        const scanGrad = ctx.createLinearGradient(cx - 80, scanY, cx + 80, scanY)
        scanGrad.addColorStop(0, 'transparent')
        scanGrad.addColorStop(0.5, col.scan)
        scanGrad.addColorStop(1, 'transparent')
        ctx.save()
        ctx.globalAlpha = wp
        ctx.fillStyle = scanGrad
        ctx.fillRect(cx - 80, scanY - 1, 160, 2)
        ctx.restore()
      }

      // ── Eyes ─────────────────────────────────────────────────────────
      const eyeY = headY - 25
      const eyeSpacing = 45
      const eyeOpenness = state === 'dormant' ? 0 : state === 'waking'
        ? Math.max(0, (wp - 0.3) / 0.7)
        : 1

      const drawEye = (ex: number) => {
        const eyeW = 32
        const eyeH = 14 * eyeOpenness
        if (eyeH < 0.5) {
          // Just a line (dormant)
          ctx.save()
          ctx.beginPath()
          ctx.moveTo(ex - eyeW / 2, eyeY)
          ctx.lineTo(ex + eyeW / 2, eyeY)
          ctx.strokeStyle = col.primary
          ctx.lineWidth = 1.5
          ctx.globalAlpha = 0.4
          ctx.stroke()
          ctx.restore()
          return
        }

        // Eye socket glow
        ctx.save()
        ctx.globalAlpha = 0.2 * wp
        ctx.beginPath()
        ctx.ellipse(ex, eyeY, eyeW / 2 + 6, eyeH + 8, 0, 0, Math.PI * 2)
        ctx.fillStyle = col.eye
        ctx.fill()
        ctx.restore()

        // Eye outline
        ctx.save()
        ctx.beginPath()
        ctx.ellipse(ex, eyeY, eyeW / 2, eyeH, 0, 0, Math.PI * 2)
        ctx.strokeStyle = col.primary
        ctx.lineWidth = 1.5
        ctx.shadowBlur = 12
        ctx.shadowColor = col.primary
        ctx.stroke()
        ctx.restore()

        // Iris
        const irisR = eyeH * 0.75
        const irisGrad = ctx.createRadialGradient(ex, eyeY, 0, ex, eyeY, irisR)
        irisGrad.addColorStop(0, '#ffffff')
        irisGrad.addColorStop(0.2, col.eye)
        irisGrad.addColorStop(0.7, col.primary)
        irisGrad.addColorStop(1, 'transparent')
        ctx.save()
        ctx.globalAlpha = wp
        ctx.beginPath()
        ctx.arc(ex, eyeY, irisR, 0, Math.PI * 2)
        ctx.fillStyle = irisGrad
        ctx.shadowBlur = 20
        ctx.shadowColor = col.eye
        ctx.fill()
        ctx.restore()

        // Pupil / scanner dot
        if (state === 'thinking') {
          const px = ex + Math.cos(t * 3) * (eyeW * 0.15)
          const py = eyeY + Math.sin(t * 3) * (eyeH * 0.3)
          ctx.save()
          ctx.beginPath()
          ctx.arc(px, py, 3, 0, Math.PI * 2)
          ctx.fillStyle = '#ffffff'
          ctx.shadowBlur = 10
          ctx.shadowColor = '#ffffff'
          ctx.fill()
          ctx.restore()
        } else {
          ctx.save()
          ctx.beginPath()
          ctx.arc(ex, eyeY, 3, 0, Math.PI * 2)
          ctx.fillStyle = '#ffffff'
          ctx.shadowBlur = 8
          ctx.shadowColor = '#ffffff'
          ctx.fill()
          ctx.restore()
        }

        // Scanning line through eye (listening)
        if (state === 'listening' || state === 'speaking') {
          const scanOffset = Math.sin(t * 4) * eyeH * 0.7
          ctx.save()
          ctx.globalAlpha = 0.6
          ctx.beginPath()
          ctx.moveTo(ex - eyeW / 2, eyeY + scanOffset)
          ctx.lineTo(ex + eyeW / 2, eyeY + scanOffset)
          ctx.strokeStyle = col.eye
          ctx.lineWidth = 1
          ctx.shadowBlur = 6
          ctx.shadowColor = col.eye
          ctx.stroke()
          ctx.restore()
        }
      }

      drawEye(cx - eyeSpacing)
      drawEye(cx + eyeSpacing)

      // ── Nose bridge ─────────────────────────────────────────────────
      ctx.save()
      ctx.globalAlpha = 0.4 * wp
      ctx.beginPath()
      ctx.moveTo(cx, eyeY + 8)
      ctx.lineTo(cx - 6, headY + 8)
      ctx.lineTo(cx + 6, headY + 8)
      ctx.strokeStyle = col.primary
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.restore()

      // ── Mouth / speaker grill ────────────────────────────────────────
      const mouthY = headY + 40
      const mouthW = 80

      if (state === 'speaking') {
        // Animated waveform mouth
        ctx.save()
        ctx.globalAlpha = wp
        ctx.beginPath()
        const bars = 12
        for (let i = 0; i < bars; i++) {
          const bx = cx - mouthW / 2 + (i / (bars - 1)) * mouthW
          const height = 4 + Math.sin(t * 6 + i * 0.8) * (8 + audioLevel * 20)
          ctx.moveTo(bx, mouthY - height / 2)
          ctx.lineTo(bx, mouthY + height / 2)
        }
        ctx.strokeStyle = col.primary
        ctx.lineWidth = 3
        ctx.lineCap = 'round'
        ctx.shadowBlur = 10
        ctx.shadowColor = col.primary
        ctx.stroke()
        ctx.restore()
      } else {
        // Static grill lines
        const grillLines = 5
        ctx.save()
        ctx.globalAlpha = 0.3 * wp
        for (let i = 0; i < grillLines; i++) {
          const lx = cx - mouthW / 2 + (i / (grillLines - 1)) * mouthW
          ctx.beginPath()
          ctx.moveTo(lx, mouthY - 8)
          ctx.lineTo(lx, mouthY + 8)
          ctx.strokeStyle = col.primary
          ctx.lineWidth = 2
          ctx.lineCap = 'round'
          ctx.stroke()
        }
        ctx.restore()
      }

      // ── Jaw / chin detail lines ─────────────────────────────────────
      ctx.save()
      ctx.globalAlpha = 0.3 * wp
      ctx.beginPath()
      ctx.moveTo(cx - 50, headY + 75)
      ctx.quadraticCurveTo(cx, headY + 100, cx + 50, headY + 75)
      ctx.strokeStyle = col.primary
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.restore()

      // ── Brow / forehead detail ──────────────────────────────────────
      ctx.save()
      ctx.globalAlpha = 0.35 * wp
      // Left brow
      ctx.beginPath()
      ctx.moveTo(cx - eyeSpacing - 20, eyeY - 20)
      ctx.lineTo(cx - eyeSpacing + 16, eyeY - 16)
      ctx.strokeStyle = col.primary
      ctx.lineWidth = 2
      ctx.lineCap = 'round'
      ctx.shadowBlur = 6
      ctx.shadowColor = col.primary
      ctx.stroke()
      // Right brow
      ctx.beginPath()
      ctx.moveTo(cx + eyeSpacing + 20, eyeY - 20)
      ctx.lineTo(cx + eyeSpacing - 16, eyeY - 16)
      ctx.stroke()
      ctx.restore()

      // ── Cheek data panels ──────────────────────────────────────────
      const drawCheekPanel = (side: number) => {
        const px = cx + side * 68
        const py = headY + 10
        ctx.save()
        ctx.globalAlpha = 0.18 * wp
        for (let row = 0; row < 4; row++) {
          for (let col2 = 0; col2 < 2; col2++) {
            const rx = px + (col2 - 0.5) * 12
            const ry = py + row * 10
            const active = Math.sin(t * 3 + row + col2) > 0.3
            ctx.beginPath()
            ctx.rect(rx - 4, ry - 3, 8, 5)
            ctx.fillStyle = active ? col.primary : 'transparent'
            ctx.strokeStyle = col.primary
            ctx.lineWidth = 0.5
            ctx.stroke()
            if (active) ctx.fill()
          }
        }
        ctx.restore()
      }
      drawCheekPanel(-1)
      drawCheekPanel(1)

      // ── Listening audio ripples around head ─────────────────────────
      if (state === 'listening') {
        for (let ring = 0; ring < 3; ring++) {
          const progress = ((t * 0.8 + ring * 0.33) % 1)
          const rr = 90 + progress * 60
          const alpha = (1 - progress) * 0.35
          ctx.save()
          ctx.globalAlpha = alpha
          ctx.beginPath()
          ctx.ellipse(cx, headY, rr, rr * 1.2, 0, 0, Math.PI * 2)
          ctx.strokeStyle = col.primary
          ctx.lineWidth = 1.5
          ctx.shadowBlur = 8
          ctx.shadowColor = col.primary
          ctx.stroke()
          ctx.restore()
        }
      }

      // ── Thinking rotating arcs ──────────────────────────────────────
      if (state === 'thinking') {
        for (let arc = 0; arc < 2; arc++) {
          ctx.save()
          ctx.translate(cx, headY)
          ctx.rotate(t * (arc === 0 ? 1.2 : -0.8))
          ctx.globalAlpha = 0.5
          ctx.beginPath()
          ctx.arc(0, 0, 100 + arc * 14, 0, Math.PI * 1.2)
          ctx.strokeStyle = col.primary
          ctx.lineWidth = 1.5
          ctx.shadowBlur = 10
          ctx.shadowColor = col.primary
          ctx.stroke()
          ctx.restore()
        }
      }

      // ── Wake-up power-on effect ─────────────────────────────────────
      if (state === 'waking' && wp < 0.95) {
        const flashAlpha = Math.max(0, 0.6 - wp * 0.7)
        ctx.save()
        ctx.globalAlpha = flashAlpha
        ctx.fillStyle = col.primary
        const sweepGrad = ctx.createLinearGradient(cx - 80, headY - 100 + wp * 200, cx + 80, headY - 100 + wp * 200)
        sweepGrad.addColorStop(0, 'transparent')
        sweepGrad.addColorStop(0.5, col.glow)
        sweepGrad.addColorStop(1, 'transparent')
        ctx.fillStyle = sweepGrad
        ctx.fillRect(cx - 80, headY - 100 + wp * 200 - 4, 160, 8)
        ctx.restore()
      }

      // ── Status label ────────────────────────────────────────────────
      const labels: Record<FaceState, string> = {
        dormant:   'DORMANT',
        waking:    'INITIALIZING',
        idle:      'STANDBY',
        listening: 'LISTENING',
        thinking:  'PROCESSING',
        speaking:  'RESPONDING',
      }
      ctx.save()
      ctx.globalAlpha = 0.6 * wp
      ctx.font = '700 10px "JetBrains Mono", monospace'
      ctx.textAlign = 'center'
      ctx.letterSpacing = '0.3em'
      ctx.fillStyle = col.primary
      ctx.shadowBlur = 8
      ctx.shadowColor = col.primary
      ctx.fillText(labels[state], cx, H - 24)
      ctx.restore()

      // ── Corner bracket decorations ──────────────────────────────────
      const bracketLen = 16
      const bracketPad = 10
      const corners = [
        { x: bracketPad, y: bracketPad, dx: 1, dy: 1 },
        { x: W - bracketPad, y: bracketPad, dx: -1, dy: 1 },
        { x: bracketPad, y: H - bracketPad, dx: 1, dy: -1 },
        { x: W - bracketPad, y: H - bracketPad, dx: -1, dy: -1 },
      ]
      ctx.save()
      ctx.globalAlpha = 0.4 + Math.sin(t) * 0.1
      ctx.strokeStyle = col.primary
      ctx.lineWidth = 1.5
      ctx.shadowBlur = 6
      ctx.shadowColor = col.primary
      corners.forEach(({ x, y, dx, dy }) => {
        ctx.beginPath()
        ctx.moveTo(x + dx * bracketLen, y)
        ctx.lineTo(x, y)
        ctx.lineTo(x, y + dy * bracketLen)
        ctx.stroke()
      })
      ctx.restore()

      timeRef.current += 0.018
      if (state === 'waking') {
        wakeProgressRef.current = Math.min(1, wakeProgressRef.current + 0.015)
      } else if (state === 'dormant') {
        wakeProgressRef.current = Math.max(0, wakeProgressRef.current - 0.04)
      }

      animRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [state, audioLevel])

  return (
    <div className={cn('relative flex items-center justify-center', className)}>
      <canvas
        ref={canvasRef}
        className="w-[320px] h-[400px]"
        style={{ background: 'transparent' }}
        aria-label={`ULTRON face - state: ${state}`}
      />
    </div>
  )
}
