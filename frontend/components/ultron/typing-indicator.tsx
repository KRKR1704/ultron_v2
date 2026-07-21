'use client'

import { cn } from '@/lib/utils'

interface TypingIndicatorProps {
  className?: string
  message?: string
}

export function TypingIndicator({ className, message = 'ULTRON is thinking' }: TypingIndicatorProps) {
  return (
    <div className={cn(
      'flex items-center gap-3 p-4 rounded-lg bg-cyan-950/20 border border-cyan-500/20',
      className
    )}>
      {/* Animated dots */}
      <div className="flex items-center gap-1">
        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }} />
        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '150ms' }} />
        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      
      {/* Message */}
      <span className="text-sm font-mono text-cyan-400/80">{message}...</span>
    </div>
  )
}

interface ProcessingStepsProps {
  steps: string[]
  currentStep: number
  className?: string
}

export function ProcessingSteps({ steps, currentStep, className }: ProcessingStepsProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {steps.map((step, index) => {
        const isComplete = index < currentStep
        const isCurrent = index === currentStep
        const isPending = index > currentStep

        return (
          <div 
            key={index}
            className={cn(
              'flex items-center gap-3 text-sm font-mono transition-all duration-300',
              isComplete && 'text-cyan-400',
              isCurrent && 'text-cyan-300',
              isPending && 'text-slate-500'
            )}
          >
            {/* Status indicator */}
            <div className={cn(
              'w-4 h-4 rounded-full border-2 flex items-center justify-center',
              isComplete && 'border-cyan-400 bg-cyan-400',
              isCurrent && 'border-cyan-400 animate-pulse',
              isPending && 'border-slate-600'
            )}>
              {isComplete && (
                <svg className="w-2 h-2 text-slate-900" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </div>
            
            {/* Step text */}
            <span>{step}</span>
          </div>
        )
      })}
    </div>
  )
}
