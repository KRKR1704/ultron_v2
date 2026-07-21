'use client'

import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface VoiceWaveformProps {
  isActive: boolean
  audioLevel?: number
  mode?: 'listening' | 'speaking' | 'idle'
  className?: string
}

export function VoiceWaveform({ 
  isActive, 
  audioLevel = 0, 
  mode = 'idle',
  className 
}: VoiceWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number | null>(null)
  const phaseRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height
    const centerY = height / 2

    const animate = () => {
      ctx.clearRect(0, 0, width, height)

      // Color based on mode
      const primaryColor = mode === 'listening' 
        ? 'rgba(0, 255, 255, 0.9)' 
        : mode === 'speaking' 
          ? 'rgba(255, 100, 100, 0.9)' 
          : 'rgba(0, 255, 255, 0.4)'

      const glowColor = mode === 'listening'
        ? 'rgba(0, 255, 255, 0.3)'
        : mode === 'speaking'
          ? 'rgba(255, 100, 100, 0.3)'
          : 'rgba(0, 255, 255, 0.1)'

      // Draw glow effect
      ctx.shadowBlur = isActive ? 20 : 10
      ctx.shadowColor = glowColor

      // Draw waveform
      ctx.beginPath()
      ctx.strokeStyle = primaryColor
      ctx.lineWidth = 2

      const amplitude = isActive ? (audioLevel * 40 + 10) : 5
      const frequency = isActive ? 0.03 : 0.02
      const speed = isActive ? 0.08 : 0.02

      for (let x = 0; x < width; x++) {
        const y = centerY + 
          Math.sin(x * frequency + phaseRef.current) * amplitude * 
          Math.sin((x / width) * Math.PI) +
          Math.sin(x * frequency * 2 + phaseRef.current * 1.5) * (amplitude * 0.3)

        if (x === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      }

      ctx.stroke()

      // Draw center line pulse
      ctx.beginPath()
      ctx.strokeStyle = `rgba(0, 255, 255, ${isActive ? 0.3 : 0.1})`
      ctx.lineWidth = 1
      ctx.moveTo(0, centerY)
      ctx.lineTo(width, centerY)
      ctx.stroke()

      // Draw edge particles when active
      if (isActive && audioLevel > 0.3) {
        const particleCount = Math.floor(audioLevel * 10)
        for (let i = 0; i < particleCount; i++) {
          const px = Math.random() * width
          const py = centerY + (Math.random() - 0.5) * amplitude * 2
          ctx.beginPath()
          ctx.fillStyle = `rgba(0, 255, 255, ${Math.random() * 0.5})`
          ctx.arc(px, py, Math.random() * 2, 0, Math.PI * 2)
          ctx.fill()
        }
      }

      phaseRef.current += speed
      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [isActive, audioLevel, mode])

  return (
    <canvas
      ref={canvasRef}
      className={cn(
        'w-full h-16 rounded-lg',
        className
      )}
      style={{ background: 'transparent' }}
    />
  )
}
