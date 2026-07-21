'use client'

import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

export type RobotState = 'dormant' | 'waking' | 'listening' | 'thinking' | 'speaking' | 'idle'

interface UltronRobotProps {
  state: RobotState
  audioLevel?: number
  className?: string
}

export function UltronRobot({ state, audioLevel = 0, className }: UltronRobotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const timeRef = useRef(0)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted) return
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.scale(dpr, dpr)
    }
    resize()
    window.addEventListener('resize', resize)

    const getStateColor = () => {
      switch (state) {
        case 'dormant': return { primary: '#1a3a4a', glow: '#0a1520', eye: '#2a4a5a' }
        case 'waking': return { primary: '#00d4ff', glow: '#0088aa', eye: '#00ffff' }
        case 'listening': return { primary: '#00ff88', glow: '#00aa55', eye: '#00ffaa' }
        case 'thinking': return { primary: '#ff8800', glow: '#aa5500', eye: '#ffaa00' }
        case 'speaking': return { primary: '#00d4ff', glow: '#0088ff', eye: '#00ffff' }
        case 'idle': return { primary: '#00d4ff', glow: '#006688', eye: '#00aacc' }
        default: return { primary: '#00d4ff', glow: '#0088aa', eye: '#00ffff' }
      }
    }

    const animate = () => {
      timeRef.current += 0.016
      const t = timeRef.current
      const colors = getStateColor()
      const w = canvas.getBoundingClientRect().width
      const h = canvas.getBoundingClientRect().height
      const cx = w / 2
      const cy = h / 2

      ctx.clearRect(0, 0, w, h)

      // Background glow
      const glowGradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, w * 0.45)
      glowGradient.addColorStop(0, colors.glow + '40')
      glowGradient.addColorStop(0.5, colors.glow + '10')
      glowGradient.addColorStop(1, 'transparent')
      ctx.fillStyle = glowGradient
      ctx.fillRect(0, 0, w, h)

      // Robot head outline
      const headWidth = w * 0.55
      const headHeight = h * 0.65
      const headX = cx - headWidth / 2
      const headY = cy - headHeight / 2 - h * 0.02

      // Head shape with rounded corners
      ctx.beginPath()
      ctx.roundRect(headX, headY, headWidth, headHeight, 20)
      ctx.strokeStyle = colors.primary
      ctx.lineWidth = 3
      ctx.stroke()

      // Inner head glow
      const innerGlow = ctx.createLinearGradient(headX, headY, headX, headY + headHeight)
      innerGlow.addColorStop(0, colors.glow + '20')
      innerGlow.addColorStop(0.5, colors.glow + '08')
      innerGlow.addColorStop(1, colors.glow + '15')
      ctx.fillStyle = innerGlow
      ctx.fill()

      // Forehead panel
      ctx.beginPath()
      ctx.roundRect(headX + 15, headY + 12, headWidth - 30, 25, 8)
      ctx.strokeStyle = colors.primary + '60'
      ctx.lineWidth = 1
      ctx.stroke()

      // Forehead indicator lights
      const lightCount = 5
      const lightSpacing = (headWidth - 60) / (lightCount - 1)
      for (let i = 0; i < lightCount; i++) {
        const lx = headX + 30 + i * lightSpacing
        const ly = headY + 24
        const pulse = state !== 'dormant' ? Math.sin(t * 3 + i * 0.5) * 0.3 + 0.7 : 0.2
        ctx.beginPath()
        ctx.arc(lx, ly, 4, 0, Math.PI * 2)
        ctx.fillStyle = colors.eye + Math.floor(pulse * 255).toString(16).padStart(2, '0')
        ctx.fill()
      }

      // Eyes container
      const eyeContainerY = headY + headHeight * 0.35
      const eyeContainerWidth = headWidth * 0.8
      const eyeContainerHeight = 50
      const eyeContainerX = cx - eyeContainerWidth / 2

      ctx.beginPath()
      ctx.roundRect(eyeContainerX, eyeContainerY, eyeContainerWidth, eyeContainerHeight, 10)
      ctx.strokeStyle = colors.primary + '40'
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.fillStyle = '#0a1520'
      ctx.fill()

      // Eyes
      const eyeWidth = 45
      const eyeHeight = state === 'dormant' ? 4 : state === 'waking' ? 15 + Math.sin(t * 8) * 10 : 30
      const eyeSpacing = 35
      const eyeY = eyeContainerY + eyeContainerHeight / 2

      // Left eye
      const leftEyeX = cx - eyeSpacing - eyeWidth / 2
      drawEye(ctx, leftEyeX, eyeY, eyeWidth, eyeHeight, colors, state, t, audioLevel, -1)

      // Right eye
      const rightEyeX = cx + eyeSpacing - eyeWidth / 2
      drawEye(ctx, rightEyeX, eyeY, eyeWidth, eyeHeight, colors, state, t, audioLevel, 1)

      // Nose/center piece
      ctx.beginPath()
      ctx.moveTo(cx, eyeContainerY + eyeContainerHeight + 10)
      ctx.lineTo(cx - 8, eyeContainerY + eyeContainerHeight + 30)
      ctx.lineTo(cx + 8, eyeContainerY + eyeContainerHeight + 30)
      ctx.closePath()
      ctx.strokeStyle = colors.primary + '60'
      ctx.lineWidth = 2
      ctx.stroke()

      // Mouth area
      const mouthY = headY + headHeight * 0.72
      const mouthWidth = headWidth * 0.5
      const mouthHeight = 35
      const mouthX = cx - mouthWidth / 2

      ctx.beginPath()
      ctx.roundRect(mouthX, mouthY, mouthWidth, mouthHeight, 8)
      ctx.strokeStyle = colors.primary + '50'
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.fillStyle = '#050a10'
      ctx.fill()

      // Mouth bars (audio visualizer when speaking)
      const barCount = 9
      const barWidth = (mouthWidth - 20) / barCount - 2
      for (let i = 0; i < barCount; i++) {
        const bx = mouthX + 10 + i * (barWidth + 2)
        let barHeight = 5

        if (state === 'speaking') {
          barHeight = 5 + audioLevel * 20 + Math.sin(t * 10 + i * 0.8) * 8
        } else if (state === 'listening') {
          barHeight = 5 + Math.sin(t * 4 + i * 0.5) * 4
        } else if (state === 'thinking') {
          barHeight = 5 + Math.abs(Math.sin(t * 2 + i * 0.3)) * 6
        }

        const by = mouthY + mouthHeight / 2 - barHeight / 2
        ctx.beginPath()
        ctx.roundRect(bx, by, barWidth, barHeight, 2)
        ctx.fillStyle = colors.eye
        ctx.fill()
      }

      // Chin detail
      ctx.beginPath()
      ctx.moveTo(cx - 30, headY + headHeight - 15)
      ctx.lineTo(cx, headY + headHeight - 5)
      ctx.lineTo(cx + 30, headY + headHeight - 15)
      ctx.strokeStyle = colors.primary + '40'
      ctx.lineWidth = 2
      ctx.stroke()

      // Side panels (ears)
      const earWidth = 15
      const earHeight = 60
      const earY = cy - earHeight / 2

      // Left ear
      ctx.beginPath()
      ctx.roundRect(headX - earWidth - 5, earY, earWidth, earHeight, 5)
      ctx.strokeStyle = colors.primary + '70'
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.fillStyle = colors.glow + '20'
      ctx.fill()

      // Right ear
      ctx.beginPath()
      ctx.roundRect(headX + headWidth + 5, earY, earWidth, earHeight, 5)
      ctx.strokeStyle = colors.primary + '70'
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.fillStyle = colors.glow + '20'
      ctx.fill()

      // Scanning line effect when listening/thinking
      if (state === 'listening' || state === 'thinking') {
        const scanY = headY + (Math.sin(t * 2) * 0.5 + 0.5) * headHeight
        ctx.beginPath()
        ctx.moveTo(headX + 10, scanY)
        ctx.lineTo(headX + headWidth - 10, scanY)
        ctx.strokeStyle = colors.eye + '60'
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // Pulsing outer ring when active
      if (state !== 'dormant') {
        const pulseRadius = w * 0.42 + Math.sin(t * 2) * 5
        ctx.beginPath()
        ctx.arc(cx, cy, pulseRadius, 0, Math.PI * 2)
        ctx.strokeStyle = colors.primary + '30'
        ctx.lineWidth = 1
        ctx.stroke()
      }

      // Rotating arcs when thinking
      if (state === 'thinking') {
        for (let i = 0; i < 3; i++) {
          const arcRadius = w * 0.38 + i * 10
          ctx.beginPath()
          ctx.arc(cx, cy, arcRadius, t * (1 + i * 0.3) + i, t * (1 + i * 0.3) + i + Math.PI * 0.5)
          ctx.strokeStyle = colors.primary + '40'
          ctx.lineWidth = 2
          ctx.stroke()
        }
      }

      // Status text
      ctx.font = '12px monospace'
      ctx.fillStyle = colors.primary
      ctx.textAlign = 'center'
      const statusText = state.toUpperCase()
      ctx.fillText(`[ ${statusText} ]`, cx, h - 20)

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationRef.current)
    }
  }, [state, audioLevel, mounted])

  if (!mounted) {
    return (
      <div className={cn("w-full h-full bg-slate-900/50 rounded-lg", className)} />
    )
  }

  return (
    <div className={cn("relative w-full h-full", className)}>
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ display: 'block' }}
      />
      
      {/* Corner decorations */}
      <div className="absolute top-2 left-2 w-4 h-4 border-l-2 border-t-2 border-cyan-500/50" />
      <div className="absolute top-2 right-2 w-4 h-4 border-r-2 border-t-2 border-cyan-500/50" />
      <div className="absolute bottom-2 left-2 w-4 h-4 border-l-2 border-b-2 border-cyan-500/50" />
      <div className="absolute bottom-2 right-2 w-4 h-4 border-r-2 border-b-2 border-cyan-500/50" />
    </div>
  )
}

