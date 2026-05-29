<template>
  <div>
    <div class="page-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
        <h3 style="margin: 0">批改历史记录</h3>
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <div v-if="loading && !items.length" class="progress-overlay">
        <el-icon class="is-loading" :size="32" color="#409EFF"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="!items.length" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><FolderOpened /></el-icon>
        <p>暂无批改历史记录</p>
        <el-button type="primary" @click="$router.push('/')">去批改试卷</el-button>
      </div>

      <div v-else class="history-grid">
        <el-card v-for="item in items" :key="item.grading_id" class="history-card" shadow="hover" @click="openGrading(item.grading_id)">
          <div style="padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <h4 style="margin: 0; font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px;">
                {{ item.original_filename || '未命名试卷' }}
              </h4>
              <div style="display: flex; gap: 4px;">
                <el-tag size="small">{{ item.subject }}</el-tag>
                <el-tag size="small" type="info">{{ item.stage }}</el-tag>
              </div>
            </div>
            <div class="card-meta">
              <span>{{ item.sections_count }} 大题</span>
              <span>{{ item.problems_count }} 小题</span>
              <span v-if="item.total_score != null" class="score-text" :class="scoreClass(item)">
                得分 {{ item.total_score }}/{{ item.total_max_score }}
              </span>
            </div>
            <div class="card-time">{{ formatTime(item.created_at) }}</div>
            <el-button text size="small" type="danger" style="margin-top: 8px" @click.stop="handleDelete(item.grading_id, $event)">
              删除
            </el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Loading, FolderOpened } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { getGradingHistory, deleteGrading } from '@/api'
import type { GradingHistoryItem } from '@/types'

const router = useRouter()
const items = ref<GradingHistoryItem[]>([])
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    items.value = await getGradingHistory()
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function openGrading(gradingId: string) {
  router.push({ path: '/', query: { grading_id: gradingId } })
}

async function handleDelete(gradingId: string, e: Event) {
  try {
    await ElMessageBox.confirm('确定删除这条批改记录？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteGrading(gradingId)
    ElMessage.success('已删除')
    refresh()
  } catch { /* cancelled */ }
}

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function scoreClass(item: GradingHistoryItem): string {
  if (item.total_max_score == null || item.total_max_score === 0) return ''
  const pct = item.total_score! / item.total_max_score
  return pct >= 0.6 ? 'score-good' : 'score-bad'
}

onMounted(refresh)
</script>

<style scoped>
.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}

.card-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 2px;
}

.score-text { font-weight: 600; }
.score-good { color: #67C23A; }
.score-bad { color: #F56C6C; }
</style>
