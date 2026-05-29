<template>
  <div>
    <div class="page-card-header">
      <h3 style="font-size: 18px; margin: 0;">提示词管理</h3>
      <p style="color: #909399; font-size: 13px; margin: 4px 0 0 0;">
        管理不同学科和学段的 AI 分析、批改提示词模板
      </p>
    </div>

    <div style="margin-top: 20px;">
      <el-table :data="prompts" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="subject" label="学科" width="100" />
        <el-table-column prop="stage" label="学段" width="100" />
        <el-table-column prop="analysis_prompt" label="分析提示词" min-width="200">
          <template #default="{ row }">
            <el-text truncated>{{ row.analysis_prompt.slice(0, 60) }}...</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="grading_prompt" label="批改提示词" min-width="200">
          <template #default="{ row }">
            <el-text truncated>{{ row.grading_prompt.slice(0, 60) }}...</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="editPrompt(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="`编辑提示词 - ${editingPrompt?.subject} ${editingPrompt?.stage}`"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="版面分析提示词">
          <el-input
            v-model="editForm.analysis_prompt"
            type="textarea"
            :rows="10"
            placeholder="用于版面分析的系统提示词"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            提示词中可使用 {"{img_w}"} 和 {"{img_h}"} 占位符，系统会自动替换为实际图片尺寸。
          </div>
        </el-form-item>
        <el-form-item label="批改提示词">
          <el-input
            v-model="editForm.grading_prompt"
            type="textarea"
            :rows="10"
            placeholder="用于批改学生答卷的系统提示词"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            可使用 {"{standard_answers_section}"} 插入标准答案、{"{layout_json}"} 插入版面数据、{"{subject}"} 替换为学科。
          </div>
        </el-form-item>
        <el-form-item label="答案提取提示词">
          <el-input
            v-model="editForm.answer_extraction_prompt"
            type="textarea"
            :rows="6"
            placeholder="用于从答案图片中提取标准答案的提示词"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePrompt">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPrompts, updatePrompt } from '@/api'
import type { PromptResponse } from '@/types'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const prompts = ref<PromptResponse[]>([])
const editingPrompt = ref<PromptResponse | null>(null)
const editForm = ref({
  analysis_prompt: '',
  grading_prompt: '',
  answer_extraction_prompt: '',
})

onMounted(() => {
  loadPrompts()
})

async function loadPrompts() {
  loading.value = true
  try {
    prompts.value = await getPrompts()
  } catch {
    ElMessage.error('加载提示词模板失败')
  } finally {
    loading.value = false
  }
}

function editPrompt(row: PromptResponse) {
  editingPrompt.value = row
  editForm.value = {
    analysis_prompt: row.analysis_prompt,
    grading_prompt: row.grading_prompt,
    answer_extraction_prompt: row.answer_extraction_prompt,
  }
  dialogVisible.value = true
}

async function savePrompt() {
  if (!editingPrompt.value) return
  saving.value = true
  try {
    const updated = await updatePrompt(editingPrompt.value.id, editForm.value)
    const idx = prompts.value.findIndex(p => p.id === updated.id)
    if (idx !== -1) prompts.value[idx] = updated
    dialogVisible.value = false
    ElMessage.success('提示词已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}
</script>

<style scoped>
.page-card-header {
  margin-bottom: 8px;
}
</style>
