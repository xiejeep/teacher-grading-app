<template>
  <div>
    <div class="page-card-header">
      <h3 style="font-size: 18px; margin: 0;">AI 服务设置</h3>
      <p style="color: #909399; font-size: 13px; margin: 4px 0 0 0;">
        配置 AI 推理服务提供商和模型参数
      </p>
    </div>

    <el-card class="settings-card" v-loading="loading">
      <el-form label-position="top">
        <el-form-item label="AI 服务提供商">
          <el-radio-group v-model="form.ai_provider">
            <el-radio value="volces" border style="margin-right: 12px;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span>火山引擎 (豆包 / Volces Ark)</span>
                <el-tag v-if="currentSettings.volces_has_key" size="small" type="success">已配置</el-tag>
                <el-tag v-else size="small" type="info">未配置</el-tag>
              </div>
            </el-radio>
            <el-radio value="modelscope" border>
              <div style="display: flex; align-items: center; gap: 6px;">
                <span>ModelScope (魔搭社区)</span>
                <el-tag v-if="currentSettings.modelscope_has_key" size="small" type="success">已配置</el-tag>
                <el-tag v-else size="small" type="info">未配置</el-tag>
              </div>
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <el-divider />

        <!-- Volces fields -->
        <template v-if="form.ai_provider === 'volces'">
          <el-form-item label="API Key">
            <el-input
              v-model="form.volces_api_key"
              type="password"
              show-password
              placeholder="输入新的 API Key（留空则保持现有配置）"
              clearable
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ currentSettings.volces_has_key ? '当前已配置' : '当前未配置' }}
            </div>
          </el-form-item>
          <el-form-item label="Endpoint ID (模型接入点)">
            <el-input
              v-model="form.volces_ep_id"
              :placeholder="currentSettings.volces_ep_id || '例如 ep-2025xxxx-xxxxx'"
              clearable
            />
          </el-form-item>
        </template>

        <!-- ModelScope fields -->
        <template v-if="form.ai_provider === 'modelscope'">
          <el-form-item label="API Key">
            <el-input
              v-model="form.modelscope_api_key"
              type="password"
              show-password
              placeholder="输入新的 API Key（留空则保持现有配置）"
              clearable
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ currentSettings.modelscope_has_key ? '当前已配置' : '当前未配置' }}
            </div>
          </el-form-item>
          <el-form-item label="模型">
            <el-select
              v-model="form.modelscope_model"
              style="width: 100%;"
              allow-create
              filterable
              placeholder="选择或输入模型名称"
            >
              <el-option
                v-for="m in MODEL_SCOPE_MODELS"
                :key="m.value"
                :label="m.label"
                :value="m.value"
              />
            </el-select>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              ModelScope 免费额度每天 2000 次调用
            </div>
          </el-form-item>
        </template>

        <el-divider />

        <div style="display: flex; gap: 12px;">
          <el-button type="primary" :loading="saving" @click="handleSave">保存设置</el-button>
          <el-button :loading="testing" @click="handleTest">测试连接</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProviderSettings, saveProviderSettings, testProviderConnection } from '@/api'
import type { ProviderSettingsResponse } from '@/types'

const MODEL_SCOPE_MODELS = [
  { label: 'Kimi-K2.6（推荐，支持思考）', value: 'moonshotai/Kimi-K2.6:DashScope' },
  { label: 'Qwen3-VL-235B-A22B-Instruct', value: 'Qwen/Qwen3-VL-235B-A22B-Instruct' },
]

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const currentSettings = reactive<ProviderSettingsResponse>({
  ai_provider: 'volces',
  volces_has_key: false,
  volces_ep_id: '',
  modelscope_has_key: false,
  modelscope_model: 'moonshotai/Kimi-K2.6',
})

const form = reactive({
  ai_provider: 'volces',
  volces_api_key: '',
  volces_ep_id: '',
  modelscope_api_key: '',
  modelscope_model: 'moonshotai/Kimi-K2.6',
})

onMounted(() => loadSettings())

async function loadSettings() {
  loading.value = true
  try {
    const s = await getProviderSettings()
    Object.assign(currentSettings, s)
    form.ai_provider = s.ai_provider
    form.volces_ep_id = s.volces_ep_id
    form.modelscope_model = s.modelscope_model
  } catch {
    ElMessage.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const payload: Record<string, string> = { ai_provider: form.ai_provider }
    if (form.volces_api_key) payload.volces_api_key = form.volces_api_key
    if (form.volces_ep_id) payload.volces_ep_id = form.volces_ep_id
    if (form.modelscope_api_key) payload.modelscope_api_key = form.modelscope_api_key
    if (form.modelscope_model) payload.modelscope_model = form.modelscope_model

    const result = await saveProviderSettings(payload as any)
    Object.assign(currentSettings, result)
    form.volces_api_key = ''
    form.modelscope_api_key = ''
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    const payload: Record<string, string> = { ai_provider: form.ai_provider }
    if (form.volces_api_key) payload.volces_api_key = form.volces_api_key
    if (form.volces_ep_id) payload.volces_ep_id = form.volces_ep_id
    if (form.modelscope_api_key) payload.modelscope_api_key = form.modelscope_api_key
    if (form.modelscope_model) payload.modelscope_model = form.modelscope_model

    const result = await testProviderConnection(payload as any)
    if (result.success) {
      ElMessage.success(result.message)
    } else {
      ElMessage.error(result.message)
    }
  } catch {
    ElMessage.error('测试连接失败')
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.settings-card {
  margin-top: 20px;
  max-width: 600px;
}
</style>
