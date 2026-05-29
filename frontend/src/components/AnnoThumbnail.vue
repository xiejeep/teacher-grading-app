<template>
  <div class="thumb-container">
    <img
      ref="imgRef"
      :src="imageUrl"
      alt=""
      class="thumb-img"
      loading="lazy"
      @load="syncSize"
    />
    <svg
      v-if="ready"
      class="thumb-svg"
      :width="displayW"
      :height="displayH"
      :viewBox="`0 0 ${displayW} ${displayH}`"
    >
      <rect
        v-for="(b, i) in previewBboxes"
        :key="i"
        :x="b.x * displayW"
        :y="b.y * displayH"
        :width="b.w * displayW"
        :height="b.h * displayH"
        class="thumb-area"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { BBox } from '@/types'

defineProps<{
  imageUrl: string
  imageWidth: number
  imageHeight: number
  previewBboxes: BBox[]
}>()

const imgRef = ref<HTMLImageElement>()
const ready = ref(false)
const displayW = ref(0)
const displayH = ref(0)

function syncSize() {
  const img = imgRef.value
  if (!img) return
  displayW.value = img.clientWidth
  displayH.value = img.clientHeight
  ready.value = true
}
</script>

<style scoped>
.thumb-container {
  position: relative;
  line-height: 0;
  overflow: hidden;
  width: 100%;
  height: 100%;
}

.thumb-img {
  display: block;
  width: 100%;
  height: 180px;
  object-fit: cover;
  border-radius: 8px 8px 0 0;
}

.thumb-svg {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.thumb-area {
  fill: rgba(229, 57, 53, 0.12);
  stroke: #e53935;
  stroke-width: 1;
}
</style>
