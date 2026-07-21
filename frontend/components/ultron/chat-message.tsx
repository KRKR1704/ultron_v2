'use client'

// FIXED: Replaced UIMessage/AI-SDK type with simple {role, content} message
//        that matches the backend API response format.

import { cn } from '@/lib/utils'
import { User, Bot } from 'lucide-react'

interface SimpleMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface ChatMessageProps {
  message: SimpleMessage
  isStreaming?: boolean
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        'flex gap-3 p-4 rounded-lg transition-all duration-300',
        isUser
          ? 'bg-slate-800/40 border border-slate-700/50'
          : 'bg-cyan-950/20 border border-cyan-500/20',
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          isUser
            ? 'bg-slate-700 text-slate-300'
            : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40',
        )}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div
          className={cn(
            'text-xs font-mono uppercase tracking-wider mb-1',
            isUser ? 'text-slate-400' : 'text-cyan-400',
          )}
        >
          {isUser ? 'User' : 'ULTRON'}
        </div>

        <div
          className={cn(
            'text-sm leading-relaxed whitespace-pre-wrap',
            isUser ? 'text-slate-200' : 'text-cyan-100',
            isStreaming && 'animate-pulse',
          )}
        >
          {message.content}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-cyan-400 animate-pulse" />
          )}
        </div>

        <div className="text-[10px] text-slate-600 font-mono mt-1">
          {message.timestamp.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
          })}
        </div>
      </div>
    </div>
  )
}
