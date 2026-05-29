<template>
  <div class="canvas-wrapper" ref="wrapperRef">
    <AnnotationLayer
      v-if="store.result"
      :image-url="store.getOriginalImageUrl()"
      :image-width="store.result.image_width"
      :image-height="store.result.image_height"
      @drawing-end="onDrawingEnd"
    />

    <el-dialog v-model="showAssignDialog" title="选择归属题目" width="480px">
      <el-select v-model="assignTarget" placeholder="选择要添加到此题目" style="width: 100%">
        <el-option
          v-for="p in problemOptions"
          :key="p.value"
          :label="p.label"
          :value="p.value"
        />
      </el-select>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign" :disabled="!assignTarget">
          确定添加
        </el-button>
      </template>
    </el-dialog>

    <div v-if="!store.result" class="empty-canvas">
      <el-icon :size="48" color="#c0c4cc"><Picture /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { useAnalysisStore } from '@/stores/analysis'
import type { BBox } from '@/types'
import AnnotationLayer from '@/components/AnnotationLayer.vue'

const store = useAnalysisStore()
const wrapperRef = ref<HTMLElement>()
const showAssignDialog = ref(false)
const assignTarget = ref('')
const pendingBbox = ref<BBox | null>(null)

const problemOptions = computed(() => {
  if (!store.result) return []
  return store.result.sections.flatMap((section, si) =>
    section.problems.map((problem, pi) => ({
      sectionIdx: si,
      problemIdx: pi,
      label: `${section.title || '第' + section.section_number + '大题'} > ${problem.problem_number}. ${problem.text || '(无文字)'}`,
      value: `${si}-${pi}`,
    }))
  )
})

function onDrawingEnd(bbox: BBox) {
  if (!store.result || !store.drawMode) return
  pendingBbox.value = bbox
  store.toggleDrawMode()

  const options = problemOptions.value
  if (options.length === 0) {
    store.addArea(0, 0, bbox, 'box_area')
    return
  }
  assignTarget.value = ''
  showAssignDialog.value = true
}

function confirmAssign() {
  if (!assignTarget.value || !pendingBbox.value) return
  const [si, pi] = assignTarget.value.split('-').map(Number)
  store.addArea(si, pi, pendingBbox.value, 'box_area')
  showAssignDialog.value = false
  pendingBbox.value = null
}
</script>

<style scoped>
.canvas-wrapper {
  display: flex;
  justify-content: center;
}

.empty-canvas {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
</style>
