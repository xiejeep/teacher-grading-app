import type { AnalysisResponse, GradingResult, BBox } from '@/types'

const CHECK_PATH = 'M997.934545 70.097455c-311.389091 191.022545-537.134545 432.221091-639.06909 552.96L110.126545 428.032 0 516.654545l429.521455 437.15491C503.342545 764.369455 737.838545 394.24 1024 131.165091l-26.065455-60.881455z'
const CROSS_PATH = 'M839 73.9c-1.2-2.4-3.7-9.8-7.4-9.8s-11.1 8.6-13.5 12.3l-13.5 12.3c-7.4-6.1-35.6-23.4-43-23.4-11.1 0-104.6 113.2-118.1 129.1l-60.2 68.8-30.7 38.1-43.1-83.6-50.4-100.8c-4.9-9.8-8.6-22.1-22.1-22.1-7.3 0-9.8 3.6-13.5 9.8-3.7 4.9-3.7 4.9-11.1 8.6-8.6 0-12.3 0-19.7 6.2-6.2-4.9-11.1-11.1-19.7-11.1-3.7 0-6.2 1.2-8.6 3.6l-8.6 7.4c-4.8 6.1-15.9 17.2-15.9 25.8 0 11 9.8 31.9 13.5 41.8l90.9 250.8-14.7 17.3c-66.4 79.8-159.8 190.5-210.2 279l-29.5 50.4c-8.6 14.7-29.5 44.3-29.5 60.2 0 3.7 3.8 6.2 6.2 8.6 8.6 7.3 3.6 14.7 1.2 24.5-2.5 7.4-3.7 12.3-3.7 19.7 0 13.5 11.1 27 18.5 38.1 7.3 12.2 9.9 24.5 25.8 24.5 17.2 0 49.2-3.6 63.9-14.7l243.4-377.5 115.6 178.5c6.1 9.8 30.7 54.1 46.7 54.1 14.8 0 38.1-16.1 40.6-30.8-2.6-4.9-6.2-12.3-6.2-17.2 0-7.5 19.7-14.9 24.6-19.7v-9.9c8.6-3.7 13.5-8.6 17.2-17.2l-95.9-205.3-38.2-76.3 13.6-19.7 174.6-225.9c11-14.8 28.3-38.1 41.8-50.4 4.9-5 13.5-12.3 13.5-19.7 0-8.6-19.7-22.1-24.6-34.4z'
const GREEN = '#d81e06'
const RED = '#F56C6C'

function normToPx(val: number, size: number): number {
  return val * size
}

function calcIconSize(w: number, h: number): number {
  const raw = Math.max(Math.min(w, h), 18)
  return Math.min(raw, 48)
}

interface GradingIcon {
  cx: number
  cy: number
  size: number
  isCorrect: boolean
}

function collectGradingIcons(
  analysis: AnalysisResponse,
  grading: GradingResult | null,
  imgW: number,
  imgH: number,
): GradingIcon[] {
  const icons: GradingIcon[] = []

  if (!grading) {
    for (const section of analysis.sections) {
      for (const problem of section.problems) {
        for (const area of problem.answer_areas) {
          const b = area.bbox
          const px = normToPx(b.x, imgW)
          const py = normToPx(b.y, imgH)
          const pw = normToPx(b.w, imgW) || 20
          const ph = normToPx(b.h, imgH) || 16
          icons.push({
            cx: px + pw / 2,
            cy: py + ph / 2,
            size: calcIconSize(pw, ph),
            isCorrect: false,
          })
        }
      }
    }
    return icons
  }

  const titleToFirstIdx = new Map<string, number>()
  analysis.sections.forEach((s, i) => {
    if (!titleToFirstIdx.has(s.title || '')) titleToFirstIdx.set(s.title || '', i)
  })

  for (const section of grading.sections) {
    const origIdx = section._orig_section_idx
    let si: number | undefined
    if (origIdx != null && origIdx < analysis.sections.length) {
      si = origIdx
    } else {
      si = titleToFirstIdx.get(section.title || '')
    }
    if (si == null) continue

    for (const problem of section.problems) {
      const pi = problem.problem_number - 1
      const analysisSection = analysis.sections[si]
      if (!analysisSection) continue
      const analysisProblem = analysisSection.problems[pi]
      if (!analysisProblem) continue

      for (const areaGrading of problem.area_gradings) {
        const ai = areaGrading.area_index
        const answerAreas = analysisProblem.answer_areas
        if (!answerAreas || ai >= answerAreas.length) continue
        const answerArea = answerAreas[ai]
        if (!answerArea) continue

        const b = answerArea.bbox
        const px = normToPx(b.x, imgW)
        const py = normToPx(b.y, imgH)
        const pw = normToPx(b.w, imgW) || 20
        const ph = normToPx(b.h, imgH) || 16

        icons.push({
          cx: px + pw / 2,
          cy: py + ph / 2,
          size: calcIconSize(pw, ph),
          isCorrect: areaGrading.is_correct === true,
        })
      }
    }
  }

  return icons
}

