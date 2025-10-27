<template>
  <div class="app-container" :class="`theme-${currentTheme}`" @keydown="handleGlobalKeyDown">
    <HeaderBar 
      :theme="currentTheme"
      :hasResults="polishResults.length > 0"
      @theme-change="handleThemeChange"
      @export="handleExport"
      @settings="showSettings = true"
      @accept-all="handleAcceptAll"
    />
    <div class="main-content">
      <EditorPanel 
        ref="editorRef"
        :theme="currentTheme"
        @polish="handlePolish"
        @predict="handlePredict"
        @user-input="handleUserInput"
        @line-deleted="handleLineDeleted"
      />
      <PolishResultPanel
        :results="polishResults"
        :currentResultIndex="currentResultIndex"
        :theme="currentTheme"
        @accept="handleAccept"
        @reject="handleReject"
        @accept-all="handleAcceptAll"
      />
    </div>
    <StatusBar 
      :message="statusMessage"
      :theme="currentTheme"
    />
    
    <!-- 设置对话框 -->
    <SettingsDialog
      :show="showSettings"
      @close="showSettings = false"
      @applied="handleSettingsApplied"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useThemeStore } from './stores/theme'
import { usePolishStore } from './stores/polish'
import { useSettingsStore } from './stores/settings'
import HeaderBar from './components/HeaderBar.vue'
import EditorPanel from './components/EditorPanel.vue'
import PolishResultPanel from './components/PolishResultPanel.vue'
import StatusBar from './components/StatusBar.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import api from './api/client'

const themeStore = useThemeStore()
const polishStore = usePolishStore()
const settingsStore = useSettingsStore()

const editorRef = ref(null)
const currentTheme = ref('dark')
const polishResults = ref([])
const currentResultIndex = ref(0)
const statusMessage = ref('')
const statusMessageTimer = ref(null)
const showSettings = ref(false)

onMounted(() => {
  // 从localStorage加载主题
  const savedTheme = localStorage.getItem('theme') || 'dark'
  currentTheme.value = savedTheme
  themeStore.setTheme(savedTheme)
  
  // 连接WebSocket
  api.ws.connect()
  
  // 监听WebSocket消息
  api.ws.on('polish_result', handlePolishResult)
  api.ws.on('predict_result', handlePredictResult)
  api.ws.on('status', handleStatusUpdate)
  
  // 添加全局键盘事件监听
  document.addEventListener('keydown', handleGlobalKeyDown)
})

onUnmounted(() => {
  // 清理事件监听
  document.removeEventListener('keydown', handleGlobalKeyDown)
})

function setStatusMessage(message, duration = 3000) {
  statusMessage.value = message
  
  if (statusMessageTimer.value) {
    clearTimeout(statusMessageTimer.value)
  }
  
  if (duration > 0) {
    statusMessageTimer.value = setTimeout(() => {
      statusMessage.value = ''
    }, duration)
  }
}

function handleStatusUpdate(data) {
  setStatusMessage(data.message, 2000)
}

function handlePolishResult(data) {
  if (data.success) {
    polishResults.value.push({
      original_text: data.original_text,
      polished_text: data.polished_text,
      line_number: data.line_number,
      is_prediction: false
    })
    setStatusMessage('润色完成，按TAB键确认，按~键拒绝', 3000)
  } else {
    setStatusMessage(`润色失败: ${data.error}`, 5000)
  }
}

function handlePredictResult(data) {
  if (data.success && data.predictions) {
    const currentLineCount = editorRef.value?.content?.split('\n').length || 0
    
    data.predictions.forEach((text, index) => {
      polishResults.value.push({
        original_text: '',
        polished_text: text,
        line_number: currentLineCount + index,
        is_prediction: true
      })
    })
    setStatusMessage(`剧情预测完成，生成${data.predictions.length}行内容`, 3000)
  } else if (!data.success) {
    setStatusMessage(`预测失败: ${data.error}`, 5000)
  }
}

