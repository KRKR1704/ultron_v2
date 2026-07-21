'use client'

import { useEffect, useState } from 'react'
import { HudPanel, HudStatus } from './hud-panel'
import { Activity, Cpu, HardDrive, Wifi, Clock, Calendar } from 'lucide-react'

interface StatusSidebarProps {
  className?: string
}

export function StatusSidebar({ className }: StatusSidebarProps) {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [systemStats, setSystemStats] = useState({
    cpu: Math.floor(Math.random() * 30) + 10,
    memory: Math.floor(Math.random() * 40) + 30,
    network: 'Connected'
  })

  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    const statsInterval = setInterval(() => {
      setSystemStats({
        cpu: Math.floor(Math.random() * 30) + 10,
        memory: Math.floor(Math.random() * 40) + 30,
        network: 'Connected'
      })
    }, 3000)

    return () => {
      clearInterval(timeInterval)
      clearInterval(statsInterval)
    }
  }, [])

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  }

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className={className}>
      <HudPanel className="p-4 space-y-4" title="System Status">
        {/* Time & Date */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-cyan-400">
            <Clock className="w-4 h-4" />
            <span className="font-mono text-lg">{formatTime(currentTime)}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <Calendar className="w-4 h-4" />
            <span className="font-mono text-sm">{formatDate(currentTime)}</span>
          </div>
        </div>

        <div className="border-t border-cyan-500/20 pt-4 space-y-3">
          {/* CPU */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="flex items-center gap-2 text-slate-400">
                <Cpu className="w-3 h-3" />
                CPU
              </span>
              <span className="text-cyan-400">{systemStats.cpu}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-500"
                style={{ width: `${systemStats.cpu}%` }}
              />
            </div>
          </div>

          {/* Memory */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="flex items-center gap-2 text-slate-400">
                <HardDrive className="w-3 h-3" />
                Memory
              </span>
              <span className="text-cyan-400">{systemStats.memory}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-500"
                style={{ width: `${systemStats.memory}%` }}
              />
            </div>
          </div>

          {/* Network */}
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="flex items-center gap-2 text-slate-400">
              <Wifi className="w-3 h-3" />
              Network
            </span>
            <HudStatus label="" value={systemStats.network} status="online" />
          </div>

          {/* AI Status */}
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="flex items-center gap-2 text-slate-400">
              <Activity className="w-3 h-3" />
              AI Core
            </span>
            <HudStatus label="" value="Active" status="online" />
          </div>
        </div>
      </HudPanel>
    </div>
  )
}
