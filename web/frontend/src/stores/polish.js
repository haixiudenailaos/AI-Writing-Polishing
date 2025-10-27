import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/client'

export const usePolishStore = defineStore('polish', () => {
  const polishHistory = ref([])
  const isPolishing = ref(false)
  const isPredicting = ref(false)
  
  async function polish(data) {
    isPolishing.value = true
    try {
      const result = await api.polish({
        context_lines: data.contextLines || [],
        target_line: data.targetLine,
        line_number: data.lineNumber,
        style_prompt: data.stylePrompt || ''
      })
      
      if (result.success) {
        polishHistory.value.push(result)
      }
      
      return result
    } catch (error) {
      console.error('润色失败:', error)
      throw error
    } finally {
      isPolishing.value = false
    }
  }
  
  async function predict(data) {
    isPredicting.value = true
    try {
      const result = await api.predict({
        full_text: typeof data === 'string' ? data : data.full_text,
        style_prompt: typeof data === 'object' ? data.style_prompt : ''
      })
      
      return result
    } catch (error) {
      console.error('预测失败:', error)
      throw error
    } finally {
      isPredicting.value = false
    }
  }
  
  function clearHistory() {
    polishHistory.value = []
  }
  
  return {
    polishHistory,
    isPolishing,
    isPredicting,
    polish,
    predict,
    clearHistory
  }
})
