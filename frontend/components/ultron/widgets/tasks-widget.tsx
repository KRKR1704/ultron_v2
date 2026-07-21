'use client'

import { useState } from 'react'
import { CheckCircle2, Circle, Plus, Clock, AlertCircle, Trash2 } from 'lucide-react'
import { HudPanel, HudButton } from '../hud-panel'
import { cn } from '@/lib/utils'

interface Task {
  id: string
  title: string
  completed: boolean
  priority: 'low' | 'medium' | 'high'
  dueTime?: string
}

const defaultTasks: Task[] = [
  { id: '1', title: 'Review system diagnostics', completed: false, priority: 'high', dueTime: '14:00' },
  { id: '2', title: 'Update security protocols', completed: false, priority: 'medium', dueTime: '16:30' },
  { id: '3', title: 'Sync data with cloud', completed: true, priority: 'low' },
  { id: '4', title: 'Run performance analysis', completed: false, priority: 'medium', dueTime: '18:00' },
]

const priorityColors = {
  low: 'text-slate-400 border-slate-400/30',
  medium: 'text-yellow-400 border-yellow-400/30',
  high: 'text-red-400 border-red-400/30'
}

const priorityGlow = {
  low: '',
  medium: 'shadow-[0_0_5px_rgba(250,204,21,0.2)]',
  high: 'shadow-[0_0_5px_rgba(248,113,113,0.3)]'
}

export function TasksWidget() {
  const [tasks, setTasks] = useState<Task[]>(defaultTasks)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [showAddTask, setShowAddTask] = useState(false)

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(task => 
      task.id === id ? { ...task, completed: !task.completed } : task
    ))
  }

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(task => task.id !== id))
  }

  const addTask = () => {
    if (!newTaskTitle.trim()) return
    
    const newTask: Task = {
      id: Date.now().toString(),
      title: newTaskTitle,
      completed: false,
      priority: 'medium'
    }
    
    setTasks(prev => [...prev, newTask])
    setNewTaskTitle('')
    setShowAddTask(false)
  }

  const pendingTasks = tasks.filter(t => !t.completed)
  const completedTasks = tasks.filter(t => t.completed)

  return (
    <HudPanel className="p-4" title="Upcoming Tasks">
      <div className="space-y-3">
        {/* Task Stats */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-slate-400">
            {pendingTasks.length} pending
          </span>
          <span className="text-cyan-400">
            {completedTasks.length} completed
          </span>
        </div>

        {/* Task List */}
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {tasks.length === 0 ? (
            <div className="text-center py-4 text-slate-500 text-xs font-mono">
              No tasks scheduled
            </div>
          ) : (
            tasks.map(task => (
              <div
                key={task.id}
                className={cn(
                  "flex items-start gap-2 p-2 rounded",
                  "bg-slate-900/50 border",
                  task.completed 
                    ? "border-slate-700/30 opacity-50" 
                    : priorityColors[task.priority],
                  !task.completed && priorityGlow[task.priority],
                  "group transition-all duration-200"
                )}
              >
                <button
                  onClick={() => toggleTask(task.id)}
                  className="flex-shrink-0 mt-0.5"
                >
                  {task.completed ? (
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                  ) : (
                    <Circle className={cn("w-4 h-4", priorityColors[task.priority].split(' ')[0])} />
                  )}
                </button>
                
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-xs font-mono truncate",
                    task.completed ? "text-slate-500 line-through" : "text-cyan-300"
                  )}>
                    {task.title}
                  </p>
                  {task.dueTime && !task.completed && (
                    <div className="flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span className="text-[10px] font-mono text-slate-500">
                        {task.dueTime}
                      </span>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => deleteTask(task.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 className="w-3 h-3 text-slate-500 hover:text-red-400" />
                </button>
              </div>
            ))
          )}
        </div>

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
                "flex-1 bg-slate-900/50 border border-cyan-500/30 rounded px-2 py-1",
                "text-cyan-100 placeholder:text-slate-500 font-mono text-xs",
                "focus:outline-none focus:border-cyan-400"
              )}
              autoFocus
            />
            <HudButton onClick={addTask} size="sm" variant="primary">
              Add
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