const handleThemeChange = (theme) => {
  currentTheme.value = theme
  themeStore.setTheme(theme)
  localStorage.setItem('theme', theme)
}

const handlePolish = async (data) => {
  try {
    statusMessage.value = '正在润色...'
    
    // 获取用户选择的风格提示词
    const settings = settingsStore.getSettings()
    const selectedStyles = settings.selectedStyles || []
    const customStyles = settings.customStyles || []
    
    // 构建组合提示词
    let stylePrompt = ''
    if (selectedStyles.length > 0) {
      // 从后端获取预设风格
      const response = await fetch('http://localhost:8000/api/preset-styles')
      const stylesResult = await response.json()
      
      if (stylesResult.success) {
        const allStyles = [...stylesResult.styles, ...customStyles]
        const selectedPrompts = allStyles
          .filter(s => selectedStyles.includes(s.id))
          .map(s => s.prompt)
        stylePrompt = selectedPrompts.join('\n\n---\n\n')
      }
    }
    
    // 添加风格提示词到请求数据
    const polishData = {
      ...data,
      stylePrompt: stylePrompt
    }
    
    const result = await polishStore.polish(polishData)
    
    if (result.success) {
      polishResults.value.push(result)
      statusMessage.value = '润色完成，按TAB键确认，按~键拒绝'
    } else {
      statusMessage.value = `润色失败: ${result.error}`
    }
  } catch (error) {
    statusMessage.value = `错误: ${error.message}`
  }
}

const handlePredict = async (fullText) => {
  // 验证输入内容不为空
  if (!fullText || !fullText.trim()) {
    return
  }
  
  try {
    statusMessage.value = '正在预测剧情...'
    
    // 获取用户选择的风格提示词
    const settings = settingsStore.getSettings()
    const selectedStyles = settings.selectedStyles || []
    const customStyles = settings.customStyles || []
    
    // 构建组合提示词
    let stylePrompt = ''
    if (selectedStyles.length > 0) {
      // 从后端获取预设风格
      const response = await fetch('http://localhost:8000/api/preset-styles')
      const stylesResult = await response.json()
      
      if (stylesResult.success) {
        const allStyles = [...stylesResult.styles, ...customStyles]
        const selectedPrompts = allStyles
          .filter(s => selectedStyles.includes(s.id))
          .map(s => s.prompt)
        stylePrompt = selectedPrompts.join('\n\n---\n\n')
      }
    }
    
    // 调用预测接口，传递风格提示词
    const result = await polishStore.predict({
      full_text: fullText,
      style_prompt: stylePrompt
    })
    
    if (result.success) {
      result.predictions.forEach((text, index) => {
        polishResults.value.push({
          original_text: '',
          polished_text: text,
          is_prediction: true,
          line_number: -1
        })
      })
      statusMessage.value = `剧情预测完成，生成${result.predictions.length}行内容`
    } else {
      // 如果错误是由于内容为空，不显示错误信息
      if (result.error && !result.error.includes('内容为空')) {
        statusMessage.value = `预测失败: ${result.error}`
      }
    }
  } catch (error) {
    statusMessage.value = `错误: ${error.message}`
  }
}

// 处理用户手动输入，清除未确认的预测结果
const handleUserInput = () => {
  // 移除所有未确认的预测结果
  const beforeCount = polishResults.value.length
  polishResults.value = polishResults.value.filter(result => !result.is_prediction)
  const removedCount = beforeCount - polishResults.value.length
  
  if (removedCount > 0) {
    setStatusMessage(`已自动清除${removedCount}条未确认的预测内容`, 2000)
  }
}

