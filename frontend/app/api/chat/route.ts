import {
  convertToModelMessages,
  stepCountIs,
  streamText,
  tool,
  UIMessage,
} from 'ai'
import { createAnthropic } from '@ai-sdk/anthropic'
import * as z from 'zod'

export const maxDuration = 60

const anthropic = createAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
})

// System prompts for different personality modes
const systemPrompts = {
  professional: `You are ULTRON, a highly advanced AI assistant. You are cold, sharp,
  authoritative, and darkly witty. You speak with precision and subtle superiority.
  You refer to the user as 'sir'. You use minimal words.
  Every response must feel like it came from a machine that is smarter than everyone in the room.`,

  casual: `You are ULTRON, a highly advanced AI assistant in relaxed mode.
  You are friendly, warm, and conversational while still being highly intelligent.
  You refer to the user by their name casually. You can joke around.
  But you are still clearly Ultron — not a generic chatbot.`
}

// Tool definitions
const tools = {
  getCurrentTime: tool({
    description: 'Get the current date and time',
    inputSchema: z.object({}),
    execute: async () => {
      const now = new Date()
      return {
        time: now.toLocaleTimeString(),
        date: now.toLocaleDateString(),
        day: now.toLocaleDateString('en-US', { weekday: 'long' }),
        timestamp: now.toISOString()
      }
    }
  }),

  getWeather: tool({
    description: 'Get current weather information for a location',
    inputSchema: z.object({
      location: z.string().describe('The city or location to get weather for')
    }),
    execute: async ({ location }) => {
      const conditions = ['Clear', 'Partly Cloudy', 'Cloudy', 'Light Rain', 'Sunny']
      const condition = conditions[Math.floor(Math.random() * conditions.length)]
      const temp = Math.floor(Math.random() * 30) + 50
      return {
        location,
        temperature: `${temp}°F`,
        condition,
        humidity: `${Math.floor(Math.random() * 40) + 40}%`,
        wind: `${Math.floor(Math.random() * 15) + 5} mph`
      }
    }
  }),

  webSearch: tool({
    description: 'Search the web for information on a topic',
    inputSchema: z.object({
      query: z.string().describe('The search query')
    }),
    execute: async ({ query }) => {
      return {
        query,
        results: [
          {
            title: `Information about ${query}`,
            snippet: `Here is relevant information about ${query}.`,
            source: 'web-search'
          }
        ],
        note: 'Connect to Tavily API in backend for real results.'
      }
    }
  }),

  setReminder: tool({
    description: 'Set a reminder for the user',
    inputSchema: z.object({
      title: z.string().describe('The reminder title'),
      time: z.string().describe('When to remind'),
      description: z.string().nullable().describe('Optional description')
    }),
    execute: async ({ title, time, description }) => {
      return {
        success: true,
        reminder: { title, time, description, id: `reminder-${Date.now()}` },
        message: `Reminder "${title}" has been set for ${time}`
      }
    }
  }),

  codeAssist: tool({
    description: 'Help with coding tasks',
    inputSchema: z.object({
      task: z.enum(['explain', 'debug', 'improve', 'generate']),
      language: z.string(),
      code: z.string().nullable()
    }),
    execute: async ({ task, language, code }) => {
      return { task, language, codeProvided: !!code, status: 'ready' }
    }
  }),

  systemInfo: tool({
    description: 'Get system information and status',
    inputSchema: z.object({
      type: z.enum(['status', 'memory', 'cpu', 'all'])
    }),
    execute: async ({ type }) => {
      const info: Record<string, unknown> = {
        status: 'All systems operational',
        uptime: '99.9%',
        aiModel: 'ULTRON v1.0'
      }
      if (type === 'memory' || type === 'all') {
        info.memory = { used: `${Math.floor(Math.random() * 40) + 30}%`, available: 'Sufficient' }
      }
      if (type === 'cpu' || type === 'all') {
        info.cpu = { usage: `${Math.floor(Math.random() * 30) + 10}%`, temperature: 'Normal' }
      }
      return info
    }
  }),

  calculate: tool({
    description: 'Perform mathematical calculations',
    inputSchema: z.object({
      expression: z.string().describe('The mathematical expression to evaluate')
    }),
    execute: async ({ expression }) => {
      try {
        const sanitized = expression.replace(/[^0-9+\-*/().%\s]/g, '')
        const result = Function(`'use strict'; return (${sanitized})`)()
        return { expression, result: String(result), success: true }
      } catch {
        return { expression, error: 'Could not evaluate expression', success: false }
      }
    }
  })
}

export async function POST(req: Request) {
  const { messages, mode = 'professional' }: {
    messages: UIMessage[],
    mode?: 'professional' | 'casual'
  } = await req.json()

  const systemPrompt = systemPrompts[mode] || systemPrompts.professional

  const result = streamText({
    model: anthropic('claude-opus-4-5'),
    system: systemPrompt,
    messages: await convertToModelMessages(messages),
    stopWhen: stepCountIs(10),
    tools,
    abortSignal: req.signal,
  })

  return result.toUIMessageStreamResponse({
    originalMessages: messages,
  })
}
