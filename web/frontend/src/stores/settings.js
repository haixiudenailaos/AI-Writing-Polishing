import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref({
    apiKey: '',
    baseUrl: '',
    model: '',
    selectedStyles: [],
    customStyles: []
  })
  
  // 从localStorage加载设置
  function loadSettings() {
    const saved = localStorage.getItem('novel-polish-settings')
    if (saved) {
      try {
        settings.value = JSON.parse(saved)
      } catch (e) {
        console.error('Failed to load settings:', e)
      }
    }
  }
  
  // 保存设置到localStorage
  function saveSettings() {
    localStorage.setItem('novel-polish-settings', JSON.stringify(settings.value))
  }
  
  // 更新设置
  function updateSettings(newSettings) {
    settings.value = { ...settings.value, ...newSettings }
    saveSettings()
  }
  
  // 获取设置
  function getSettings() {
    return settings.value
  }
  
  // 获取API配置
  function getApiConfig() {
    return {
      apiKey: settings.value.apiKey,
      baseUrl: settings.value.baseUrl,
      model: settings.value.model
    }
  }
  
  // 获取选中的风格
  function getSelectedStyles() {
    return settings.value.selectedStyles || []
  }
  
  // 获取自定义风格
  function getCustomStyles() {
    return settings.value.customStyles || []
  }
  
  // 初始化时加载设置
  loadSettings()
  
  return {
    settings,
    loadSettings,
    saveSettings,
    updateSettings,
    getSettings,
    getApiConfig,
    getSelectedStyles,
    getCustomStyles
  }
})