function iconToSvgElement(icon: GradingIcon): string {
  const half = icon.size / 2
  const path = icon.isCorrect ? CHECK_PATH : CROSS_PATH
  const color = icon.isCorrect ? GREEN : RED
  return `<g transform="translate(${icon.cx - half}, ${icon.cy - half}) scale(${icon.size / 1024})">
    <path d="${path}" fill="${color}" />
  </g>`
}

export function gradingToSvgString(
  analysis: AnalysisResponse,
  grading: GradingResult | null,
  imgW: number,
  imgH: number,
): string {
  const icons = collectGradingIcons(analysis, grading, imgW, imgH)
  const elements = icons.map(iconToSvgElement).join('\n  ')
  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${imgW}" height="${imgH}" viewBox="0 0 ${imgW} ${imgH}">`,
    `  ${elements}`,
    `</svg>`,
  ].join('\n')
}

export function gradingToSvgBlob(
  analysis: AnalysisResponse,
  grading: GradingResult | null,
  imgW: number,
  imgH: number,
): Blob {
  return new Blob([gradingToSvgString(analysis, grading, imgW, imgH)], { type: 'image/svg+xml;charset=utf-8' })
}

export async function gradingToPngBlob(
  analysis: AnalysisResponse,
  grading: GradingResult | null,
  imgW: number,
  imgH: number,
): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = imgW
  canvas.height = imgH
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')

  ctx.clearRect(0, 0, imgW, imgH)

  const icons = collectGradingIcons(analysis, grading, imgW, imgH)

  for (const icon of icons) {
    const half = icon.size / 2
    const color = icon.isCorrect ? GREEN : RED
    const pathData = icon.isCorrect ? CHECK_PATH : CROSS_PATH

    ctx.save()
    ctx.translate(icon.cx - half, icon.cy - half)
    ctx.scale(icon.size / 1024, icon.size / 1024)

    const p = new Path2D(pathData)
    ctx.fillStyle = color
    ctx.fill(p)

    ctx.restore()
  }

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b)
      else reject(new Error('Canvas toBlob failed'))
    }, 'image/png')
  })
}

// Legacy analysis-only export (for HomeView)
function getAllAreas(sections: AnalysisResponse['sections']): { bbox: BBox }[] {
  const areas: { bbox: BBox }[] = []
  for (const section of sections) {
    for (const problem of section.problems) {
      for (const area of problem.answer_areas) {
        areas.push({ bbox: area.bbox })
      }
    }
  }
  return areas
}

function svgRect(b: BBox, imgW: number, imgH: number): string {
  const x = normToPx(b.x, imgW)
  const y = normToPx(b.y, imgH)
  const w = normToPx(b.w, imgW)
  const h = normToPx(b.h, imgH)
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="rgba(229,57,53,0.15)" stroke="#e53935" stroke-width="2" />`
}

export function toSvgString(sections: AnalysisResponse['sections'], imgW: number, imgH: number): string {
  const areas = getAllAreas(sections)
  const rects = areas.map(a => svgRect(a.bbox, imgW, imgH)).join('\n  ')
  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${imgW}" height="${imgH}" viewBox="0 0 ${imgW} ${imgH}">`,
    `  ${rects}`,
    `</svg>`,
  ].join('\n')
}

export function toSvgBlob(sections: AnalysisResponse['sections'], imgW: number, imgH: number): Blob {
  return new Blob([toSvgString(sections, imgW, imgH)], { type: 'image/svg+xml;charset=utf-8' })
}

export async function toPngBlob(sections: AnalysisResponse['sections'], imgW: number, imgH: number): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = imgW
  canvas.height = imgH
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')

  ctx.clearRect(0, 0, imgW, imgH)

  const areas = getAllAreas(sections)
  for (const area of areas) {
    const b = area.bbox
    const x = normToPx(b.x, imgW)
    const y = normToPx(b.y, imgH)
    const w = normToPx(b.w, imgW)
    const h = normToPx(b.h, imgH)

    ctx.fillStyle = 'rgba(229,57,53,0.15)'
    ctx.fillRect(x, y, w, h)
    ctx.strokeStyle = '#e53935'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, w, h)
  }

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b)
      else reject(new Error('Canvas toBlob failed'))
    }, 'image/png')
  })
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Failed to load image'))
    img.src = url
  })
}

export async function compositeGradingToPngBlob(
  imageUrl: string,
  analysis: AnalysisResponse,
  grading: GradingResult | null,
  imgW: number,
  imgH: number,
): Promise<Blob> {
  const img = await loadImage(imageUrl)
  const canvas = document.createElement('canvas')
  canvas.width = imgW
  canvas.height = imgH
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')

  ctx.drawImage(img, 0, 0, imgW, imgH)

  const icons = collectGradingIcons(analysis, grading, imgW, imgH)

  for (const icon of icons) {
    const half = icon.size / 2
    const color = icon.isCorrect ? GREEN : RED
    const pathData = icon.isCorrect ? CHECK_PATH : CROSS_PATH

    ctx.save()
    ctx.translate(icon.cx - half, icon.cy - half)
    ctx.scale(icon.size / 1024, icon.size / 1024)

    const p = new Path2D(pathData)
    ctx.fillStyle = color
    ctx.fill(p)

    ctx.restore()
  }

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b)
      else reject(new Error('Canvas toBlob failed'))
    }, 'image/png')
  })
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
