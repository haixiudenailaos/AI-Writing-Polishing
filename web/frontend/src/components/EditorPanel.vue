<template>
  <div class="editor-panel">
    <div class="line-numbers">
      <div 
        v-for="(line, index) in lines"
        :key="index"
        class="line-number"
        :class="{ active: index === currentLine }"
      >
        {{ index + 1 }}
      </div>
    </div>
    <textarea
      ref="editorRef"
      v-model="content"
      class="editor-content"
      placeholder="在此输入待润色的文本，按 Enter 键提交到 AI 进行润色..."
      @keydown="handleKeyDown"
      @input="handleInput"
      @scroll="handleScroll"
    ></textarea>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
  theme: {
    type: String,
    default: 'dark'
  }
})

const emit = defineEmits(['polish', 'predict', 'userInput', 'lineDeleted'])

const content = ref('')
const editorRef = ref(null)
const currentLine = ref(0)
const inputTimer = ref(null)
const programmaticUpdate = ref(false) // 标记是否为程序化更新
const previousLines = ref([]) // 记录上一次的行内容，用于检测删除

const lines = computed(() => {
  if (!content.value) return ['']
  return content.value.split('\n')
})

watch(content, (newVal, oldVal) => {
  updateCurrentLine()
  
  // 检测行删除
  if (!programmaticUpdate.value && oldVal !== undefined) {
    const oldLines = oldVal.split('\n')
    const newLines = newVal.split('\n')
    
    // 检测是否有行被删除
    if (newLines.length < oldLines.length) {
      // 找出被删除的行号
      const deletedLineNumbers = []
      let newIndex = 0
      
      for (let oldIndex = 0; oldIndex < oldLines.length; oldIndex++) {
        if (newIndex < newLines.length && oldLines[oldIndex] === newLines[newIndex]) {
          newIndex++
        } else {
          deletedLineNumbers.push(oldIndex)
        }
      }
      
      // 通知父组件删除对应的润色结果
      if (deletedLineNumbers.length > 0) {
        emit('lineDeleted', deletedLineNumbers)
      }
    }
    
    // 只有当是用户手动输入时，才通知父组件清除预测结果
    if (newVal !== oldVal) {
      emit('userInput')
    }
  }
  
  // 重置程序化更新标记
  programmaticUpdate.value = false
  
  // 输入停止3秒后触发预测
  clearTimeout(inputTimer.value)
  
  // 只有当内容不为空时才触发预测
  if (content.value && content.value.trim()) {
    inputTimer.value = setTimeout(() => {
      emit('predict', content.value)
    }, 3000)
  }
  
  // 更新前一次的行记录
  previousLines.value = lines.value.slice()
})

function updateCurrentLine() {
  if (!editorRef.value) return
  
  const textarea = editorRef.value
  const cursorPosition = textarea.selectionStart
  const textBeforeCursor = content.value.substring(0, cursorPosition)
  currentLine.value = textBeforeCursor.split('\n').length - 1
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    // Enter键：触发润色
    event.preventDefault()
    
    const lineTexts = lines.value
    const lineNumber = currentLine.value
    
    if (lineNumber >= 0 && lineNumber < lineTexts.length) {
      const targetLine = lineTexts[lineNumber].trim()
      
      if (targetLine) {
        // 获取上下文（前5行）
        const contextLines = lineTexts.slice(Math.max(0, lineNumber - 5), lineNumber)
        
        emit('polish', {
          contextLines,
          targetLine,
          lineNumber
        })
      }
    }
    
    // 插入换行
    const textarea = editorRef.value
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const text = content.value
    content.value = text.substring(0, start) + '\n' + text.substring(end)
    
    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = start + 1
      updateCurrentLine()
    })
  } else if (event.key === 'Tab') {
    event.preventDefault()
    // Tab键由父组件处理
  }
}

function handleInput() {
  updateCurrentLine()
}

function handleScroll(event) {
  const lineNumbers = event.target.parentElement.querySelector('.line-numbers')
  if (lineNumbers) {
    lineNumbers.scrollTop = event.target.scrollTop
  }
}

function insertText(text, lineNumber = -1) {
  // 标记为程序化更新，避免触发 userInput 事件
  programmaticUpdate.value = true
  
  if (lineNumber >= 0 && lineNumber < lines.value.length) {
    // 替换指定行
    const lineTexts = [...lines.value]
    lineTexts[lineNumber] = text
    content.value = lineTexts.join('\n')
  } else {
    // 追加到末尾
    if (content.value && !content.value.endsWith('\n')) {
      content.value += '\n'
    }
    content.value += text + '\n'
  }
}

defineExpose({
  insertText,
  content
})
</script>

<style scoped>
.editor-panel {
  display: flex;
  height: 100%;
  background-color: var(--editor-background);
  border-right: 1px solid var(--border-color);
  overflow: hidden;
}

.line-numbers {
  width: 60px;
  background-color: var(--line-number-background);
  color: var(--line-number-foreground);
  padding: 8px 8px 8px 0;
  text-align: right;
  font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  user-select: none;
  overflow-y: hidden;
  flex-shrink: 0;
}

.line-number {
  height: 20.8px;
  padding-right: 8px;
}

.line-number.active {
  color: var(--accent);
  font-weight: bold;
}

.editor-content {
  flex: 1;
  background-color: var(--editor-background);
  color: var(--editor-foreground);
  border: none;
  outline: none;
  resize: none;
  padding: 8px 12px;
  font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-y: auto;
}

.editor-content::placeholder {
  color: var(--muted-foreground);
}

.editor-content::-webkit-scrollbar {
  width: 10px;
}

.editor-content::-webkit-scrollbar-track {
  background: var(--editor-background);
}

.editor-content::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 5px;
}

.editor-content::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
}
</style>
