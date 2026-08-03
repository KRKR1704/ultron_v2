'use client'

import { useState, useEffect, useCallback } from 'react'
import { ChevronLeft, ChevronRight, Loader2, Plus, RefreshCw, CalendarOff } from 'lucide-react'
import { HudPanel, HudButton } from '../hud-panel'
import { calendarAction } from '@/lib/api'
import { cn } from '@/lib/utils'

const DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

// Backend returns a friendly plain-English message (not a real event list)
// whenever Google Calendar OAuth2 credentials aren't set up — recognize it
// so the UI can show a clean empty state instead of "displaying" that string
// as if it were calendar content.
function isNotConfigured(result: string): boolean {
  return /not configured/i.test(result)
}

interface CalendarWidgetProps {
  sessionId: string
}

export function CalendarWidget({ sessionId }: CalendarWidgetProps) {
  const [currentDate, setCurrentDate] = useState(new Date())
  const today = new Date()

  const [events, setEvents] = useState<string[]>([])
  const [notConfigured, setNotConfigured] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showAddEvent, setShowAddEvent] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newWhen, setNewWhen] = useState('')
  const [creating, setCreating] = useState(false)

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  const firstDayOfMonth = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const daysInPrevMonth = new Date(year, month, 0).getDate()

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1))
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1))
  const goToToday = () => setCurrentDate(new Date())

  // ── Real backend event list ─────────────────────────────────────────────
  const fetchEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await calendarAction('list', '', sessionId)
      if (isNotConfigured(res.result)) {
        setNotConfigured(true)
        setEvents([])
      } else {
        setNotConfigured(false)
        // Backend returns a human-readable multi-line block — one event per
        // line (see tools/calendar_tasks.py list_events()). Drop the leading
        // "Your next N events:" summary line and any blank lines.
        const lines = res.result
          .split('\n')
          .map((l) => l.trim())
          .filter((l) => l.startsWith('-'))
        setEvents(lines.length > 0 ? lines : [res.result])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach the calendar.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  // ── Real backend event creation ─────────────────────────────────────────
  const createEvent = useCallback(async () => {
    if (!newTitle.trim()) return
    setCreating(true)
    try {
      const details = newWhen.trim() ? `${newTitle.trim()} ${newWhen.trim()}` : newTitle.trim()
      await calendarAction('create', details, sessionId)
      setNewTitle('')
      setNewWhen('')
      setShowAddEvent(false)
      await fetchEvents()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the event.')
    } finally {
      setCreating(false)
    }
  }, [newTitle, newWhen, sessionId, fetchEvents])

  // Generate calendar grid days (pure date arithmetic — this part is real,
  // not backend data, and is only used for month navigation/"today" display)
  const days: { day: number; isCurrentMonth: boolean; isToday: boolean }[] = []
  for (let i = firstDayOfMonth - 1; i >= 0; i--) {
    days.push({ day: daysInPrevMonth - i, isCurrentMonth: false, isToday: false })
  }
  for (let i = 1; i <= daysInMonth; i++) {
    const isToday = i === today.getDate() && month === today.getMonth() && year === today.getFullYear()
    days.push({ day: i, isCurrentMonth: true, isToday })
  }
  const remainingDays = 42 - days.length
  for (let i = 1; i <= remainingDays; i++) {
    days.push({ day: i, isCurrentMonth: false, isToday: false })
  }

  return (
    <HudPanel className="p-4" title="Calendar">
      <div className="space-y-3">
        {/* Month Navigation */}
        <div className="flex items-center justify-between">
          <button onClick={prevMonth} className="p-1 hover:bg-cyan-500/20 rounded transition-colors">
            <ChevronLeft className="w-4 h-4 text-cyan-400" />
          </button>
          <button
            onClick={goToToday}
            className="text-sm font-mono font-bold text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            {MONTHS[month]} {year}
          </button>
          <button onClick={nextMonth} className="p-1 hover:bg-cyan-500/20 rounded transition-colors">
            <ChevronRight className="w-4 h-4 text-cyan-400" />
          </button>
        </div>

        {/* Day Headers */}
        <div className="grid grid-cols-7 gap-1">
          {DAYS.map((day) => (
            <div key={day} className="text-center text-xs font-mono text-slate-500 py-1">
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
                'aspect-square flex items-center justify-center text-xs font-mono rounded transition-all',
                item.isCurrentMonth ? 'text-cyan-300 hover:bg-cyan-500/20' : 'text-slate-600',
                item.isToday && [
                  'bg-cyan-500 text-slate-900 font-bold',
                  'shadow-[0_0_10px_rgba(0,212,255,0.5)]',
                  'hover:bg-cyan-400',
                ],
              )}
            >
              {item.day}
            </button>
          ))}
        </div>

        <div className="border-t border-cyan-500/20 pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              Upcoming Events
            </span>
            <button
              onClick={fetchEvents}
              disabled={loading}
              className="text-slate-500 hover:text-cyan-400 transition-colors"
              aria-label="Refresh events"
            >
              {loading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <RefreshCw className="w-3 h-3" />
              )}
            </button>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-xs font-mono text-slate-500 py-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              Loading events…
            </div>
          ) : error ? (
            <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-2">
              <p className="text-[10px] text-red-400 font-mono">{error}</p>
            </div>
          ) : notConfigured ? (
            <div className="flex flex-col items-center gap-1 py-3 text-center">
              <CalendarOff className="w-5 h-5 text-slate-600" />
              <p className="text-xs font-mono text-slate-500">Calendar not connected yet</p>
              <p className="text-[10px] font-mono text-slate-600">
                Set up Google Calendar credentials in the backend to enable this.
              </p>
            </div>
          ) : events.length === 0 ? (
            <p className="text-xs font-mono text-slate-500 text-center py-2">No upcoming events.</p>
          ) : (
            <ul className="space-y-1 max-h-32 overflow-y-auto">
              {events.map((line, i) => (
                <li key={i} className="text-xs font-mono text-cyan-200 leading-relaxed">
                  {line}
                </li>
              ))}
            </ul>
          )}

          {showAddEvent ? (
            <div className="space-y-2">
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Event title…"
                className="w-full bg-slate-900/50 border border-cyan-500/30 rounded px-2 py-1 text-cyan-100 placeholder:text-slate-500 font-mono text-xs focus:outline-none focus:border-cyan-400"
                autoFocus
              />
              <input
                type="text"
                value={newWhen}
                onChange={(e) => setNewWhen(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createEvent()}
                placeholder="When (e.g. tomorrow at 3pm)…"
                className="w-full bg-slate-900/50 border border-cyan-500/30 rounded px-2 py-1 text-cyan-100 placeholder:text-slate-500 font-mono text-xs focus:outline-none focus:border-cyan-400"
              />
              <div className="flex gap-2">
                <HudButton onClick={createEvent} disabled={creating || !newTitle.trim()} size="sm" variant="primary">
                  {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add'}
                </HudButton>
                <HudButton onClick={() => setShowAddEvent(false)} size="sm">
                  Cancel
                </HudButton>
              </div>
            </div>
          ) : (
            <HudButton
              onClick={() => setShowAddEvent(true)}
              size="sm"
              className="w-full justify-center"
              icon={<Plus className="w-3 h-3" />}
            >
              Add Event
            </HudButton>
          )}
        </div>
      </div>
    </HudPanel>
  )
}
