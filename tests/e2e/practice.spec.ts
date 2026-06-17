import { expect, type Page, test } from '@playwright/test'

async function startOrContinuePractice(page: Page) {
  const entryButton = page.getByRole('button', { name: /^(\u5f00\u59cb\u7ec3\u4e60|\u7ee7\u7eed\u7ec3\u4e60)$/ })
  await expect(entryButton).toBeVisible()
  await entryButton.click()
}

async function switchToSection(page: Page, section: '01' | '02') {
  await page
    .getByRole('tab', { name: new RegExp(`^(Section\\s*)?${section}|\\u7b2c\\s*${Number(section)}\\s*\\u90e8\\u5206`) })
    .click()
}

function questionInput(page: Page, questionNumber: number) {
  return page.getByLabel(new RegExp(`^(\\u7b2c\\s*)?${questionNumber}\\s*(\\u9898|\\.)?$|^Question\\s*${questionNumber}$`, 'i'))
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
    const followButtonBox = await page.getByRole('button', { name: /^\u539f\u6587\u8ddf\u8bfb$/ }).boundingBox()
    expect(sideBox).not.toBeNull()
    expect(followButtonBox).not.toBeNull()
    expect(followButtonBox!.y + followButtonBox!.height).toBeLessThanOrEqual(sideBox!.y + sideBox!.height + 1)
  })

  test('captures a wrong blank into the mistake vocabulary notebook and completes practice', async ({ page }) => {
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

    await page.getByRole('button', { name: /^\u5168\u91cf\u987a\u5e8f\u7ec3\u4e60$/ }).click()
    await page.getByRole('button', { name: /^\u64ad\u653e$/ }).first().click()
    await page.getByLabel('听写答案').fill('Ardleigh')
    await page.getByRole('button', { name: /^\u63d0\u4ea4\u542c\u5199$/ }).click()

    await expect(page.getByText('正确拼写：Ardleigh')).toBeVisible()
    await expect(page.getByText('阿德利').first()).toBeVisible()
    await page.getByRole('button', { name: /^\u5b8c\u6210\u672c\u8f6e$|^\u4e0b\u4e00\u5f20$/ }).click()
    await expect(page.getByText(/本轮结果：1 \/ 1/)).toBeVisible()

    await ardleighCard.getByRole('button', { name: /^\u79fb\u9664$/ }).click()
    await expect(ardleighCard).toHaveCount(0)
  })
})
