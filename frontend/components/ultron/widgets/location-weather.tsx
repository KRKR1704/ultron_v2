'use client'

import { useState, useEffect } from 'react'
import { MapPin, Cloud, Sun, CloudRain, Snowflake, Wind, Loader2, MapPinOff } from 'lucide-react'
import { HudPanel } from '../hud-panel'
import { getWeather } from '@/lib/api'
import type { WeatherResponse } from '@/types/ultron'
import { cn } from '@/lib/utils'

const weatherIcons = {
  sunny: Sun,
  cloudy: Cloud,
  rainy: CloudRain,
  snowy: Snowflake,
  windy: Wind,
} as const

type LocationState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'error'; message: string }
  | { status: 'ready'; weather: WeatherResponse }

export function LocationWeatherWidget() {
  const [time, setTime] = useState<Date | null>(null)
  const [mounted, setMounted] = useState(false)
  const [state, setState] = useState<LocationState>({ status: 'loading' })

  // Initialize time on client only to avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
    setTime(new Date())
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Real geolocation → real backend weather. No mock coordinates, no mock
  // weather object — a denied/unavailable permission is shown as its own
  // state rather than silently substituted with fake data.
  useEffect(() => {
    if (!navigator.geolocation) {
      setState({ status: 'error', message: 'Geolocation is not supported in this browser.' })
      return
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const weather = await getWeather(position.coords.latitude, position.coords.longitude)
          setState({ status: 'ready', weather })
        } catch (err) {
          setState({
            status: 'error',
            message: err instanceof Error ? err.message : 'Could not fetch weather.',
          })
        }
      },
      () => setState({ status: 'denied' }),
    )
  }, [])

  const formattedTime =
    time?.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) ??
    '--:--:--'

  const formattedDate =
    time?.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) ??
    'Loading...'

  if (!mounted) {
    return (
      <HudPanel className="p-4" title="Location & Weather">
        <div className="space-y-4 animate-pulse">
          <div className="text-center">
            <div className="text-3xl font-mono font-bold text-cyan-400/50 tracking-wider">--:--:--</div>
            <div className="text-xs font-mono text-slate-500 mt-1">Loading...</div>
          </div>
        </div>
      </HudPanel>
    )
  }

  const WeatherIcon = state.status === 'ready' ? weatherIcons[state.weather.condition] : Cloud

  return (
    <HudPanel className="p-4" title="Location & Weather">
      <div className="space-y-4">
        {/* Time Display */}
        <div className="text-center">
          <div className="text-3xl font-mono font-bold text-cyan-400 tracking-wider">{formattedTime}</div>
          <div className="text-xs font-mono text-slate-400 mt-1">{formattedDate}</div>
        </div>

        <div className="border-t border-cyan-500/20" />

        {state.status === 'loading' && (
          <div className="flex items-center justify-center gap-2 text-xs font-mono text-slate-500 py-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            Getting your location…
          </div>
        )}

        {state.status === 'denied' && (
          <div className="flex flex-col items-center gap-1 py-3 text-center">
            <MapPinOff className="w-5 h-5 text-slate-600" />
            <p className="text-xs font-mono text-slate-500">Enable location for weather</p>
            <p className="text-[10px] font-mono text-slate-600">
              Location permission was denied — allow it in your browser/OS settings to see local weather.
            </p>
          </div>
        )}

        {state.status === 'error' && (
          <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-2 text-center">
            <p className="text-[10px] text-red-400 font-mono">{state.message}</p>
          </div>
        )}

        {state.status === 'ready' && (
          <>
            {/* Location */}
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-cyan-400" />
              <div className="flex-1">
                <div className="text-xs font-mono text-slate-400 uppercase">Location</div>
                <div className="text-sm text-cyan-300 font-mono">{state.weather.location_name}</div>
              </div>
            </div>

            {/* Weather */}
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'w-12 h-12 rounded-lg flex items-center justify-center',
                  'bg-gradient-to-br from-cyan-500/20 to-blue-500/20',
                  'border border-cyan-500/30',
                )}
              >
                <WeatherIcon className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <div className="text-2xl font-mono font-bold text-cyan-300">
                  {Math.round(state.weather.temperature)}°C
                </div>
                <div className="text-xs font-mono text-slate-400 capitalize">{state.weather.condition}</div>
              </div>
            </div>
          </>
        )}
      </div>
    </HudPanel>
  )
}
