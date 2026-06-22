import { expect, type Page, test } from '@playwright/test'

async function startOrContinuePractice(page: Page) {
  const entryButton = page.getByRole('button', { name: /^(\u5f00\u59cb\u7ec3\u4e60|\u7ee7\u7eed\u7ec3\u4e60)$/ })
  await expect(entryButton).toBeVisible()
  await entryButton.click()
}

async function switchToSection(page: Page, section: '01' | '02' | '03' | '04') {
  await page
    .getByRole('tab', { name: new RegExp(`^(Section\\s*)?${section}|\\u7b2c\\s*${Number(section)}\\s*\\u90e8\\u5206`) })
    .click()
}

function questionInput(page: Page, questionNumber: number) {
  return page.getByLabel(new RegExp(`^(\\u7b2c\\s*)?${questionNumber}\\s*(\\u9898|\\.)?$|^Question\\s*${questionNumber}$`, 'i'))
}

async function nativePlaybackRate(page: Page) {
  return page.locator('audio').evaluate((audio: HTMLAudioElement) => audio.playbackRate)
}

test.describe('practice workflow', () => {
  test('continues practice, persists q1, submits, and resets answers', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('main')).toBeVisible()
    await startOrContinuePractice(page)

    const q1 = questionInput(page, 1)
    await expect(q1).toBeVisible()
    await q1.fill('Ardleigh')

    await switchToSection(page, '02')
    await page.reload()
    await startOrContinuePractice(page)
    await switchToSection(page, '01')
    await expect(questionInput(page, 1)).toHaveValue('Ardleigh')

    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()
    await expect(page.getByText(/\/\s*10/)).toBeVisible()

    await page.getByRole('button', { name: /^(\u91cd\u7f6e\u7ec3\u4e60|\u91cd\u65b0\u5f00\u59cb)$/ }).click()
    await page.getByRole('button', { name: /^\u786e\u8ba4\u91cd\u7f6e$/ }).click()
    await expect(questionInput(page, 1)).toHaveValue('')
  })

  test('keeps the feedback and action rail scrollable on a short viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1365, height: 768 })
    await page.goto('/')

    await startOrContinuePractice(page)
    await questionInput(page, 1).fill('Ardleigh')
    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()

    const sidePanel = page.locator('.workspace-side-panel')
    await expect(sidePanel).toHaveCSS('overflow-y', /auto|scroll/)

    const metrics = await sidePanel.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)

    await sidePanel.evaluate((element) => {
      element.scrollTop = element.scrollHeight
    })

    const sideBox = await sidePanel.boundingBox()
    const followButton = page.getByRole('button', { name: /^\u6253\u5f00\u539f\u6587$/ })
    await expect(followButton).toBeEnabled()
    const followButtonBox = await followButton.boundingBox()
    expect(sideBox).not.toBeNull()
    expect(followButtonBox).not.toBeNull()
    expect(followButtonBox!.y + followButtonBox!.height).toBeLessThanOrEqual(sideBox!.y + sideBox!.height + 1)
  })

  test('captures a wrong blank into mistake vocabulary, reviews, dictates, archives, and restores it', async ({ page }) => {
    await page.goto('/')
    await startOrContinuePractice(page)

    await questionInput(page, 1).fill('Ardley')
    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()
    await expect(page.getByText(/Raw score:\s*0\s*\/\s*10/)).toBeVisible()

    await page.getByRole('button', { name: /^\u8fd4\u56de\u9996\u9875$/ }).click()
    await page.getByRole('button', { name: /^\u9519\u9898\u672c$/ }).click()

    const ardleighCard = page.getByLabel('错题词 Ardleigh')
    await expect(ardleighCard).toBeVisible()
    await expect(ardleighCard.getByText('阿德利')).toBeVisible()

    await page.getByRole('tab', { name: /^\u542c\u97f3\u590d\u4e60$/ }).click()
    await page.getByLabel('间隔秒数').fill('1')
    await page.getByRole('button', { name: /^\u5168\u90e8$/ }).click()
    await expect(page.getByRole('region', { name: /^\u542c\u97f3\u590d\u4e60$/ })).toBeVisible()
    await expect(ardleighCard).toHaveAttribute('aria-current', 'true')
    await expect(page.getByText('正确拼写：Ardleigh')).toBeVisible()
    await expect(page.getByText('阿德利').first()).toBeVisible()

    await page.getByRole('button', { name: /^\u9690\u85cf\u62fc\u5199$/ }).click()
    await expect(page.getByRole('region', { name: /^\u542c\u97f3\u590d\u4e60$/ })).not.toContainText('正确拼写：Ardleigh')
    await page.getByRole('button', { name: /^\u6682\u505c$/ }).click()
    await expect(page.getByRole('button', { name: /^\u7ee7\u7eed$/ })).toBeVisible()
    await page.getByRole('button', { name: /^\u7ee7\u7eed$/ }).click()
    await page.getByRole('button', { name: /^\u505c\u6b62$/ }).click()
    await expect(page.getByRole('region', { name: /^\u542c\u97f3\u590d\u4e60$/ })).toHaveCount(0)

    await page.getByRole('tab', { name: /^\u542c\u5199\u6a21\u5f0f$/ }).click()
    await page.getByRole('button', { name: /^\u5168\u90e8$/ }).click()
    const dictation = page.getByRole('region', { name: /^\u9519\u9898\u542c\u5199\u7ec3\u4e60$/ })
    await expect(dictation).toBeVisible()
    await expect(page.getByLabel('\u9519\u9898\u8bcd 1')).toBeVisible()
    await expect(page.getByLabel('错题词 Ardleigh')).toHaveCount(0)
    await expect(page.getByLabel('\u9519\u9898\u8bcd\u5217\u8868')).not.toContainText('Ardleigh')
    await expect(page.getByLabel('\u9519\u9898\u8bcd\u5217\u8868')).not.toContainText('阿德利')
    await expect(dictation.getByRole('button', { name: /^\u64ad\u653e$|^\u63d0\u4ea4\u542c\u5199$|^\u4e0b\u4e00\u5f20$|^\u5b8c\u6210\u672c\u8f6e$/ })).toHaveCount(0)

    await page.locator('article[aria-current="true"] audio').evaluate((audio: HTMLAudioElement) => {
      audio.dispatchEvent(new Event('ended'))
    })
    await expect(page.getByText('最终准确率：0% (0 / 1)')).toBeVisible({ timeout: 5000 })
    await expect(page.getByLabel('错题词 Ardleigh').getByText('本轮：错误')).toBeVisible()
    await expect(page.getByLabel('错题词 Ardleigh').getByText('错误次数：2')).toBeVisible()

    await page.getByLabel('错题词 Ardleigh').getByRole('button', { name: /^\u5f52\u6863$/ }).click()
    await expect(page.getByLabel('错题词 Ardleigh')).toHaveCount(0)

    await page.getByRole('button', { name: /^\u67e5\u770b\u5f52\u6863$/ }).click()
    const archivedCard = page.getByLabel('归档错题词 Ardleigh')
    await expect(archivedCard).toBeVisible()
    await archivedCard.getByRole('button', { name: /^\u64ad\u653e$/ }).click()
    await archivedCard.getByRole('button', { name: /^\u6062\u590d\u5230\u9519\u9898\u672c$/ }).click()
    await page.getByRole('button', { name: /^\u8fd4\u56de\u9519\u9898\u672c$/ }).click()
    await expect(page.getByLabel('错题词 Ardleigh')).toBeVisible()

    const restoredNotebook = await page.evaluate(() => {
      const raw = localStorage.getItem('yasi:cambridge-10:test-1:listening:mistake-vocabulary:v1')
      return raw === null ? null : JSON.parse(raw)
    })
    expect(restoredNotebook?.cards?.ardleigh?.dictationAttempts).toBe(1)
    expect(restoredNotebook?.cards?.ardleigh?.mistakeCount).toBe(2)
    expect(restoredNotebook?.cards?.ardleigh?.lastDictationResult).toBe('incorrect')
    expect(restoredNotebook?.archivedCards?.ardleigh).toBeUndefined()
  })

  test('opens transcript shadowing in Sections 02 through 04', async ({ page }) => {
    await page.goto('/')
    await startOrContinuePractice(page)

    for (const section of ['02', '03', '04'] as const) {
      await switchToSection(page, section)
      const openTranscript = page.getByRole('button', { name: /^\u6253\u5f00\u539f\u6587$/ })
      await expect(openTranscript).toBeEnabled()
      await openTranscript.click()

      await expect(page.getByRole('region', { name: `Section ${section} \u539f\u6587\u8ddf\u8bfb` })).toBeVisible()
      await expect(page.getByRole('button', { name: /^\u6536\u8d77\u539f\u6587$/ })).toBeVisible()
      await page.getByRole('button', { name: /^\u6536\u8d77\u539f\u6587$/ }).click()
    }
  })

  test('\u7cbe\u542c unlocks by submitted section and keeps state isolated', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('button', { name: /^\u7cbe\u542c$/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^\u539f\u6587\u8ddf\u8bfb$/ })).toHaveCount(0)
    await startOrContinuePractice(page)

    const actionIntensive = page.getByRole('button', { name: /^\u7cbe\u542c$/ })
    await expect(actionIntensive).toBeDisabled()

    await questionInput(page, 1).fill('Ardley')
    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7b54\u6848$/ }).click()
    await expect(page.getByText(/Raw score:\s*0\s*\/\s*10/)).toBeVisible()
    await expect(actionIntensive).toBeEnabled()

    await switchToSection(page, '02')
    await expect(page.getByRole('button', { name: /^\u7cbe\u542c$/ })).toBeDisabled()
    await switchToSection(page, '01')
    await page.getByRole('button', { name: /^\u7cbe\u542c$/ }).click()

    await expect(page.getByRole('heading', { name: /Section 01 \u7cbe\u542c/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: '01' })).toBeEnabled()
    await expect(page.getByRole('tab', { name: '02' })).toBeDisabled()

    const transcript = page.getByRole('region', { name: 'Section 01 \u7cbe\u542c\u539f\u6587' })
    const firstTranscriptSegment = page.locator('.intensive-transcript__segment').first()
    await expect(transcript).toContainText('Good morning')
    await expect(firstTranscriptSegment).toContainText('How can I help you')
    await expect(firstTranscriptSegment).not.toContainText('World Tours')

    const firstBlank = page.getByRole('textbox', { name: '\u7cbe\u542c\u7a7a 1', exact: true })
    await expect(firstBlank).toBeVisible()
    await firstBlank.fill('world tour')

    const speedButton = page.getByRole('button', { name: '1.25x' })
    await speedButton.click()
    await expect(speedButton).toHaveAttribute('aria-pressed', 'true')
    expect(await nativePlaybackRate(page)).toBe(1.25)

    await page.getByRole('button', { name: /^\u63d0\u4ea4\u7cbe\u542c$/ }).click()
    await expect(page.getByText('\u62fc\u5199\u6709\u8bef').first()).toBeVisible()

    await page.getByRole('button', { name: /^\u67e5\u770b\u7b54\u6848$/ }).click()
    await expect(page.getByText('\u6b63\u786e\u7b54\u6848\uff1aWorld Tours')).toBeVisible()

    await page.getByRole('button', { name: /^\u67e5\u770b\u539f\u6587$/ }).click()
    await expect(firstTranscriptSegment).toContainText('World Tours')
    await expect(page.getByRole('textbox')).toHaveCount(0)

    await page.getByRole('button', { name: /^\u91cd\u7f6e\u7cbe\u542c$/ }).click()
    await expect(page.getByRole('textbox', { name: '\u7cbe\u542c\u7a7a 1', exact: true })).toHaveValue('')

    await page.getByRole('button', { name: /^\u8fd4\u56de\u7ec3\u4e60$/ }).click()
    await expect(questionInput(page, 1)).toHaveValue('Ardley')

    await page.getByRole('button', { name: /^\u8fd4\u56de\u9996\u9875$/ }).click()
    await page.getByRole('button', { name: /^\u9519\u9898\u672c$/ }).click()
    await expect(page.getByLabel('\u9519\u9898\u8bcd Ardleigh')).toBeVisible()
  })
})
