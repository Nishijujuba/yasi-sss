import { expect, test, type Page } from '@playwright/test'

const expectedPageHeights: Record<string, number> = {
  'page-010.png': 1462,
  'page-011.png': 800,
  'page-012.png': 560,
  'page-013.png': 880,
  'page-014.png': 1120,
  'page-015.png': 690,
  'page-016.png': 1467,
}

const expectedOverlayRects: Record<string, { x: number; y: number; w: number; h: number }> = {
  q3: { x: 585, y: 1052, w: 185, h: 36 },
  q8: { x: 800, y: 502, w: 99, h: 36 },
  q14: { x: 169, y: 455, w: 178, h: 30 },
  q27: { x: 518, y: 384, w: 179, h: 36 },
  q31: { x: 573, y: 459, w: 184, h: 36 },
  q38: { x: 775, y: 972, w: 184, h: 36 },
  q40: { x: 359, y: 1155, w: 208, h: 36 },
}

async function enterPractice(page: Page) {
  await page.goto('/')
  const startOrContinue = page.getByRole('button', { name: /^(开始练习|继续练习)$/ })
  await startOrContinue.click()
}

async function switchSection(page: Page, label: string) {
  await page.getByRole('tab', { name: label }).click()
}

async function waitForQuestionPageImages(page: Page) {
  await page.waitForFunction(() =>
    [...document.querySelectorAll<HTMLImageElement>('.question-page img')]
      .every((image) => image.complete && image.naturalHeight > 0),
  )
}

test.describe('Chrome regression audit', () => {
  test('covers audio, cropped pages, cleaned watermark area, and compact overlays', async ({ page }) => {
    await enterPractice(page)
    await waitForQuestionPageImages(page)
    await page.waitForFunction(() => {
      const audio = document.querySelector('audio')
      return audio !== null && (audio.readyState >= 1 || audio.error !== null)
    })

    const audioState = await page.locator('audio').evaluate((audio: HTMLAudioElement) => ({
      src: audio.currentSrc || audio.src,
      readyState: audio.readyState,
      errorCode: audio.error?.code ?? null,
    }))
    expect(audioState.src).toContain('/assets/audio/section-01.mp3')
    expect(audioState.errorCode).toBeNull()
    expect(audioState.readyState).toBeGreaterThanOrEqual(1)

    await page.locator('.audio-player__controls button').first().click()
    await page.waitForFunction(() => {
      const audio = document.querySelector('audio')
      return audio !== null && !audio.paused && audio.currentTime > 0
    })
    const playbackState = await page.locator('audio').evaluate((audio: HTMLAudioElement) => ({
      currentTime: audio.currentTime,
      errorCode: audio.error?.code ?? null,
      paused: audio.paused,
    }))
    expect(playbackState.errorCode).toBeNull()
    expect(playbackState.paused).toBe(false)
    expect(playbackState.currentTime).toBeGreaterThan(0)

    for (const section of ['01', '02', '03', '04']) {
      await switchSection(page, section)
      await expect(page.getByText(`Listening Section ${section}`)).toBeVisible()
      await waitForQuestionPageImages(page)

      const sectionState = await page.evaluate((heights) => {
        const pages = [...document.querySelectorAll<HTMLElement>('.question-page')].map((pageNode) => {
          const image = pageNode.querySelector<HTMLImageElement>('img')
          const pageName = image?.src.split('/').pop() ?? ''
          const canvas = document.createElement('canvas')
          const context = canvas.getContext('2d')
          let watermarkDarkPixels = 0

          if (image !== null && context !== null) {
            canvas.width = image.naturalWidth
            canvas.height = image.naturalHeight
            context.drawImage(image, 0, 0)
            const left = Math.min(680, image.naturalWidth)
            const width = Math.max(0, image.naturalWidth - left)
            const height = Math.min(120, image.naturalHeight)
            if (width > 0 && height > 0) {
              const data = context.getImageData(left, 0, width, height).data
              for (let index = 0; index < data.length; index += 4) {
                const luminance = 0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2]
                if (luminance < 180) watermarkDarkPixels += 1
              }
            }
          }

          return {
            pageName,
            naturalHeight: image?.naturalHeight ?? 0,
            expectedHeight: heights[pageName],
            watermarkDarkPixels,
          }
        })

        const overlays = [...document.querySelectorAll<HTMLElement>('.interaction-overlay')].map((node) => {
          const rect = node.getBoundingClientRect()
          const pageNode = node.closest<HTMLElement>('.question-page')
          const pageRect = pageNode?.getBoundingClientRect()
          const image = pageNode?.querySelector<HTMLImageElement>('img')
          const scale = image !== undefined && image !== null && pageRect !== undefined ? pageRect.width / image.naturalWidth : 1
          return {
            questionId: node.dataset.questionId ?? '',
            width: rect.width,
            height: rect.height,
            pixel: pageRect === undefined
              ? null
              : {
                  x: Math.round((rect.x - pageRect.x) / scale),
                  y: Math.round((rect.y - pageRect.y) / scale),
                  w: Math.round(rect.width / scale),
                  h: Math.round(rect.height / scale),
                },
            overlayOnlyChoiceCount: node.querySelectorAll('.choice-option[data-overlay-only="true"]').length,
          }
        })

        return { pages, overlays }
      }, expectedPageHeights)

      for (const pageState of sectionState.pages) {
        expect(pageState.naturalHeight).toBe(pageState.expectedHeight)
        expect(pageState.watermarkDarkPixels).toBeLessThan(150)
      }

      for (const overlay of sectionState.overlays) {
        if (overlay.overlayOnlyChoiceCount > 0) {
          expect(overlay.width).toBeLessThanOrEqual(24)
          expect(overlay.height).toBeLessThanOrEqual(24)
        }

        const expectedRect = expectedOverlayRects[overlay.questionId]
        if (expectedRect !== undefined) {
          expect(overlay.pixel).toEqual(expectedRect)
        }
      }
    }
  })
})
