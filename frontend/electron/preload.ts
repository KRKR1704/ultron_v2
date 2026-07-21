import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

// ── Type definitions ──────────────────────────────────────────────────────────

export interface WindowState {
  isMaximized: boolean
}

export interface ElectronAPI {
  minimize: () => void
  maximize: () => void
  close: () => void
  getWindowState: () => Promise<WindowState>
  openExternal: (url: string) => void
  onWindowStateChange: (callback: (event: IpcRendererEvent, state: WindowState) => void) => void
}

export interface VersionInfo {
  node: string
  chrome: string
  electron: string
}

// ── Expose safe IPC bridge to renderer ───────────────────────────────────────

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close: () => ipcRenderer.send('close-window'),
  getWindowState: (): Promise<WindowState> => ipcRenderer.invoke('get-window-state'),
  openExternal: (url: string) => ipcRenderer.send('open-external', url),
  onWindowStateChange: (callback: (event: IpcRendererEvent, state: WindowState) => void) => {
    ipcRenderer.on('window-state-changed', callback)
  },
} satisfies ElectronAPI)

contextBridge.exposeInMainWorld('versions', {
  node: process.versions.node,
  chrome: process.versions.chrome,
  electron: process.versions.electron,
} satisfies VersionInfo)
