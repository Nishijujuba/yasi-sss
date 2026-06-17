# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: chrome-regression.spec.ts >> Chrome regression audit >> covers audio, cropped pages, cleaned watermark area, and compact overlays
- Location: tests\e2e\chrome-regression.spec.ts:34:3

# Error details

```
Error: expect(received).toBeGreaterThanOrEqual(expected)

Expected: >= 1
Received:    0
```

# Page snapshot

```yaml
- main [ref=e3]:
  - generic [ref=e4]:
    - generic [ref=e5]:
      - generic [ref=e6]: Cambridge IELTS 10 Test 1 Listening
      - generic [ref=e7]: Listening Section 01
    - tablist "Section 导航" [ref=e8]:
      - tab "01" [selected] [ref=e9] [cursor=pointer]
      - tab "02" [ref=e10] [cursor=pointer]
      - tab "03" [ref=e11] [cursor=pointer]
      - tab "04" [ref=e12] [cursor=pointer]
    - region "Section 01 音频" [ref=e13]:
      - generic [ref=e14]:
        - strong [ref=e15]: 音频 Section 01
        - generic "保存的播放位置" [ref=e16]: 约 0 秒
      - generic [ref=e18]:
        - button "播放" [ref=e19] [cursor=pointer]
        - button "暂停" [ref=e20] [cursor=pointer]
        - button "后退 5 秒" [ref=e21] [cursor=pointer]
        - button "前进 5 秒" [ref=e22] [cursor=pointer]
  - generic [ref=e23]:
    - region "题面滚动区" [ref=e24]:
      - article "page-010.png 题面" [ref=e25]:
        - img "page-010.png 原始题面" [ref=e26]
        - generic "page-010.png 答题层" [ref=e27]:
          - textbox "第 1 题" [ref=e29]
          - textbox "第 2 题" [ref=e31]
          - textbox "第 3 题" [ref=e33]
          - textbox "第 4 题" [ref=e35]
          - textbox "第 5 题" [ref=e37]
          - textbox "第 6 题" [ref=e39]
      - article "page-011.png 题面" [ref=e40]:
        - img "page-011.png 原始题面" [ref=e41]
        - generic "page-011.png 答题层" [ref=e42]:
          - textbox "第 7 题" [ref=e44]
          - textbox "第 8 题" [ref=e46]
          - textbox "第 9 题" [ref=e48]
          - textbox "第 10 题" [ref=e50]
    - generic [ref=e51]:
      - region "练习进度" [ref=e52]: 已作答 0 / 40
      - complementary "练习操作" [ref=e53]:
        - region "快捷键说明" [ref=e54]:
          - strong [ref=e55]: 快捷键
          - paragraph [ref=e56]: Enter：播放 / 暂停
          - paragraph [ref=e57]: Alt + ← / →：跳转 5 秒
        - button "提交答案" [ref=e58] [cursor=pointer]
        - button "下一错误题" [disabled] [ref=e59]
        - button "返回首页" [ref=e60] [cursor=pointer]
        - button "重置练习" [ref=e61] [cursor=pointer]
        - button "精听" [disabled] [ref=e62]
        - button "原文跟读" [disabled] [ref=e63]
```

# Test source

