'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

interface UseVoiceOptions {
  onTranscript?: (transcript: string) => void
  onSpeakEnd?: () => void
  onWakeWord?: () => void
  continuous?: boolean
  wakeWord?: string
}

interface UseVoiceReturn {
  isListening: boolean
  isSpeaking: boolean
  isWakeListening: boolean
  transcript: string
  startListening: () => void
  stopListening: () => void
  startWakeWordListening: () => void
  stopWakeWordListening: () => void
  speak: (text: string) => void
  stopSpeaking: () => void
  isSupported: boolean
  voices: SpeechSynthesisVoice[]
  selectedVoice: SpeechSynthesisVoice | null
  setSelectedVoice: (voice: SpeechSynthesisVoice | null) => void
  audioLevel: number
}

export function useVoice(options: UseVoiceOptions = {}): UseVoiceReturn {
  const { continuous = false, wakeWord = 'ultron' } = options
  
  // Store callbacks in refs to avoid re-running effect
  const onTranscriptRef = useRef(options.onTranscript)
  const onSpeakEndRef = useRef(options.onSpeakEnd)
  const onWakeWordRef = useRef(options.onWakeWord)
  
  // Keep refs updated
  useEffect(() => {
    onTranscriptRef.current = options.onTranscript
    onSpeakEndRef.current = options.onSpeakEnd
    onWakeWordRef.current = options.onWakeWord
  })
  
  const [isListening, setIsListening] = useState(false)
  const [isWakeListening, setIsWakeListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)
  const [isSupported, setIsSupported] = useState(false)
  
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const wakeRecognitionRef = useRef<SpeechRecognition | null>(null)
  const synthRef = useRef<SpeechSynthesis | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const initializedRef = useRef(false)

  // Initialize speech recognition and synthesis - only once
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (initializedRef.current) return
    initializedRef.current = true

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    
    if (SpeechRecognition) {
      setIsSupported(true)
      const recognition = new SpeechRecognition()
      recognition.continuous = continuous
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = ''
        let interimTranscript = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]
          if (result.isFinal) {
            finalTranscript += result[0].transcript
          } else {
            interimTranscript += result[0].transcript
          }
        }

        const currentTranscript = finalTranscript || interimTranscript
        setTranscript(currentTranscript)

        if (finalTranscript && onTranscriptRef.current) {
          onTranscriptRef.current(finalTranscript)
        }
      }

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
      }

      recognition.onend = () => {
        setIsListening(false)
        setAudioLevel(0)
      }

      recognitionRef.current = recognition
    }

    // Wake word recognition (continuous, background)
    if (SpeechRecognition) {
      const wakeRec = new SpeechRecognition()
      wakeRec.continuous = true
      wakeRec.interimResults = true
      wakeRec.lang = 'en-US'

      wakeRec.onresult = (event: SpeechRecognitionEvent) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const text = event.results[i][0].transcript.toLowerCase().trim()
          if (text.includes(wakeWord.toLowerCase())) {
            onWakeWordRef.current?.()
          }
        }
      }

      wakeRec.onend = () => {
        // Auto-restart if wake listening is active
        if (wakeRecognitionRef.current) {
          try { wakeRec.start() } catch (_) {}
        }
      }

      wakeRecognitionRef.current = wakeRec
    }

    synthRef.current = window.speechSynthesis

    // Load voices
    const loadVoices = () => {
      const availableVoices = window.speechSynthesis.getVoices()
      setVoices(availableVoices)
      
      // Select a good default voice (prefer English, female voice for assistant)
      const preferredVoice = availableVoices.find(
        voice => voice.lang.startsWith('en') && voice.name.includes('Female')
      ) || availableVoices.find(
        voice => voice.lang.startsWith('en')
      ) || availableVoices[0]
      
      if (preferredVoice) {
        setSelectedVoice(prev => prev || preferredVoice)
      }
    }

    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [continuous, wakeWord])

  // Audio level monitoring
  const startAudioMonitoring = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioContextRef.current = new AudioContext()
      analyserRef.current = audioContextRef.current.createAnalyser()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      source.connect(analyserRef.current)
      analyserRef.current.fftSize = 256

      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)

      const updateLevel = () => {
        if (!analyserRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length
        setAudioLevel(average / 255)
        animationFrameRef.current = requestAnimationFrame(updateLevel)
      }

      updateLevel()
    } catch (error) {
      console.error('Error accessing microphone:', error)
    }
  }, [])

  const stopAudioMonitoring = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    setAudioLevel(0)
  }, [])

  const startWakeWordListening = useCallback(() => {
    if (!wakeRecognitionRef.current || isWakeListening) return
    try {
      wakeRecognitionRef.current.start()
      setIsWakeListening(true)
    } catch (_) {}
  }, [isWakeListening])

  const stopWakeWordListening = useCallback(() => {
    if (!wakeRecognitionRef.current) return
    const ref = wakeRecognitionRef.current
    wakeRecognitionRef.current = null
    try { ref.stop() } catch (_) {}
    setIsWakeListening(false)
  }, [])

  const startListening = useCallback(() => {
    if (!recognitionRef.current || isListening) return
    
    setTranscript('')
    recognitionRef.current.start()
    setIsListening(true)
    startAudioMonitoring()
  }, [isListening, startAudioMonitoring])

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) return
    
    recognitionRef.current.stop()
    setIsListening(false)
    stopAudioMonitoring()
  }, [stopAudioMonitoring])

  const speak = useCallback((text: string) => {
    if (!synthRef.current) return
    
    // Cancel any ongoing speech
    synthRef.current.cancel()
    
    const utterance = new SpeechSynthesisUtterance(text)
    
    if (selectedVoice) {
      utterance.voice = selectedVoice
    }
    
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.volume = 1.0

    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => {
      setIsSpeaking(false)
      onSpeakEndRef.current?.()
    }
    utterance.onerror = () => setIsSpeaking(false)

    synthRef.current.speak(utterance)
  }, [selectedVoice])

  const stopSpeaking = useCallback(() => {
    if (!synthRef.current) return
    synthRef.current.cancel()
    setIsSpeaking(false)
  }, [])

  return {
    isListening,
    isSpeaking,
    isWakeListening,
    transcript,
    startListening,
    stopListening,
    startWakeWordListening,
    stopWakeWordListening,
    speak,
    stopSpeaking,
    isSupported,
    voices,
    selectedVoice,
    setSelectedVoice,
    audioLevel
  }
}

// Type declarations for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition
    webkitSpeechRecognition: typeof SpeechRecognition
  }
}