// 处理行删除事件，同步删除对应的润色结果
const handleLineDeleted = (deletedLineNumbers) => {
  const beforeCount = polishResults.value.length
  
  // 删除对应行号的润色结果（非预测内容）
  polishResults.value = polishResults.value.filter(result => {
    // 预测内容不受影响
    if (result.is_prediction) {
      return true
    }
    // 检查是否在被删除的行号列表中
    return !deletedLineNumbers.includes(result.line_number)
  })
  
  // 更新剩余润色结果的行号（大于被删除行号的需要减1）
  deletedLineNumbers.sort((a, b) => b - a) // 从大到小排序
  deletedLineNumbers.forEach(deletedLine => {
    polishResults.value.forEach(result => {
      if (!result.is_prediction && result.line_number > deletedLine) {
        result.line_number--
      }
    })
  })
  
  const removedCount = beforeCount - polishResults.value.length
  if (removedCount > 0) {
    setStatusMessage(`已删除${removedCount}条对应的润色结果`, 2000)
  }
}

const handleAccept = (index) => {
  const result = polishResults.value[index]
  
  if (!editorRef.value) return
  
  // 插入或替换文本
  if (result.is_prediction) {
    // 预测内容：追加到末尾
    editorRef.value.insertText(result.polished_text)
  } else {
    // 润色内容：替换指定行
    editorRef.value.insertText(result.polished_text, result.line_number)
  }
  
  polishResults.value.splice(index, 1)
  setStatusMessage('已接受润色结果', 2000)
}

// 一键接受所有润色结果
const handleAcceptAll = () => {
  if (polishResults.value.length === 0) {
    return
  }
  
  if (!editorRef.value) return
  
  const count = polishResults.value.length
  
  // 按顺序处理所有结果
  // 先处理润色结果（替换），再处理预测结果（追加）
  const polishItems = polishResults.value.filter(r => !r.is_prediction)
  const predictionItems = polishResults.value.filter(r => r.is_prediction)
  
  // 处理润色结果 - 按行号从大到小排序，避免行号变化影响
  polishItems.sort((a, b) => b.line_number - a.line_number)
  polishItems.forEach(result => {
    editorRef.value.insertText(result.polished_text, result.line_number)
  })
  
  // 处理预测结果 - 按原顺序追加
  predictionItems.forEach(result => {
    editorRef.value.insertText(result.polished_text)
  })
  
  // 清空所有结果
  polishResults.value = []
  
  setStatusMessage(`已接受所有${count}条润色结果`, 2000)
}

const handleReject = (index) => {
  polishResults.value.splice(index, 1)
  setStatusMessage('已拒绝润色结果', 2000)
}

const handleExport = () => {
  if (!editorRef.value?.content) {
    setStatusMessage('没有可导出的内容', 2000)
    return
  }
  
  const text = editorRef.value.content
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `novel_text_${new Date().getTime()}.txt`
  link.click()
  URL.revokeObjectURL(url)
  
  setStatusMessage('文本已导出', 2000)
}

// 全局键盘事件处理
function handleGlobalKeyDown(event) {
  // Tab 键：接受当前润色结果
  if (event.key === 'Tab' && polishResults.value.length > 0) {
    event.preventDefault()
    handleAccept(currentResultIndex.value)
  }
  
  // ` 键（反引号）：拒绝当前润色结果
  if (event.key === '`' && polishResults.value.length > 0) {
    event.preventDefault()
    handleReject(currentResultIndex.value)
  }
  
  // 上下箭头键：切换当前润色结果
  if (event.key === 'ArrowDown' && polishResults.value.length > 0) {
    event.preventDefault()
    currentResultIndex.value = Math.min(currentResultIndex.value + 1, polishResults.value.length - 1)
  }
  
  if (event.key === 'ArrowUp' && polishResults.value.length > 0) {
    event.preventDefault()
    currentResultIndex.value = Math.max(currentResultIndex.value - 1, 0)
  }
}

// 设置应用后的回调
function handleSettingsApplied() {
  setStatusMessage('设置已应用', 2000)
}
</script>

<style scoped>
.app-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 0;
  overflow: hidden;
}

/* 主题变量在全局样式中定义 */
</style>
