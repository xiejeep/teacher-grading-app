<template>
  <div>
    <div
      class="upload-area"
      :class="{ active: dragging }"
      @click="triggerInput"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="handleDrop"
    >
      <input
        ref="inputRef"
        type="file"
        accept="image/*"
        style="display: none"
        @change="handleFileChange"
      />
      <div v-if="!previewUrl" class="upload-content">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">点击或拖拽试卷图片到此区域</div>
        <div class="upload-hint">推荐使用扫描仪扫描；若用相机拍摄，请确保拍到试卷四条边、尽量正对减少倾斜</div>
      </div>
      <div v-else class="upload-preview">
        <img :src="previewUrl" alt="预览" class="preview-image" />
        <div class="preview-actions">
          <el-button size="small" @click.stop="handleRotate">
            <el-icon><Refresh /></el-icon>旋转
          </el-button>
          <el-button size="small" type="primary" @click.stop="clearPreview">
            重新选择
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

defineProps<{ analyzing?: boolean }>()
const emit = defineEmits<{
  analyze: [file: File]
}>()

const inputRef = ref<HTMLInputElement>()
const dragging = ref(false)
const file = ref<File | null>(null)
const previewUrl = ref<string | null>(null)

function triggerInput() {
  inputRef.value?.click()
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const f = target.files?.[0]
  if (f) setFile(f)
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) setFile(f)
}

function setFile(f: File) {
  if (!f.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  handleCompress(f)
}

async function handleCompress(f: File) {
  try {
    const { compressImage } = await import('@/utils/compressImage')
    const compressed = await compressImage(f)
    file.value = compressed
    previewUrl.value = URL.createObjectURL(compressed)
    emit('analyze', compressed)
  } catch (e: any) {
    ElMessage.error(e.message || '图片处理失败')
  }
}

async function handleRotate() {
  if (!file.value) return
  try {
    const { rotateImage } = await import('@/utils/compressImage')
    const rotated = await rotateImage(file.value)
    file.value = rotated
    previewUrl.value = URL.createObjectURL(rotated)
    emit('analyze', rotated)
  } catch (e: any) {
    ElMessage.error(e.message || '旋转失败')
  }
}

function clearPreview() {
  file.value = null
  previewUrl.value = null
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<style scoped>
.upload-preview {
  position: relative;
  display: inline-block;
}

.preview-image {
  max-width: 100%;
  max-height: 320px;
  border-radius: 6px;
  object-fit: contain;
}

.preview-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
}
</style>
