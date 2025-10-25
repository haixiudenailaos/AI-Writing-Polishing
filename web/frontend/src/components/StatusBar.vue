<template>
  <div class="status-bar">
    <div class="status-left">
      <span v-if="message" class="status-message">{{ message }}</span>
    </div>
    <div class="status-right">
      <span class="status-info">按 Enter 润色 | Tab 接受 | ~ 拒绝</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: ''
  },
  theme: {
    type: String,
    default: 'dark'
  }
})
</script>

<style scoped>
.status-bar {
  height: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  background-color: var(--title-bar-background);
  color: var(--title-bar-foreground);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  flex-shrink: 0;
}

.status-left {
  flex: 1;
}

.status-message {
  color: var(--foreground);
}

.status-right {
  display: flex;
  gap: 12px;
}

.status-info {
  color: var(--muted-foreground);
}
</style>
