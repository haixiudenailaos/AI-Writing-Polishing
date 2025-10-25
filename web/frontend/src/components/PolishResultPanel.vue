<template>
  <div class="polish-result-panel">
    <div class="panel-header">
      <h3>润色结果</h3>
      <button 
        v-if="results.length > 0"
        @click="acceptAll"
        class="accept-all-btn"
        title="接受所有润色结果"
      >
        一键接受 ({{ results.length }})
      </button>
    </div>
    
    <div class="results-list">
      <div 
        v-if="results.length === 0"
        class="empty-state"
      >
        <p>暂无润色结果</p>
        <p class="hint">按 Enter 键开始润色</p>
      </div>
      
      <div 
        v-for="(result, index) in results"
        :key="index"
        class="result-line"
        :class="{ 
          'is-prediction': result.is_prediction,
          'is-active': index === currentResultIndex
        }"
      >
        <div class="line-prefix">
          <span v-if="result.is_prediction" class="prediction-tag">[预测]</span>
          <span v-else class="line-tag">[{{ result.line_number + 1 }}]</span>
        </div>
        <div class="line-content">
          <div v-if="!result.is_prediction" class="original-line">
            {{ result.original_text }}
          </div>
          <div class="polished-line">
            {{ result.polished_text }}
          </div>
        </div>
        <div class="line-actions">
          <button 
            @click="acceptResult(index)"
            class="action-btn accept-btn"
            title="接受 (Tab)"
          >
            ✓
          </button>
          <button 
            @click="rejectResult(index)"
            class="action-btn reject-btn"
            title="拒绝 (`)"
          >
            ✗
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, computed } from 'vue'

const props = defineProps({
  results: {
    type: Array,
    default: () => []
  },
  theme: {
    type: String,
    default: 'dark'
  },
  currentResultIndex: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['accept', 'reject', 'accept-all'])

function acceptResult(index) {
  emit('accept', index)
}

function rejectResult(index) {
  emit('reject', index)
}

function acceptAll() {
  emit('accept-all')
}
</script>

<style scoped>
.polish-result-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--panel-background);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--foreground);
}

.accept-all-btn {
  padding: 4px 12px;
  background-color: var(--accent);
  color: #ffffff;
  border: none;
  border-radius: 3px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.accept-all-btn:hover {
  background-color: var(--button-hover-background);
  transform: translateY(-1px);
}

.accept-all-btn:active {
  transform: translateY(0);
}

.results-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted-foreground);
  text-align: center;
}

.empty-state p {
  margin: 4px 0;
}

.hint {
  font-size: 12px;
  opacity: 0.8;
}

/* 润色结果行样式 */
.result-line {
  display: flex;
  align-items: flex-start;
  padding: 6px 8px;
  margin-bottom: 2px;
  border-left: 2px solid transparent;
  transition: all 0.2s;
  font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.result-line:hover {
  background-color: var(--input-background);
  border-left-color: var(--accent);
}

.result-line.is-active {
  background-color: var(--selection);
  border-left-color: var(--accent);
}

.result-line.is-prediction {
  border-left-color: var(--focus-border);
  background-color: rgba(0, 122, 204, 0.1);
}

/* 行号前缀 */
.line-prefix {
  flex-shrink: 0;
  margin-right: 8px;
  color: var(--line-number-foreground);
  user-select: none;
}

.line-tag {
  color: var(--line-number-foreground);
  font-weight: 500;
}

.prediction-tag {
  color: var(--accent);
  font-weight: 600;
}

/* 行内容 */
.line-content {
  flex: 1;
  min-width: 0;
}

.original-line {
  color: var(--muted-foreground);
  text-decoration: line-through;
  margin-bottom: 4px;
  opacity: 0.7;
  font-size: 12px;
}

.polished-line {
  color: var(--foreground);
  word-wrap: break-word;
  white-space: pre-wrap;
}

/* 行操作按钮 */
.line-actions {
  display: flex;
  gap: 4px;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.result-line:hover .line-actions,
.result-line.is-active .line-actions {
  opacity: 1;
}

.action-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  background-color: var(--button-background);
  color: var(--button-foreground);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: var(--button-hover-background);
  border-color: var(--focus-border);
}

.accept-btn {
  color: #4ec9b0;
}

.accept-btn:hover {
  background-color: #4ec9b0;
  color: #ffffff;
}

.reject-btn {
  color: #f48771;
}

.reject-btn:hover {
  background-color: #f48771;
  color: #ffffff;
}
</style>