```ts
  1   | import { expect, test, type Page } from '@playwright/test'
  2   | 
  3   | const expectedPageHeights: Record<string, number> = {
  4   |   'page-010.png': 1462,
  5   |   'page-011.png': 800,
  6   |   'page-012.png': 560,
  7   |   'page-013.png': 880,
  8   |   'page-014.png': 1120,
  9   |   'page-015.png': 690,
  10  |   'page-016.png': 1467,
  11  | }
  12  | 
  13  | const expectedOverlayRects: Record<string, { x: number; y: number; w: number; h: number }> = {
  14  |   q3: { x: 585, y: 1052, w: 185, h: 36 },
  15  |   q8: { x: 800, y: 502, w: 99, h: 36 },
  16  |   q14: { x: 169, y: 455, w: 178, h: 30 },
  17  |   q27: { x: 518, y: 384, w: 179, h: 36 },
  18  |   q31: { x: 573, y: 459, w: 184, h: 36 },
  19  |   q38: { x: 775, y: 972, w: 184, h: 36 },
  20  |   q40: { x: 359, y: 1155, w: 208, h: 36 },
  21  | }
  22  | 
  23  | async function enterPractice(page: Page) {
  24  |   await page.goto('/')
  25  |   const startOrContinue = page.getByRole('button', { name: /^(开始练习|继续练习)$/ })
  26  |   await startOrContinue.click()
  27  | }
  28  | 
  29  | async function switchSection(page: Page, label: string) {
  30  |   await page.getByRole('tab', { name: label }).click()
  31  | }
  32  | 
  33  | test.describe('Chrome regression audit', () => {
  34  |   test('covers audio, cropped pages, cleaned watermark area, and compact overlays', async ({ page }) => {
  35  |     await enterPractice(page)
  36  | 
  37  |     const audioState = await page.locator('audio').evaluate((audio: HTMLAudioElement) => ({
  38  |       src: audio.currentSrc || audio.src,
  39  |       readyState: audio.readyState,
  40  |       errorCode: audio.error?.code ?? null,
  41  |     }))
  42  |     expect(audioState.src).toContain('/assets/audio/section-01.mp3')
  43  |     expect(audioState.errorCode).toBeNull()
> 44  |     expect(audioState.readyState).toBeGreaterThanOrEqual(1)
      |                                   ^ Error: expect(received).toBeGreaterThanOrEqual(expected)
  45  | 
  46  |     for (const section of ['01', '02', '03', '04']) {
  47  |       await switchSection(page, section)
  48  |       await expect(page.getByText(`Listening Section ${section}`)).toBeVisible()
  49  | 
  50  |       const sectionState = await page.evaluate((heights) => {
  51  |         const pages = [...document.querySelectorAll<HTMLElement>('.question-page')].map((pageNode) => {
  52  |           const image = pageNode.querySelector<HTMLImageElement>('img')
  53  |           const pageName = image?.src.split('/').pop() ?? ''
  54  |           const canvas = document.createElement('canvas')
  55  |           const context = canvas.getContext('2d')
  56  |           let watermarkDarkPixels = 0
  57  | 
  58  |           if (image !== null && context !== null) {
  59  |             canvas.width = image.naturalWidth
  60  |             canvas.height = image.naturalHeight
  61  |             context.drawImage(image, 0, 0)
  62  |             const left = Math.min(680, image.naturalWidth)
  63  |             const width = Math.max(0, image.naturalWidth - left)
  64  |             const height = Math.min(120, image.naturalHeight)
  65  |             if (width > 0 && height > 0) {
  66  |               const data = context.getImageData(left, 0, width, height).data
  67  |               for (let index = 0; index < data.length; index += 4) {
  68  |                 const luminance = 0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2]
  69  |                 if (luminance < 180) watermarkDarkPixels += 1
  70  |               }
  71  |             }
  72  |           }
  73  | 
  74  |           return {
  75  |             pageName,
  76  |             naturalHeight: image?.naturalHeight ?? 0,
  77  |             expectedHeight: heights[pageName],
  78  |             watermarkDarkPixels,
  79  |           }
  80  |         })
  81  | 
  82  |         const overlays = [...document.querySelectorAll<HTMLElement>('.interaction-overlay')].map((node) => {
  83  |           const rect = node.getBoundingClientRect()
  84  |           const pageNode = node.closest<HTMLElement>('.question-page')
  85  |           const pageRect = pageNode?.getBoundingClientRect()
  86  |           const image = pageNode?.querySelector<HTMLImageElement>('img')
  87  |           const scale = image !== undefined && image !== null && pageRect !== undefined ? pageRect.width / image.naturalWidth : 1
  88  |           return {
  89  |             questionId: node.dataset.questionId ?? '',
  90  |             width: rect.width,
  91  |             height: rect.height,
  92  |             pixel: pageRect === undefined
  93  |               ? null
  94  |               : {
  95  |                   x: Math.round((rect.x - pageRect.x) / scale),
  96  |                   y: Math.round((rect.y - pageRect.y) / scale),
  97  |                   w: Math.round(rect.width / scale),
  98  |                   h: Math.round(rect.height / scale),
  99  |                 },
  100 |             overlayOnlyChoiceCount: node.querySelectorAll('.choice-option[data-overlay-only="true"]').length,
  101 |           }
  102 |         })
  103 | 
  104 |         return { pages, overlays }
  105 |       }, expectedPageHeights)
  106 | 
  107 |       for (const pageState of sectionState.pages) {
  108 |         expect(pageState.naturalHeight).toBe(pageState.expectedHeight)
  109 |         expect(pageState.watermarkDarkPixels).toBeLessThan(150)
  110 |       }
  111 | 
  112 |       for (const overlay of sectionState.overlays) {
  113 |         if (overlay.overlayOnlyChoiceCount > 0) {
  114 |           expect(overlay.width).toBeLessThanOrEqual(24)
  115 |           expect(overlay.height).toBeLessThanOrEqual(24)
  116 |         }
  117 | 
  118 |         const expectedRect = expectedOverlayRects[overlay.questionId]
  119 |         if (expectedRect !== undefined) {
  120 |           expect(overlay.pixel).toEqual(expectedRect)
  121 |         }
  122 |       }
  123 |     }
  124 |   })
  125 | })
  126 | 
```