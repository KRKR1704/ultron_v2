'use client'

import { useState, useEffect, useCallback } from 'react'
import { CheckCircle2, Circle, Plus, Clock, Loader2, RefreshCw, ListX } from 'lucide-react'
import { HudPanel, HudButton } from '../hud-panel'
import { taskAction } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Task {
  /** Raw backend line, used as the React key — the backend has no numeric IDs. */
  raw: string
  title: string
  completed: boolean
  due?: string
}

// Backend returns a friendly plain-English message (not a real task list)
// whenever Google Tasks OAuth2 credentials aren't set up.
function isNotConfigured(result: string): boolean {
  return /not configured/i.test(result)
}

// Parse one line of tools/calendar_tasks.py's list_tasks() output:
//   "✓ Title (due 2026-07-25)"   or   "○ Title"
function parseTaskLine(line: string): Task | null {
  const trimmed = line.trim()
  const match = trimmed.match(/^([✓○])\s+(.+?)(?:\s+\(due\s+([^)]+)\))?$/)
  if (!match) return null
  const [, glyph, title, due] = match
  return { raw: line, title, completed: glyph === '✓', due }
}

interface TasksWidgetProps {
  sessionId: string
}

export function TasksWidget({ sessionId }: TasksWidgetProps) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [notConfigured, setNotConfigured] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [completingTitle, setCompletingTitle] = useState<string | null>(null)

  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [showAddTask, setShowAddTask] = useState(false)
  const [adding, setAdding] = useState(false)

  const fetchTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await taskAction('list', '', sessionId)
      if (isNotConfigured(res.result)) {
        setNotConfigured(true)
        setTasks([])
      } else {
        setNotConfigured(false)
        const parsed = res.result
          .split('\n')
          .map(parseTaskLine)
          .filter((t): t is Task => t !== null)
        setTasks(parsed)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach the task list.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  const completeTask = useCallback(
    async (title: string) => {
      setCompletingTitle(title)
      try {
        await taskAction('complete', title, sessionId)
        await fetchTasks()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not update the task.')
      } finally {
        setCompletingTitle(null)
      }
    },
    [sessionId, fetchTasks],
  )

  const addTask = useCallback(async () => {
    if (!newTaskTitle.trim()) return
    setAdding(true)
    try {
      await taskAction('create', newTaskTitle.trim(), sessionId)
      setNewTaskTitle('')
      setShowAddTask(false)
      await fetchTasks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the task.')
    } finally {
      setAdding(false)
    }
  }, [newTaskTitle, sessionId, fetchTasks])

  const pendingCount = tasks.filter((t) => !t.completed).length
  const completedCount = tasks.filter((t) => t.completed).length

  return (
    <HudPanel className="p-4" title="Upcoming Tasks">
      <div className="space-y-3">
        {/* Task Stats + refresh */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-slate-400">{pendingCount} pending</span>
          <span className="text-cyan-400">{completedCount} completed</span>
          <button
            onClick={fetchTasks}
            disabled={loading}
            className="text-slate-500 hover:text-cyan-400 transition-colors"
            aria-label="Refresh tasks"
          >
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          </button>
        </div>

        {/* Task List */}
        {loading ? (
          <div className="flex items-center gap-2 text-xs font-mono text-slate-500 py-4 justify-center">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading tasks…
          </div>
        ) : error ? (
          <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-2">
            <p className="text-[10px] text-red-400 font-mono">{error}</p>
          </div>
        ) : notConfigured ? (
          <div className="flex flex-col items-center gap-1 py-4 text-center">
            <ListX className="w-5 h-5 text-slate-600" />
            <p className="text-xs font-mono text-slate-500">Tasks not connected yet</p>
            <p className="text-[10px] font-mono text-slate-600">
              Set up Google Tasks credentials in the backend to enable this.
            </p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-4 text-slate-500 text-xs font-mono">No tasks scheduled</div>
        ) : (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {tasks.map((task) => (
              <div
                key={task.raw}
                className={cn(
                  'flex items-start gap-2 p-2 rounded bg-slate-900/50 border transition-all duration-200',
                  task.completed ? 'border-slate-700/30 opacity-50' : 'border-cyan-500/20',
                )}
              >
                <button
                  onClick={() => !task.completed && completeTask(task.title)}
                  disabled={task.completed || completingTitle === task.title}
                  className="flex-shrink-0 mt-0.5 disabled:cursor-default"
                >
                  {completingTitle === task.title ? (
                    <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                  ) : task.completed ? (
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                  ) : (
                    <Circle className="w-4 h-4 text-slate-400 hover:text-cyan-400" />
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      'text-xs font-mono truncate',
                      task.completed ? 'text-slate-500 line-through' : 'text-cyan-300',
                    )}
                  >
                    {task.title}
                  </p>
                  {task.due && !task.completed && (
                    <div className="flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span className="text-[10px] font-mono text-slate-500">{task.due}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add Task */}
        {showAddTask ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addTask()}
              placeholder="Task description..."
              className={cn(
                'flex-1 bg-slate-900/50 border border-cyan-500/30 rounded px-2 py-1',
                'text-cyan-100 placeholder:text-slate-500 font-mono text-xs',
                'focus:outline-none focus:border-cyan-400',
              )}
              autoFocus
            />
            <HudButton onClick={addTask} disabled={adding || !newTaskTitle.trim()} size="sm" variant="primary">
              {adding ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add'}
            </HudButton>
          </div>
        ) : (
          <HudButton
            onClick={() => setShowAddTask(true)}
            size="sm"
            className="w-full justify-center"
            icon={<Plus className="w-3 h-3" />}
          >
            Add Task
          </HudButton>
        )}
      </div>
    </HudPanel>
  )
}
