<template>
  <div class="header-bar">
    <div class="header-left">
      <h1 class="title">字见润新</h1>
      <select 
        class="theme-selector"
        :value="theme"
        @change="$emit('theme-change', $event.target.value)"
      >
        <option value="dark">暗色</option>
        <option value="light">亮色</option>
        <option value="teal">暗青色</option>
        <option value="eyeCare">护眼</option>
      </select>
    </div>
    <div class="header-right">
      <button @click="$emit('accept-all')" :disabled="!hasResults" title="接受所有润色结果">一键接受</button>
      <button @click="$emit('settings')">设置</button>
      <button @click="$emit('export')">导出文本</button>
      <button @click="showAbout = true">关于</button>
    </div>
    
    <!-- 关于对话框 -->
    <div v-if="showAbout" class="modal-overlay" @click="showAbout = false">
      <div class="modal-content" @click.stop>
        <h2>关于</h2>
        <p>字见润新Web应用 v1.0.0</p>
        <p>基于AI的智能文本润色工具</p>
        <p>VSCode风格界面设计</p>
        <button @click="showAbout = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  theme: {
    type: String,
    default: 'dark'
  },
  hasResults: {
    type: Boolean,
    default: false
  }
})

defineEmits(['theme-change', 'export', 'settings', 'accept-all'])

const showAbout = ref(false)
</script>

<style scoped>
.header-bar {
  height: 44px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  background-color: var(--title-bar-background);
  color: var(--title-bar-foreground);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.theme-selector {
  min-width: 120px;
}

.header-right {
  display: flex;
  gap: 8px;
}

.modal-overlay {
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

.modal-content {
  background-color: var(--panel-background);
  color: var(--foreground);
  padding: 24px;
  border-radius: 4px;
  min-width: 300px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.modal-content h2 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 18px;
}

.modal-content p {
  margin: 8px 0;
  font-size: 14px;
}

.modal-content button {
  margin-top: 16px;
  width: 100%;
}
</style>
