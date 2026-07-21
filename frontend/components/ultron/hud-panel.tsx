'use client'

import { cn } from '@/lib/utils'

interface HudPanelProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'accent' | 'warning'
  glow?: boolean
  title?: string
}

export function HudPanel({ 
  children, 
  className, 
  variant = 'default',
  glow = false,
  title
}: HudPanelProps) {
  const variantStyles = {
    default: 'border-cyan-500/30 bg-slate-900/60',
    accent: 'border-cyan-400/50 bg-cyan-950/40',
    warning: 'border-red-500/50 bg-red-950/30'
  }

  return (
    <div 
      className={cn(
        'relative rounded-lg border backdrop-blur-md',
        variantStyles[variant],
        glow && 'shadow-lg shadow-cyan-500/20',
        className
      )}
    >
      {/* Corner decorations */}
      <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-cyan-400/60 rounded-tl-lg" />
      <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-cyan-400/60 rounded-tr-lg" />
      <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-cyan-400/60 rounded-bl-lg" />
      <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-cyan-400/60 rounded-br-lg" />
      
      {title && (
        <div className="absolute -top-3 left-4 px-2 bg-slate-950 text-cyan-400 text-xs font-mono uppercase tracking-wider">
          {title}
        </div>
      )}
      
      {children}
    </div>
  )
}

interface HudStatusProps {
  label: string
  value: string | number
  status?: 'online' | 'offline' | 'warning'
  className?: string
}

export function HudStatus({ label, value, status = 'online', className }: HudStatusProps) {
  const statusColors = {
    online: 'bg-cyan-400',
    offline: 'bg-slate-500',
    warning: 'bg-amber-400'
  }

  return (
    <div className={cn('flex items-center gap-2 text-sm font-mono', className)}>
      <div className={cn('w-2 h-2 rounded-full animate-pulse', statusColors[status])} />
      <span className="text-slate-400 uppercase text-xs">{label}:</span>
      <span className="text-cyan-300">{value}</span>
    </div>
  )
}

interface HudButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
}

export function HudButton({ 
  children, 
  className, 
  variant = 'default',
  size = 'md',
  icon,
  ...props 
}: HudButtonProps) {
  const variantStyles = {
    default: 'border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/20 hover:border-cyan-400',
    primary: 'border-cyan-400 text-cyan-300 bg-cyan-500/20 hover:bg-cyan-500/40',
    danger: 'border-red-500/50 text-red-400 hover:bg-red-500/20 hover:border-red-400'
  }

  const sizeStyles = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base'
  }

  return (
    <button
      className={cn(
        'relative font-mono uppercase tracking-wider border rounded transition-all duration-200',
        'flex items-center gap-2',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  )
}
