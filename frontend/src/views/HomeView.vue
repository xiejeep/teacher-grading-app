<template>
  <div>
    <div class="split-layout" :class="{ 'has-result': store.result }">
      <div class="page-card">
        <ImageUploader
          :analyzing="store.loading"
          @analyze="handleAnalyze"
        />

        <el-alert
          v-if="store.error"
          :title="store.error"
          type="error"
          show-icon
          :closable="true"
          style="margin-top: 16px"
          @close="store.clearResult()"
        />
      </div>

      <div v-if="store.result" class="page-card">
        <div class="result-header">
          <h3>分析结果</h3>
          <el-tag v-if="!store.editMode" type="success" size="small">完成</el-tag>
          <el-tag v-else type="warning" size="small">编辑中</el-tag>
        </div>

        <div class="edit-toolbar">
          <template v-if="!store.editMode">
            <el-button type="primary" size="small" @click="store.enterEdit()">
              编辑标注
            </el-button>
          </template>
          <template v-else>
            <el-button
              :type="store.drawMode ? 'warning' : 'default'"
              size="small"
              @click="store.toggleDrawMode()"
            >
              {{ store.drawMode ? '退出绘制' : '新建标注' }}
            </el-button>
            <el-button
              type="danger"
              size="small"
              :disabled="!store.selectedArea"
              @click="store.deleteSelectedArea()"
            >
              删除选中
            </el-button>
            <el-button
              type="primary"
              size="small"
              :loading="store.saving"
              @click="store.saveLayout()"
            >
              保存
            </el-button>
            <el-button size="small" @click="store.exitEdit()">
              取消
            </el-button>
          </template>

          <el-dropdown v-if="store.result" @command="handleExport">
            <el-button size="small" :disabled="exporting">
              {{ exporting ? '导出中...' : '导出标注' }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="svg">SVG（矢量，推荐打印）</el-dropdown-item>
                <el-dropdown-item command="png">透明 PNG</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-divider style="margin: 8px 0" />

        <div class="canvas-wrapper-panel">
          <AnnotationCanvas />
        </div>
        <el-divider style="margin: 8px 0" />
        <ResultDetail :result="store.result" />
      </div>
    </div>

    <div v-if="store.loading" class="page-card" style="margin-top: 16px">
      <div class="progress-overlay">
        <el-icon class="is-loading" :size="36" color="#409EFF">
          <Loading />
        </el-icon>
        <div class="progress-text">AI 正在分析试卷版面结构，请耐心等待...</div>
        <div style="font-size: 13px; color: #909399">
          正在提取大题、小题、填空位置与作答区域
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Loading, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import ImageUploader from '@/components/ImageUploader.vue'
import AnnotationCanvas from '@/components/AnnotationCanvas.vue'
import ResultDetail from '@/components/ResultDetail.vue'
import { useAnalysisStore } from '@/stores/analysis'
import { toSvgBlob, toPngBlob, downloadBlob } from '@/utils/exportAnnotations'

const route = useRoute()
const store = useAnalysisStore()
const exporting = ref(false)

watch(() => route.query.run_id, (runId) => {
  if (runId && typeof runId === 'string') {
    store.loadResult(runId)
  }
}, { immediate: true })

function handleAnalyze(file: File) {
  store.analyze(file)
}

async function handleExport(format: string) {
  if (!store.result) return
  const { sections, image_width, image_height, run_id } = store.result
  exporting.value = true
  try {
    if (format === 'svg') {
      const blob = toSvgBlob(sections, image_width, image_height)
      downloadBlob(blob, `annotations_${run_id}.svg`)
    } else if (format === 'png') {
      const blob = await toPngBlob(sections, image_width, image_height)
      downloadBlob(blob, `annotations_${run_id}.png`)
    }
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-header h3 {
  margin: 0;
  font-size: 15px;
}

.edit-toolbar {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.canvas-wrapper-panel {
  max-height: 55vh;
  overflow: auto;
  border-radius: 8px;
  background: #f0f0f0;
  display: flex;
  justify-content: center;
}
</style>
