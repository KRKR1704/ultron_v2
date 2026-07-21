'use client'

import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface UltronCoreProps {
  status: 'idle' | 'listening' | 'thinking' | 'speaking'
  audioLevel?: number
  className?: string
}

export function UltronCore({ status, audioLevel = 0, className }: UltronCoreProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number | null>(null)
  const timeRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const size = 200
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const centerX = size / 2
    const centerY = size / 2

    const animate = () => {
      ctx.clearRect(0, 0, size, size)

      // Status-based colors
      const colors = {
        idle: { primary: '#00d4ff', secondary: '#0066ff', glow: 'rgba(0, 212, 255, 0.3)' },
        listening: { primary: '#00ff88', secondary: '#00d4ff', glow: 'rgba(0, 255, 136, 0.4)' },
        thinking: { primary: '#ff9500', secondary: '#ff5500', glow: 'rgba(255, 149, 0, 0.4)' },
        speaking: { primary: '#ff4444', secondary: '#ff0066', glow: 'rgba(255, 68, 68, 0.4)' }
      }

      const color = colors[status]
      const intensity = status === 'idle' ? 0.5 : 0.8 + audioLevel * 0.2

      // Outer glow
      const glowGradient = ctx.createRadialGradient(
        centerX, centerY, 30,
        centerX, centerY, 90
      )
      glowGradient.addColorStop(0, color.glow)
      glowGradient.addColorStop(1, 'transparent')
      ctx.fillStyle = glowGradient
      ctx.fillRect(0, 0, size, size)

      // Rotating outer ring
      const ringCount = 3
      for (let ring = 0; ring < ringCount; ring++) {
        const radius = 60 + ring * 12
        const segments = 60
        const rotation = timeRef.current * (0.5 + ring * 0.2) * (ring % 2 === 0 ? 1 : -1)

        ctx.beginPath()
        for (let i = 0; i < segments; i++) {
          const angle = (i / segments) * Math.PI * 2 + rotation
          const segmentIntensity = Math.sin(i * 0.5 + timeRef.current * 2) * 0.5 + 0.5
          const r = radius + Math.sin(angle * 3 + timeRef.current) * (2 + audioLevel * 5)

          const x = centerX + Math.cos(angle) * r
          const y = centerY + Math.sin(angle) * r

          if (i === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }

          // Draw glow dots
          if (segmentIntensity > 0.7) {
            ctx.save()
            ctx.fillStyle = `rgba(0, 212, 255, ${segmentIntensity * intensity})`
            ctx.shadowBlur = 10
            ctx.shadowColor = color.primary
            ctx.beginPath()
            ctx.arc(x, y, 2, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()
          }
        }
        ctx.closePath()
        ctx.strokeStyle = `rgba(0, 212, 255, ${0.3 * intensity})`
        ctx.lineWidth = 1
        ctx.stroke()
      }

      // Inner core gradient
      const coreGradient = ctx.createRadialGradient(
        centerX - 10, centerY - 10, 0,
        centerX, centerY, 40 + audioLevel * 10
      )
      coreGradient.addColorStop(0, '#ffffff')
      coreGradient.addColorStop(0.3, color.primary)
      coreGradient.addColorStop(0.7, color.secondary)
      coreGradient.addColorStop(1, 'transparent')

      ctx.beginPath()
      ctx.arc(centerX, centerY, 35 + audioLevel * 8, 0, Math.PI * 2)
      ctx.fillStyle = coreGradient
      ctx.shadowBlur = 30 * intensity
      ctx.shadowColor = color.primary
      ctx.fill()

      // Pulsing inner highlight
      const pulseSize = Math.sin(timeRef.current * 3) * 5 + 15
      const innerGlow = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, pulseSize
      )
      innerGlow.addColorStop(0, 'rgba(255, 255, 255, 0.9)')
      innerGlow.addColorStop(0.5, 'rgba(255, 255, 255, 0.3)')
      innerGlow.addColorStop(1, 'transparent')

      ctx.beginPath()
      ctx.arc(centerX, centerY, pulseSize, 0, Math.PI * 2)
      ctx.fillStyle = innerGlow
      ctx.fill()

      // Data streams when thinking
      if (status === 'thinking') {
        const streamCount = 8
        for (let i = 0; i < streamCount; i++) {
          const angle = (i / streamCount) * Math.PI * 2 + timeRef.current
          const startR = 45
          const endR = 80
          const progress = (timeRef.current * 2 + i) % 1

          ctx.beginPath()
          ctx.moveTo(
            centerX + Math.cos(angle) * (startR + progress * (endR - startR)),
            centerY + Math.sin(angle) * (startR + progress * (endR - startR))
          )
          ctx.lineTo(
            centerX + Math.cos(angle) * (startR + progress * (endR - startR) + 10),
            centerY + Math.sin(angle) * (startR + progress * (endR - startR) + 10)
          )
          ctx.strokeStyle = `rgba(255, 149, 0, ${1 - progress})`
          ctx.lineWidth = 2
          ctx.stroke()
        }
      }

      timeRef.current += 0.02
      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [status, audioLevel])

  return (
    <div className={cn('relative', className)}>
      <canvas
        ref={canvasRef}
        className="w-[200px] h-[200px]"
        style={{ background: 'transparent' }}
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className={cn(
          'text-xs font-mono uppercase tracking-[0.3em] transition-colors duration-300',
          status === 'idle' && 'text-cyan-400/60',
          status === 'listening' && 'text-green-400',
          status === 'thinking' && 'text-orange-400',
          status === 'speaking' && 'text-red-400'
        )}>
          {status}
        </span>
      </div>
    </div>
  )
}
