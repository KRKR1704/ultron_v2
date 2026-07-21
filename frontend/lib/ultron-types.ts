export type PersonalityMode = 'professional' | 'casual'

export interface UltronMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  toolCalls?: ToolCallResult[]
}

export interface ToolCallResult {
  toolName: string
  result: unknown
  status: 'pending' | 'success' | 'error'
}

export interface VoiceSettings {
  enabled: boolean
  autoSpeak: boolean
  voice: SpeechSynthesisVoice | null
  rate: number
  pitch: number
}

export interface UltronState {
  isListening: boolean
  isSpeaking: boolean
  isThinking: boolean
  personalityMode: PersonalityMode
  systemStatus: 'online' | 'processing' | 'error'
}
