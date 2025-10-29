<template>
  <div v-if="show" class="settings-overlay" @click.self="close">
    <div class="settings-dialog">
      <!-- 标题栏 -->
      <div class="settings-header">
        <h2>设置</h2>
        <button class="close-btn" @click="close">×</button>
      </div>

      <!-- 主体内容 -->
      <div class="settings-body">
        <!-- 侧边栏 -->
        <div class="settings-sidebar">
          <div 
            class="sidebar-item"
            :class="{ active: currentTab === 'api' }"
            @click="currentTab = 'api'"
          >
            API 配置
          </div>
          <div 
            class="sidebar-item"
            :class="{ active: currentTab === 'styles' }"
            @click="currentTab = 'styles'"
          >
            润色风格
          </div>
          <div 
            class="sidebar-item"
            :class="{ active: currentTab === 'advanced' }"
            @click="currentTab = 'advanced'"
          >
            高级设置
          </div>
        </div>

        <!-- 内容面板 -->
        <div class="settings-content">
          <!-- API配置面板 -->
          <div v-show="currentTab === 'api'" class="settings-panel">
            <h3 class="panel-title">API 配置</h3>
            
            <!-- 提醒信息 -->
            <div class="info-box">
              <div class="info-icon">ℹ️</div>
              <div class="info-content">
                <strong>提示：</strong>本应用已内置免费AI服务，无需配置API密钥即可使用。
              </div>
            </div>
            
            <div class="form-group">
              <label>API 密钥</label>
              <div class="input-with-button">
                <input 
                  v-model="formData.apiKey"
                  :type="showApiKey ? 'text' : 'password'"
                  placeholder="sk-..."
                  class="form-input"
                />
                <button 
                  class="toggle-btn"
                  @click="showApiKey = !showApiKey"
                >
                  {{ showApiKey ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>

            <div class="form-group">
              <label>基础 URL</label>
              <input 
                v-model="formData.baseUrl"
                type="text"
                placeholder="https://api.example.com/v1/chat/completions"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label>模型</label>
              <select 
                v-model="formData.model"
                class="form-select"
                title="选择AI模型"
              >
                <option value="deepseek-ai/DeepSeek-V3.2-Exp">DeepSeek-V3.2-Exp</option>
                <option value="deepseek-ai/DeepSeek-V3">DeepSeek-V3</option>
              </select>
              <p class="model-note">💡 当前仅支持 <strong>DeepSeek-V3.2-Exp</strong> 和 <strong>DeepSeek-V3</strong> 模型</p>
            </div>

            <div class="form-group">
              <button class="test-btn" @click="testConnection" :disabled="testing">
                {{ testing ? '测试中...' : '测试连接' }}
              </button>
              <span v-if="testResult" :class="['test-result', testResult.success ? 'success' : 'error']">
                {{ testResult.message }}
              </span>
            </div>
          </div>

          <!-- 润色风格面板 -->
          <div v-show="currentTab === 'styles'" class="settings-panel">
            <h3 class="panel-title">润色风格</h3>
            
            <div class="form-group">
              <label>预设风格</label>
              <div class="styles-list">
                <div 
                  v-for="style in presetStyles" 
                  :key="style.id"
                  class="style-item"
                >
                  <label class="style-checkbox">
                    <input 
                      type="checkbox"
                      :value="style.id"
                      v-model="formData.selectedStyles"
                    />
                    <span>{{ style.name }}</span>
                  </label>
                  <div class="style-prompt">{{ style.prompt }}</div>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label>自定义风格</label>
              <div class="styles-list">
                <div 
                  v-for="style in customStyles" 
                  :key="style.id"
                  class="style-item custom"
                >
                  <label class="style-checkbox">
                    <input 
                      type="checkbox"
                      :value="style.id"
                      v-model="formData.selectedStyles"
                    />
                    <span>{{ style.name }}</span>
                  </label>
                  <div class="style-actions">
                    <button class="edit-btn" @click="editStyle(style)">编辑</button>
                    <button class="delete-btn" @click="deleteStyle(style.id)">删除</button>
                  </div>
                  <div class="style-prompt">{{ style.prompt }}</div>
                </div>
              </div>
              <button class="add-style-btn" @click="showStyleEditor = true">
                新建自定义风格
              </button>
            </div>

            <div class="form-group">
              <label>风格预览</label>
              <div class="style-preview">
                {{ combinedStylePrompt || '未选择风格' }}
              </div>
            </div>
          </div>

          <!-- 高级设置面板 -->
          <div v-show="currentTab === 'advanced'" class="settings-panel">
            <h3 class="panel-title">高级设置</h3>
            
            <div class="form-group">
              <label>配置管理</label>
              <div class="button-group">
                <button class="action-btn" @click="exportConfig">导出配置</button>
                <button class="action-btn" @click="importConfig">导入配置</button>
                <input 
                  ref="importFileInput" 
                  type="file" 
                  accept=".json"
                  style="display: none"
                  @change="handleImportFile"
                />
              </div>
            </div>

            <div class="form-group">
              <label>重置设置</label>
              <p class="warning-text">⚠️ 此操作将删除所有自定义配置，包括API密钥和自定义风格。</p>
              <button class="reset-btn" @click="resetSettings">重置所有设置</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="settings-footer">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" @click="apply">应用</button>
        <button class="btn btn-primary" @click="save">保存</button>
      </div>
    </div>
  </div>

  <!-- 风格编辑器 -->
  <StyleEditor
    v-if="showStyleEditor"
    :style="editingStyle"
    @save="saveStyle"
    @close="closeStyleEditor"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import StyleEditor from './StyleEditor.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'applied'])

const settingsStore = useSettingsStore()

// 表单数据
const formData = ref({
  apiKey: '',
  baseUrl: '',
  model: '',
  selectedStyles: []
})

// UI状态
const currentTab = ref('api')
const showApiKey = ref(false)
const testing = ref(false)
const testResult = ref(null)
const showStyleEditor = ref(false)
const editingStyle = ref(null)
const importFileInput = ref(null)

// 预设风格（从后端加载）
const presetStyles = ref([])

// 自定义风格
const customStyles = ref([])

// 组合风格提示
const combinedStylePrompt = computed(() => {
  const selected = [...presetStyles.value, ...customStyles.value]
    .filter(s => formData.value.selectedStyles.includes(s.id))
    .map(s => s.prompt)
  return selected.join('\n\n---\n\n')
})

// 加载预设风格
async function loadPresetStyles() {
  try {
    const response = await fetch('http://localhost:8000/api/preset-styles')
    const result = await response.json()
    if (result.success) {
      presetStyles.value = result.styles
    }
  } catch (error) {
    console.error('加载预设风格失败:', error)
    // 使用默认风格
    presetStyles.value = [
      {
        id: 'professional_screenwriter',
        name: '专业编剧',
        prompt: '请使用专业的戏剧性润色，增强情节的戏剧冲突和悬念',
        is_preset: true
      }
    ]
  }
}

// 初始化
onMounted(async () => {
  await loadPresetStyles()
  loadSettings()
})

// 监听显示状态
watch(() => props.show, (newVal) => {
  if (newVal) {
    loadSettings()
  }
})

// 加载设置
function loadSettings() {
  const settings = settingsStore.getSettings()
  formData.value = {
    apiKey: settings.apiKey || '',
    baseUrl: settings.baseUrl || 'https://api.siliconflow.cn/v1/chat/completions',
    model: settings.model || 'deepseek-ai/DeepSeek-V3.2-Exp', // 默认为 DeepSeek-V3.2-Exp
    selectedStyles: settings.selectedStyles || []
  }
  customStyles.value = settings.customStyles || []
}

// 测试连接
async function testConnection() {
  if (!formData.value.apiKey) {
    testResult.value = { success: false, message: '提示：无需配置API密钥，内置服务可直接使用' }
    return
  }

  testing.value = true
  testResult.value = null

  try {
    const response = await fetch('http://localhost:8000/api/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: formData.value.apiKey,
        base_url: formData.value.baseUrl,
        model: formData.value.model // 使用选择的模型
      })
    })

    const result = await response.json()
    testResult.value = result
  } catch (error) {
    testResult.value = { success: false, message: '测试失败: ' + error.message }
  } finally {
    testing.value = false
  }
}

