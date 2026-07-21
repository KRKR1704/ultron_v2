// ── Audio utilities for ULTRON ────────────────────────────────────────────────
// Uses the Web Audio API (works in both browser and Electron).
//
// KEY DESIGN: all playback goes through a queue so responses never overlap.
// playAudioBase64() enqueues audio — if nothing is playing it starts immediately,
// otherwise it waits its turn. stopAudio() clears the queue and kills the
// current source so the next user message can play cleanly.

let audioContext: AudioContext | null = null

function getAudioContext(): AudioContext {
  if (!audioContext || audioContext.state === 'closed') {
    audioContext = new AudioContext()
  }
  return audioContext
}

// ── Queue state ───────────────────────────────────────────────────────────────

const _queue: string[]                      = []   // pending base64 strings
let   _currentSource: AudioBufferSourceNode | null = null
let   _isPlaying    = false

/** Drain the queue — plays one clip then recursively starts the next. */
async function _drainQueue(): Promise<void> {
  if (_isPlaying || _queue.length === 0) return
  _isPlaying = true

  const base64 = _queue.shift()!

  try {
    const ctx = getAudioContext()
    if (ctx.state === 'suspended') await ctx.resume()

    // Decode base64 → ArrayBuffer
    const binaryStr = atob(base64)
    const bytes     = new Uint8Array(binaryStr.length)
    for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i)

    const audioBuffer = await ctx.decodeAudioData(bytes.buffer)

    await new Promise<void>((resolve) => {
      const source      = ctx.createBufferSource()
      source.buffer     = audioBuffer
      source.connect(ctx.destination)
      source.onended    = () => { _currentSource = null; resolve() }
      _currentSource    = source
      source.start(0)
    })
  } catch (err) {
    console.error('[audio] playback error:', err)
    _currentSource = null
  }

  _isPlaying = false

  // Play next clip if queued
  if (_queue.length > 0) await _drainQueue()
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Enqueue a base64-encoded audio clip for sequential playback.
 * Never overlaps with other clips — waits its turn in the queue.
 * Returns a Promise that resolves when THIS clip finishes playing.
 */
export async function playAudioBase64(base64: string): Promise<void> {
  if (!base64) return
  _queue.push(base64)
  await _drainQueue()
}

/**
 * Immediately stop whatever is playing and clear all queued audio.
 * Call this when the user sends a new message so stale audio never plays.
 */
export function stopAudio(): void {
  // Clear pending queue
  _queue.length = 0

  // Kill the currently playing source
  if (_currentSource) {
    try { _currentSource.stop() } catch { /* already stopped */ }
    _currentSource = null
  }

  _isPlaying = false
}

// ── Recording ─────────────────────────────────────────────────────────────────

/**
 * Request microphone access, record until the caller calls stop(), and
 * return the captured audio as a base64-encoded string.
 *
 * Usage:
 *   const { stop } = await startMicRecording()
 *   const base64   = await stop()
 */
export async function startMicRecording(): Promise<{ stop: () => Promise<string> }> {
  let stream: MediaStream

  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
  } catch (err) {
    const message =
      err instanceof DOMException && err.name === 'NotAllowedError'
        ? 'Microphone permission denied. Please allow microphone access.'
        : 'Could not access microphone.'
    console.error('[audio] getUserMedia failed:', err)
    throw new Error(message)
  }

  const mimeType = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm', '']
    .find((t) => !t || MediaRecorder.isTypeSupported(t)) ?? ''

  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
  const chunks: Blob[] = []

  recorder.addEventListener('dataavailable', (e) => {
    if (e.data.size > 0) chunks.push(e.data)
  })
  recorder.start()

  const stop = (): Promise<string> =>
    new Promise((resolve, reject) => {
      recorder.addEventListener('stop', () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob   = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        const reader = new FileReader()
        reader.onloadend = () => {
          const result = reader.result as string
          resolve(result.split(',')[1] ?? '')
        }
        reader.onerror = () => reject(new Error('Failed to encode audio'))
        reader.readAsDataURL(blob)
      })
      recorder.stop()
    })

  return { stop }
}
