'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { HudPanel, HudButton } from '../hud-panel'
import { cn } from '@/lib/utils'

const DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

export function CalendarWidget() {
  const [currentDate, setCurrentDate] = useState(new Date())
  const today = new Date()

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  const firstDayOfMonth = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const daysInPrevMonth = new Date(year, month, 0).getDate()

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1))
  }

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1))
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  // Generate calendar days
  const days: { day: number; isCurrentMonth: boolean; isToday: boolean }[] = []

  // Previous month days
  for (let i = firstDayOfMonth - 1; i >= 0; i--) {
    days.push({
      day: daysInPrevMonth - i,
      isCurrentMonth: false,
      isToday: false
    })
  }

  // Current month days
  for (let i = 1; i <= daysInMonth; i++) {
    const isToday = 
      i === today.getDate() && 
      month === today.getMonth() && 
      year === today.getFullYear()
    days.push({
      day: i,
      isCurrentMonth: true,
      isToday
    })
  }

  // Next month days
  const remainingDays = 42 - days.length
  for (let i = 1; i <= remainingDays; i++) {
    days.push({
      day: i,
      isCurrentMonth: false,
      isToday: false
    })
  }

  return (
    <HudPanel className="p-4" title="Calendar">
      <div className="space-y-3">
        {/* Month Navigation */}
        <div className="flex items-center justify-between">
          <button 
            onClick={prevMonth}
            className="p-1 hover:bg-cyan-500/20 rounded transition-colors"
          >
            <ChevronLeft className="w-4 h-4 text-cyan-400" />
          </button>
          <button 
            onClick={goToToday}
            className="text-sm font-mono font-bold text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            {MONTHS[month]} {year}
          </button>
          <button 
            onClick={nextMonth}
            className="p-1 hover:bg-cyan-500/20 rounded transition-colors"
          >
            <ChevronRight className="w-4 h-4 text-cyan-400" />
          </button>
        </div>

        {/* Day Headers */}
        <div className="grid grid-cols-7 gap-1">
          {DAYS.map(day => (
            <div 
              key={day} 
              className="text-center text-xs font-mono text-slate-500 py-1"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Days */}
        <div className="grid grid-cols-7 gap-1">
          {days.map((item, index) => (
            <button
              key={index}
              className={cn(
                "aspect-square flex items-center justify-center text-xs font-mono rounded transition-all",
                item.isCurrentMonth 
                  ? "text-cyan-300 hover:bg-cyan-500/20" 
                  : "text-slate-600",
                item.isToday && [
                  "bg-cyan-500 text-slate-900 font-bold",
                  "shadow-[0_0_10px_rgba(0,212,255,0.5)]",
                  "hover:bg-cyan-400"
                ]
              )}
            >
              {item.day}
            </button>
          ))}
        </div>
      </div>
    </HudPanel>
  )
}