// 编辑风格
function editStyle(style) {
  editingStyle.value = { ...style }
  showStyleEditor.value = true
}

// 删除风格
function deleteStyle(styleId) {
  if (confirm('确定要删除这个自定义风格吗？')) {
    customStyles.value = customStyles.value.filter(s => s.id !== styleId)
    formData.value.selectedStyles = formData.value.selectedStyles.filter(id => id !== styleId)
  }
}

// 保存风格
function saveStyle(style) {
  if (editingStyle.value) {
    // 更新
    const index = customStyles.value.findIndex(s => s.id === editingStyle.value.id)
    if (index >= 0) {
      customStyles.value[index] = style
    }
  } else {
    // 新建
    customStyles.value.push(style)
  }
  closeStyleEditor()
}

// 关闭风格编辑器
function closeStyleEditor() {
  showStyleEditor.value = false
  editingStyle.value = null
}

// 导出配置
function exportConfig() {
  const config = {
    ...formData.value,
    customStyles: customStyles.value
  }
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `novel-polish-config-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 导入配置
function importConfig() {
  importFileInput.value.click()
}

// 处理导入文件
function handleImportFile(event) {
  const file = event.target.files[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const config = JSON.parse(e.target.result)
      formData.value = {
        apiKey: config.apiKey || '',
        baseUrl: config.baseUrl || '',
        model: config.model || '',
        selectedStyles: config.selectedStyles || []
      }
      customStyles.value = config.customStyles || []
      alert('配置导入成功！')
    } catch (error) {
      alert('配置文件格式错误：' + error.message)
    }
  }
  reader.readAsText(file)
}

// 重置设置
function resetSettings() {
  if (confirm('此操作将删除所有配置，确定继续吗？')) {
    formData.value = {
      apiKey: '',
      baseUrl: 'https://api.siliconflow.cn/v1/chat/completions',
      model: 'deepseek-ai/DeepSeek-V3.2-Exp', // 重置时使用默认模型
      selectedStyles: []
    }
    customStyles.value = []
    alert('设置已重置！')
  }
}

// 应用设置
function apply() {
  settingsStore.updateSettings({
    ...formData.value,
    customStyles: customStyles.value
  })
  emit('applied')
  alert('设置已应用！')
}

// 保存并关闭
function save() {
  apply()
  close()
}

// 关闭对话框
function close() {
  emit('close')
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.settings-dialog {
  background-color: var(--editor-background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  width: 90%;
  max-width: 800px;
  height: 80%;
  max-height: 600px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--title-bar-background);
}

.settings-header h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--title-bar-foreground);
}

.close-btn {
  background: none;
  border: none;
  color: var(--foreground);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
}

.close-btn:hover {
  background-color: var(--button-hover-background);
}

.settings-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.settings-sidebar {
  width: 160px;
  background-color: var(--panel-background);
  border-right: 1px solid var(--border-color);
  padding: 8px 0;
}

.sidebar-item {
  padding: 8px 16px;
  cursor: pointer;
  color: var(--foreground);
  font-size: 13px;
  transition: all 0.2s;
}

.sidebar-item:hover {
  background-color: var(--input-background);
}

.sidebar-item.active {
  background-color: var(--selection);
  border-left: 2px solid var(--accent);
  color: var(--accent);
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.settings-panel {
  max-width: 600px;
}

.panel-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--foreground);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--foreground);
  font-weight: 500;
}

.form-input,
.form-select {
  width: 100%;
  padding: 8px 10px;
  background-color: var(--input-background);
  border: 1px solid var(--input-border);
  border-radius: 3px;
  color: var(--input-foreground);
  font-size: 13px;
  font-family: inherit;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--focus-border);
  box-shadow: 0 0 0 2px rgba(75, 166, 223, 0.2);
}

.form-select {
  cursor: pointer;
  padding-right: 32px;
  background-image: linear-gradient(45deg, transparent 50%, var(--input-foreground) 50%),
                    linear-gradient(135deg, var(--input-foreground) 50%, transparent 50%);
  background-position: calc(100% - 14px) calc(50% - 2px),
                       calc(100% - 9px) calc(50% - 2px);
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}

.form-select:hover {
  border-color: var(--focus-border);
  background-color: var(--button-hover-background);
}

.form-select option {
  background-color: var(--input-background);
  color: var(--input-foreground);
  padding: 8px 12px;
}

.input-with-button {
  display: flex;
  gap: 8px;
}

.input-with-button .form-input {
  flex: 1;
}

.toggle-btn,
.test-btn,
.action-btn,
.edit-btn,
.delete-btn,
.add-style-btn,
.reset-btn {
  padding: 8px 16px;
  background-color: var(--button-background);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  color: var(--button-foreground);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover,
.test-btn:hover,
.action-btn:hover,
.edit-btn:hover {
  background-color: var(--button-hover-background);
}

.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-result {
  margin-left: 12px;
  font-size: 13px;
}

.test-result.success {
  color: #4ec9b0;
}

.test-result.error {
  color: #f48771;
}

.styles-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 8px;
}

.style-item {
  padding: 8px;
  margin-bottom: 8px;
  background-color: var(--input-background);
  border-radius: 3px;
}

.style-item.custom {
  border-left: 2px solid var(--accent);
}

.style-checkbox {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 13px;
  color: var(--foreground);
}

.style-checkbox input {
  margin-right: 8px;
}

.style-prompt {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted-foreground);
  padding-left: 24px;
}

.style-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.delete-btn {
  background-color: var(--original-background);
}

.delete-btn:hover {
  background-color: #f48771;
}

.add-style-btn {
  width: 100%;
  margin-top: 8px;
  background-color: var(--accent);
  color: #ffffff;
}

.style-preview {
  padding: 12px;
  background-color: var(--input-background);
  border: 1px solid var(--input-border);
  border-radius: 3px;
  font-size: 13px;
  color: var(--foreground);
  min-height: 60px;
  line-height: 1.6;
}

.button-group {
  display: flex;
  gap: 8px;
}

.warning-text {
  color: #ce9178;
  font-size: 12px;
  margin: 8px 0;
}

.info-box {
  display: flex;
  gap: 12px;
  padding: 12px;
  background-color: rgba(75, 166, 223, 0.1);
  border: 1px solid rgba(75, 166, 223, 0.3);
  border-radius: 4px;
  margin-bottom: 16px;
}

.info-icon {
  font-size: 20px;
  line-height: 1;
}

.info-content {
  flex: 1;
  font-size: 13px;
  color: var(--foreground);
  line-height: 1.5;
}

.info-content strong {
  color: #4ba6df;
}

.model-note {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted-foreground);
}

.model-note strong {
  color: #4ba6df;
}

.reset-btn {
  background-color: var(--original-background);
  color: #ffffff;
}

.reset-btn:hover {
  background-color: #f48771;
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  background-color: var(--panel-background);
}

.btn {
  padding: 8px 20px;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary {
  background-color: var(--button-background);
  color: var(--button-foreground);
}

.btn-secondary:hover {
  background-color: var(--button-hover-background);
}

.btn-primary {
  background-color: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}

.btn-primary:hover {
  background-color: var(--button-hover-background);
}
</style>
