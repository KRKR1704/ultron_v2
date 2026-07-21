'use client'

import { HudPanel, HudButton } from './hud-panel'
import { 
  Clock, 
  Cloud, 
  Calculator, 
  Code, 
  Search,
  Bell,
  Terminal
} from 'lucide-react'

interface QuickActionsProps {
  onAction: (prompt: string) => void
  className?: string
}

const quickActions = [
  { 
    icon: Clock, 
    label: 'Time', 
    prompt: 'What time is it?',
    description: 'Get current time'
  },
  { 
    icon: Cloud, 
    label: 'Weather', 
    prompt: 'What is the weather like in my location?',
    description: 'Check weather'
  },
  { 
    icon: Calculator, 
    label: 'Calculate', 
    prompt: 'I need help with a calculation',
    description: 'Math helper'
  },
  { 
    icon: Code, 
    label: 'Code', 
    prompt: 'I need help with some code',
    description: 'Code assistance'
  },
  { 
    icon: Search, 
    label: 'Search', 
    prompt: 'Search the web for',
    description: 'Web search'
  },
  { 
    icon: Bell, 
    label: 'Remind', 
    prompt: 'Set a reminder for',
    description: 'Set reminder'
  },
  { 
    icon: Terminal, 
    label: 'System', 
    prompt: 'Show me the system status',
    description: 'System info'
  }
]

export function QuickActions({ onAction, className }: QuickActionsProps) {
  return (
    <HudPanel className={className} title="Quick Actions">
      <div className="p-3 grid grid-cols-4 gap-2">
        {quickActions.map((action) => (
          <button
            key={action.label}
            onClick={() => onAction(action.prompt)}
            className="group flex flex-col items-center gap-1 p-2 rounded-lg border border-transparent hover:border-cyan-500/30 hover:bg-cyan-500/10 transition-all duration-200"
          >
            <action.icon className="w-5 h-5 text-cyan-400 group-hover:text-cyan-300" />
            <span className="text-[10px] font-mono text-slate-400 group-hover:text-cyan-300 uppercase">
              {action.label}
            </span>
          </button>
        ))}
      </div>
    </HudPanel>
  )
}

interface SuggestedPromptsProps {
  onPrompt: (prompt: string) => void
  personality: 'professional' | 'casual'
  className?: string
}

const suggestions = {
  professional: [
    "Provide a status report",
    "What tasks can you help me with?",
    "Search for the latest news",
    "Help me draft an email"
  ],
  casual: [
    "Hey, what can you do?",
    "Tell me something interesting",
    "What's happening in the world?",
    "Help me plan my day"
  ]
}

export function SuggestedPrompts({ onPrompt, personality, className }: SuggestedPromptsProps) {
  const prompts = suggestions[personality]

  return (
    <div className={className}>
      <p className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
        Try saying:
      </p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPrompt(prompt)}
            className="text-xs px-3 py-1.5 rounded-full border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/20 hover:border-cyan-400 transition-all duration-200 font-mono"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}
