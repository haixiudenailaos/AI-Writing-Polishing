import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref('dark')
  
  const themes = ref({
    dark: {
      label: '暗色',
      key: 'dark'
    },
    light: {
      label: '亮色',
      key: 'light'
    },
    teal: {
      label: '暗青色',
      key: 'teal'
    },
    eyeCare: {
      label: '护眼',
      key: 'eyeCare'
    }
  })
  
  function setTheme(theme) {
    if (themes.value[theme]) {
      currentTheme.value = theme
      localStorage.setItem('theme', theme)
    }
  }
  
  function getTheme() {
    return currentTheme.value
  }
  
  function getThemeList() {
    return Object.values(themes.value)
  }
  
  return {
    currentTheme,
    themes,
    setTheme,
    getTheme,
    getThemeList
  }
})
