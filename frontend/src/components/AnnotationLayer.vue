<template>
  <div class="anno-container" ref="containerRef" :style="{ cursor: cursorStyle }">
    <img
      ref="imgRef"
      :src="imageUrl"
      alt="试卷"
      class="anno-image"
      draggable="false"
      @load="syncSize"
    />
    <svg
      v-if="ready"
      ref="svgRef"
      class="anno-svg"
      :width="displayW"
      :height="displayH"
      :viewBox="`0 0 ${displayW} ${displayH}`"
      :style="{ pointerEvents: editMode ? 'all' : 'none' }"
      @mousedown="onSvgMouseDown"
    >
      <rect
        v-for="item in allAreas"
        :key="`${item.key.sectionIdx}-${item.key.problemIdx}-${item.key.areaIdx}`"
        :x="normToPx(item.area.bbox.x, 'x')"
        :y="normToPx(item.area.bbox.y, 'y')"
        :width="normToPx(item.area.bbox.w, 'w')"
        :height="normToPx(item.area.bbox.h, 'h')"
        :class="areaRectClass(item.key)"
        @mousedown.stop="onAreaMouseDown($event, item.key)"
      />
      <rect
        v-if="drawingRect"
        :x="drawingRect.x"
        :y="drawingRect.y"
        :width="drawingRect.w"
        :height="drawingRect.h"
        class="drawing-rect"
      />
    </svg>

    <div
      v-if="editMode && !drawMode"
      class="anno-overlay-hint"
      :style="{ pointerEvents: 'none' }"
    >
      <span v-if="!selectedArea">点击已有框选中，或点击"新建标注"绘制新框</span>
      <span v-else>拖拽移动选中框，或点击"删除选中"移除</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useAnalysisStore, type AreaKey } from '@/stores/analysis'
import type { BBox } from '@/types'

const props = defineProps<{
  imageUrl: string
  imageWidth: number
  imageHeight: number
}>()

const emit = defineEmits<{
  drawingEnd: [bbox: BBox]
}>()

const store = useAnalysisStore()
const containerRef = ref<HTMLElement>()
const imgRef = ref<HTMLImageElement>()
const svgRef = ref<SVGSVGElement>()
const ready = ref(false)
const displayW = ref(0)
const displayH = ref(0)

const drawingRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const drawingStart = ref<{ x: number; y: number } | null>(null)
const dragging = ref(false)
const dragStart = ref<{ x: number; y: number } | null>(null)
const dragOrigBbox = ref<BBox | null>(null)

const editMode = computed(() => store.editMode)
const drawMode = computed(() => store.drawMode)
const selectedArea = computed(() => store.selectedArea)

const cursorStyle = computed(() => {
  if (drawMode.value) return 'crosshair'
  if (editMode.value && selectedArea.value) return 'move'
  if (editMode.value) return 'default'
  return 'default'
})

const allAreas = computed(() => store.getAllAreas())

function syncSize() {
  const img = imgRef.value
  if (!img) return
  displayW.value = img.clientWidth
  displayH.value = img.clientHeight
  ready.value = true
}

function normToPx(val: number, _dim: 'x' | 'y' | 'w' | 'h'): number {
  if (_dim === 'x' || _dim === 'w') return val * displayW.value
  return val * displayH.value
}

function pxToNormX(px: number): number {
  if (displayW.value === 0) return 0
  return px / displayW.value
}

function pxToNormY(px: number): number {
  if (displayH.value === 0) return 0
  return px / displayH.value
}

