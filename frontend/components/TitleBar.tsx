'use client'

import { useEffect, useState } from 'react'
import { Minus, Square, X, Maximize2 } from 'lucide-react'
import { cn } from '@/lib/utils'

// Extend window type for Electron API — only present inside Electron
declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void
      maximize: () => void
      close: () => void
      getWindowState: () => Promise<{ isMaximized: boolean }>
      onWindowStateChange: (cb: (_e: unknown, state: { isMaximized: boolean }) => void) => void
    }
  }
}

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false)
  const [isElectron, setIsElectron] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined' && window.electronAPI) {
      setIsElectron(true)

      // Fetch initial window state
      window.electronAPI.getWindowState().then((state) => {
        setIsMaximized(state.isMaximized)
      })

      // Listen for future state changes
      window.electronAPI.onWindowStateChange((_e, state) => {
        setIsMaximized(state.isMaximized)
      })
    }
  }, [])

  // Don't render in browser — only in Electron
  if (!isElectron) return null

  return (
    <div
      className={cn(
        'flex-shrink-0 flex items-center justify-between',
        'w-full h-8 px-4',
        'bg-[#050505] border-b border-red-900/20',
        'select-none z-[9999]',
      )}
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* Left — Branding */}
      <div className="flex items-center gap-2">
        {/* Red diamond accent */}
        <div className="w-2 h-2 bg-red-600 rotate-45 opacity-80" />
        <span className="text-[11px] font-mono font-bold tracking-[0.3em] text-red-500/80 uppercase">
          Ultron
        </span>
        <span className="text-[9px] font-mono text-slate-600 tracking-widest uppercase ml-1">
          v1.0
        </span>
      </div>

      {/* Right — Window controls */}
      <div
        className="flex items-center gap-1"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        {/* Minimize */}
        <button
          onClick={() => window.electronAPI?.minimize()}
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center',
            'text-slate-500 hover:text-slate-200',
            'hover:bg-slate-700/60 transition-all duration-150',
          )}
          aria-label="Minimize"
        >
          <Minus className="w-3 h-3" />
        </button>

        {/* Maximize / Restore */}
        <button
          onClick={() => window.electronAPI?.maximize()}
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center',
            'text-slate-500 hover:text-slate-200',
            'hover:bg-slate-700/60 transition-all duration-150',
          )}
          aria-label={isMaximized ? 'Restore' : 'Maximize'}
        >
          {isMaximized ? (
            <Square className="w-2.5 h-2.5" />
          ) : (
            <Maximize2 className="w-2.5 h-2.5" />
          )}
        </button>

        {/* Close */}
        <button
          onClick={() => window.electronAPI?.close()}
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center',
            'text-slate-500 hover:text-white',
            'hover:bg-red-600 transition-all duration-150',
          )}
          aria-label="Close"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
