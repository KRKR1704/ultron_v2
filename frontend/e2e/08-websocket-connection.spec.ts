import { test, expect } from '@playwright/test'
import { launchUltronApp } from './fixtures/electron-app'
import type { ElectronApplication, Page } from 'playwright'

test.describe('08 — WebSocket connection', () => {
  let app: ElectronApplication
  let page: Page

  test.beforeEach(async () => {
    const launched = await launchUltronApp()
    app = launched.app
    page = launched.page
  })

  test.afterEach(async () => {
    await app?.close()
  })

  test('page opens a WebSocket to ws://localhost:8000/ws on load', async () => {
    const wsUrls: string[] = []
    const wsEvents: { url: string; event: string }[] = []

    page.on('websocket', (ws) => {
      wsUrls.push(ws.url())
      wsEvents.push({ url: ws.url(), event: 'created' })
      ws.on('close', () => wsEvents.push({ url: ws.url(), event: 'close' }))
      ws.on('socketerror', (err) => wsEvents.push({ url: ws.url(), event: `error:${err}` }))
    })

    await page.waitForTimeout(4000)

    // eslint-disable-next-line no-console
    console.log('WebSocket URLs observed:', wsUrls)
    // eslint-disable-next-line no-console
    console.log('WebSocket events observed:', wsEvents)

    expect(wsUrls.some((u) => u.includes('/ws'))).toBe(true)
  })
})