function drawEye(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  colors: { primary: string; glow: string; eye: string },
  state: RobotState,
  t: number,
  audioLevel: number,
  side: number
) {
  const centerX = x + width / 2
  const centerY = y

  // Eye socket
  ctx.beginPath()
  ctx.ellipse(centerX, centerY, width / 2, height / 2, 0, 0, Math.PI * 2)
  
  // Eye glow gradient
  const eyeGradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, width / 2)
  eyeGradient.addColorStop(0, colors.eye)
  eyeGradient.addColorStop(0.6, colors.eye + 'aa')
  eyeGradient.addColorStop(1, colors.glow + '40')
  ctx.fillStyle = eyeGradient
  ctx.fill()

  // Pupil movement
  let pupilOffsetX = 0
  let pupilOffsetY = 0

  if (state === 'listening') {
    // Eyes follow a circular pattern when listening
    pupilOffsetX = Math.cos(t * 2) * 5 * side
    pupilOffsetY = Math.sin(t * 2) * 3
  } else if (state === 'thinking') {
    // Eyes dart around when thinking
    pupilOffsetX = Math.sin(t * 5) * 8
    pupilOffsetY = Math.cos(t * 3) * 4
  } else if (state === 'speaking') {
    // Slight movement with audio
    pupilOffsetY = audioLevel * 3
  }

  // Pupil
  if (state !== 'dormant') {
    const pupilSize = state === 'waking' ? 3 + Math.sin(t * 8) * 2 : 6
    ctx.beginPath()
    ctx.arc(centerX + pupilOffsetX, centerY + pupilOffsetY, pupilSize, 0, Math.PI * 2)
    ctx.fillStyle = '#0a1520'
    ctx.fill()

    // Pupil highlight
    ctx.beginPath()
    ctx.arc(centerX + pupilOffsetX - 2, centerY + pupilOffsetY - 2, 2, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff80'
    ctx.fill()
  }

  // Eye border
  ctx.beginPath()
  ctx.ellipse(centerX, centerY, width / 2, height / 2, 0, 0, Math.PI * 2)
  ctx.strokeStyle = colors.primary
  ctx.lineWidth = 2
  ctx.stroke()
}
