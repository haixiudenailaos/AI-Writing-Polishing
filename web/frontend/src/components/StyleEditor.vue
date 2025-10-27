<template>
  <div class="editor-overlay" @click.self="close">
    <div class="editor-dialog">
      <div class="editor-header">
        <h3>{{ isEdit ? '编辑风格' : '新建风格' }}</h3>
        <button class="close-btn" @click="close">×</button>
      </div>

      <div class="editor-body">
        <div class="form-group">
          <label>风格名称 *</label>
          <input 
            v-model="formData.name"
            type="text"
            placeholder="输入风格名称"
            class="form-input"
          />
        </div>

        <div class="form-group">
          <label>风格提示 *</label>
          <div class="prompt-header">
            <button 
              class="btn-optimize" 
              @click="optimizePrompt"
              :disabled="optimizing || !formData.prompt.trim()"
              title="使用AI优化提示词，使其更加具体和有效"
            >
              <span v-if="optimizing">🤖 优化中...</span>
              <span v-else>✨ AI优化</span>
            </button>
          </div>
          <textarea
            v-model="formData.prompt"
            placeholder="输入风格提示词，描述这种风格的特点"
            class="form-textarea"
            rows="6"
          ></textarea>
          <div v-if="optimizeError" class="error-message">
            {{ optimizeError }}
          </div>
        </div>

        <div class="form-group">
          <label>风格说明</label>
          <textarea
            v-model="formData.description"
            placeholder="简要说明这个风格的用途（可选）"
            class="form-textarea"
            rows="3"
          ></textarea>
        </div>
      </div>

      <div class="editor-footer">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" @click="save">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  style: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['save', 'close'])

const formData = ref({
  id: '',
  name: '',
  prompt: '',
  description: ''
})

const optimizing = ref(false)
const optimizeError = ref('')

const isEdit = computed(() => !!props.style)

onMounted(() => {
  if (props.style) {
    formData.value = { ...props.style }
  } else {
    formData.value.id = 'custom_' + Date.now()
  }
})

function save() {
  if (!formData.value.name || !formData.value.prompt) {
    alert('请填写风格名称和提示词')
    return
  }

  emit('save', { ...formData.value })
}

function close() {
  emit('close')
}

async function optimizePrompt() {
  if (!formData.value.prompt.trim()) {
    optimizeError.value = '请先输入提示词内容'
    return
  }
  
  optimizing.value = true
  optimizeError.value = ''
  
  try {
    const response = await fetch('http://localhost:8000/api/optimize-prompt', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        original_prompt: formData.value.prompt,
        context: formData.value.description || null
      })
    })
    
    const result = await response.json()
    
    if (result.success && result.optimized_prompt) {
      formData.value.prompt = result.optimized_prompt
    } else {
      optimizeError.value = result.error || '优化失败，请稍后重试'
    }
  } catch (error) {
    console.error('优化提示词失败:', error)
    optimizeError.value = '网络请求失败，请检查后端服务是否启动'
  } finally {
    optimizing.value = false
  }
}
</script>

<style scoped>
.editor-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.editor-dialog {
  background-color: var(--editor-background);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  width: 90%;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--title-bar-background);
}

.editor-header h3 {
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

.editor-body {
  padding: 16px;
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

.prompt-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 6px;
}

.btn-optimize {
  padding: 6px 12px;
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  border: none;
  border-radius: 4px;
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.btn-optimize:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.btn-optimize:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  margin-top: 6px;
  padding: 8px;
  background-color: rgba(244, 135, 113, 0.1);
  border: 1px solid rgba(244, 135, 113, 0.3);
  border-radius: 3px;
  color: #f48771;
  font-size: 12px;
}

.form-input,
.form-textarea {
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
.form-textarea:focus {
  outline: none;
  border-color: var(--focus-border);
}

.form-textarea {
  resize: vertical;
}

.editor-footer {
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
