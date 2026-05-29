<template>
  <el-card class="history-card" shadow="hover" @click="$emit('select', item.run_id)">
    <AnnoThumbnail
      :image-url="item.original_image_url"
      :image-width="item.image_width"
      :image-height="item.image_height"
      :preview-bboxes="item.preview_bboxes"
    />
    <div style="padding: 12px 16px">
      <h4 class="card-title">{{ item.title }}</h4>
      <div class="card-meta">
        <span>{{ item.sections_count }} 大题</span>
        <span>{{ item.problems_count }} 小题</span>
        <span>{{ item.areas_count }} 区域</span>
      </div>
      <div class="card-time">{{ formatTime(item.created_at) }}</div>
      <el-button
        text
        size="small"
        type="danger"
        style="margin-top: 8px"
        @click.stop="handleDelete"
      >
        删除
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { HistoryItem } from '@/types'
import AnnoThumbnail from '@/components/AnnoThumbnail.vue'
import { deleteResult } from '@/api'
import { ElMessageBox, ElMessage } from 'element-plus'

const props = defineProps<{
  item: HistoryItem
}>()

const emit = defineEmits<{
  select: [runId: string]
  deleted: []
}>()

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定删除这条分析记录？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteResult(props.item.run_id)
    ElMessage.success('已删除')
    emit('deleted')
  } catch { /* cancelled */ }
}
</script>

<style scoped>
.card-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 6px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.card-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 2px;
}
</style>