function getSvgCoords(e: MouseEvent): { x: number; y: number } {
  const svg = svgRef.value
  if (!svg) return { x: 0, y: 0 }
  const rect = svg.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function areaRectClass(key: AreaKey) {
  const sel = selectedArea.value
  const isSel = sel && sel.sectionIdx === key.sectionIdx &&
    sel.problemIdx === key.problemIdx && sel.areaIdx === key.areaIdx
  return {
    'area-rect': true,
    'selected': isSel,
    'editing': editMode.value,
  }
}

function isSelected(key: AreaKey): boolean {
  const sel = selectedArea.value
  return !!(sel && sel.sectionIdx === key.sectionIdx &&
    sel.problemIdx === key.problemIdx && sel.areaIdx === key.areaIdx)
}

function onAreaMouseDown(e: MouseEvent, key: AreaKey) {
  if (!editMode.value) return
  if (drawMode.value) return

  store.selectArea(key)

  dragging.value = true
  dragStart.value = getSvgCoords(e)

  const area = store.getAreaByKey(key)
  if (area) {
    dragOrigBbox.value = { ...area.bbox }
  }

  e.preventDefault()
}

function onSvgMouseDown(e: MouseEvent) {
  if (!editMode.value) return
  if (!drawMode.value) return

  const coords = getSvgCoords(e)
  drawingStart.value = coords
  drawingRect.value = { x: coords.x, y: coords.y, w: 0, h: 0 }
}

function onMouseMove(e: MouseEvent) {
  if (dragging.value && dragStart.value && dragOrigBbox.value && selectedArea.value) {
    const coords = getSvgCoords(e)
    const dx = coords.x - dragStart.value.x
    const dy = coords.y - dragStart.value.y

    const newBbox: BBox = {
      x: Math.max(0, Math.min(1, dragOrigBbox.value.x + pxToNormX(dx))),
      y: Math.max(0, Math.min(1, dragOrigBbox.value.y + pxToNormY(dy))),
      w: dragOrigBbox.value.w,
      h: dragOrigBbox.value.h,
    }

    if (newBbox.x + newBbox.w > 1) newBbox.x = 1 - newBbox.w
    if (newBbox.y + newBbox.h > 1) newBbox.y = 1 - newBbox.h

    store.updateArea(selectedArea.value, newBbox)
  }

  if (drawingStart.value && drawingRect.value) {
    const coords = getSvgCoords(e)
    const x1 = Math.min(drawingStart.value.x, coords.x)
    const y1 = Math.min(drawingStart.value.y, coords.y)
    const x2 = Math.max(drawingStart.value.x, coords.x)
    const y2 = Math.max(drawingStart.value.y, coords.y)
    drawingRect.value = { x: x1, y: y1, w: x2 - x1, h: y2 - y1 }
  }
}

function onMouseUp(e: MouseEvent) {
  if (dragging.value) {
    dragging.value = false
    dragStart.value = null
    dragOrigBbox.value = null
    return
  }

  if (drawingStart.value && drawingRect.value && drawingRect.value.w > 10 && drawingRect.value.h > 10) {
    const rect = drawingRect.value
    const bbox: BBox = {
      x: pxToNormX(rect.x),
      y: pxToNormY(rect.y),
      w: pxToNormX(rect.w),
      h: pxToNormY(rect.h),
    }
    emit('drawingEnd', bbox)
  }

  drawingStart.value = null
  drawingRect.value = null
}

function onKeyDown(e: KeyboardEvent) {
  if (!editMode.value) return
  if (e.key === 'Delete' || e.key === 'Backspace') {
    store.deleteSelectedArea()
  }
  if (e.key === 'Escape') {
    store.exitEdit()
  }
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  const img = imgRef.value
  if (img) {
    resizeObserver = new ResizeObserver(() => syncSize())
    resizeObserver.observe(img)
  }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  window.removeEventListener('keydown', onKeyDown)
})

watch(() => props.imageUrl, () => {
  ready.value = false
})
</script>

<style scoped>
.anno-container {
  position: relative;
  display: inline-block;
  line-height: 0;
  user-select: none;
  -webkit-user-select: none;
}

.anno-image {
  display: block;
  max-width: 100%;
  max-height: 65vh;
}

.anno-svg {
  position: absolute;
  top: 0;
  left: 0;
}

.area-rect {
  fill: rgba(229, 57, 53, 0.15);
  stroke: #e53935;
  stroke-width: 2;
  cursor: pointer;
  transition: fill 0.15s;
}

.area-rect.editing {
  fill: rgba(229, 57, 53, 0.2);
  stroke: #e53935;
  stroke-width: 2;
}

.area-rect.editing:hover {
  fill: rgba(229, 57, 53, 0.35);
}

.area-rect.selected {
  fill: rgba(229, 57, 53, 0.4);
  stroke: #c62828;
  stroke-width: 3;
  stroke-dasharray: 6 3;
}

.drawing-rect {
  fill: rgba(64, 158, 255, 0.15);
  stroke: #409eff;
  stroke-width: 2;
  stroke-dasharray: 6 3;
}

.anno-overlay-hint {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 12px;
  padding: 4px 14px;
  border-radius: 100px;
  white-space: nowrap;
}
</style>
