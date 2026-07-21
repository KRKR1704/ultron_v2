'use client'

import { useState, useEffect } from 'react'
import { MapPin, Cloud, Sun, CloudRain, Snowflake, Wind, Thermometer, Droplets } from 'lucide-react'
import { HudPanel } from '../hud-panel'
import { cn } from '@/lib/utils'

interface WeatherData {
  temp: number
  condition: 'sunny' | 'cloudy' | 'rainy' | 'snowy' | 'windy'
  humidity: number
  windSpeed: number
  location: string
}

const weatherIcons = {
  sunny: Sun,
  cloudy: Cloud,
  rainy: CloudRain,
  snowy: Snowflake,
  windy: Wind
}

export function LocationWeatherWidget() {
  const [time, setTime] = useState<Date | null>(null)
  const [location, setLocation] = useState<{ city: string; country: string } | null>(null)
  const [weather, setWeather] = useState<WeatherData | null>(null)
  const [loading, setLoading] = useState(true)
  const [mounted, setMounted] = useState(false)

  // Initialize time on client only to avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
    setTime(new Date())
    const timer = setInterval(() => {
      setTime(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Get location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            // For demo, we'll use a mock location
            // In production, you'd reverse geocode the coordinates
            setLocation({ city: 'New York', country: 'USA' })
            
            // Mock weather data - in production, call a weather API
            setWeather({
              temp: 22,
              condition: 'sunny',
              humidity: 65,
              windSpeed: 12,
              location: 'New York'
            })
          } catch (error) {
            console.error('Error getting location:', error)
          } finally {
            setLoading(false)
          }
        },
        () => {
          // Default location if geolocation denied
          setLocation({ city: 'Unknown', country: '' })
          setWeather({
            temp: 20,
            condition: 'cloudy',
            humidity: 50,
            windSpeed: 8,
            location: 'Unknown'
          })
          setLoading(false)
        }
      )
    } else {
      setLoading(false)
    }
  }, [])

  const WeatherIcon = weather ? weatherIcons[weather.condition] : Cloud

  const formattedTime = time?.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }) || '--:--:--'

  const formattedDate = time?.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }) || 'Loading...'
  
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

  return (
    <HudPanel className="p-4" title="Location & Weather">
      <div className="space-y-4">
        {/* Time Display */}
        <div className="text-center">
          <div className="text-3xl font-mono font-bold text-cyan-400 tracking-wider">
            {formattedTime}
          </div>
          <div className="text-xs font-mono text-slate-400 mt-1">
            {formattedDate}
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-cyan-500/20" />

        {/* Location */}
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-cyan-400" />
          <div className="flex-1">
            <div className="text-xs font-mono text-slate-400 uppercase">Location</div>
            <div className="text-sm text-cyan-300 font-mono">
              {loading ? 'Detecting...' : `${location?.city}, ${location?.country}`}
            </div>
          </div>
        </div>

        {/* Weather */}
        {weather && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "w-12 h-12 rounded-lg flex items-center justify-center",
                  "bg-gradient-to-br from-cyan-500/20 to-blue-500/20",
                  "border border-cyan-500/30"
                )}>
                  <WeatherIcon className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <div className="text-2xl font-mono font-bold text-cyan-300">
                    {weather.temp}°C
                  </div>
                  <div className="text-xs font-mono text-slate-400 capitalize">
                    {weather.condition}
                  </div>
                </div>
              </div>
            </div>

            {/* Weather Details */}
            <div className="grid grid-cols-2 gap-2">
              <div className="flex items-center gap-2 text-xs font-mono">
                <Droplets className="w-3 h-3 text-cyan-500" />
                <span className="text-slate-400">Humidity:</span>
                <span className="text-cyan-300">{weather.humidity}%</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <Wind className="w-3 h-3 text-cyan-500" />
                <span className="text-slate-400">Wind:</span>
                <span className="text-cyan-300">{weather.windSpeed} km/h</span>
              </div>
            </div>
          </>
        )}
      </div>
    </HudPanel>
  )
}
