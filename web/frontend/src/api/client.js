import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// WebSocket连接
let ws = null
let wsReconnectTimer = null
const wsCallbacks = new Map()

function connectWebSocket() {
  const wsUrl = API_BASE_URL.replace('http', 'ws') + '/ws/polish'
  
  try {
    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('WebSocket连接已建立')
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer)
        wsReconnectTimer = null
      }
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      const type = data.type
      
      if (wsCallbacks.has(type)) {
        wsCallbacks.get(type).forEach(callback => callback(data))
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }
    
    ws.onclose = () => {
      console.log('WebSocket连接已关闭，5秒后重连...')
      wsReconnectTimer = setTimeout(() => {
        connectWebSocket()
      }, 5000)
    }
  } catch (error) {
    console.error('WebSocket连接失败:', error)
  }
}

function sendWebSocketMessage(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message))
  } else {
    console.warn('WebSocket未连接')
  }
}

function onWebSocketMessage(type, callback) {
  if (!wsCallbacks.has(type)) {
    wsCallbacks.set(type, [])
  }
  wsCallbacks.get(type).push(callback)
}

// API接口
const api = {
  // 健康检查
  async health() {
    const response = await client.get('/api/health')
    return response.data
  },
  
  // 润色文本
  async polish(data) {
    const response = await client.post('/api/polish', data)
    return response.data
  },
  
  // 剧情预测
  async predict(data) {
    const response = await client.post('/api/predict', data)
    return response.data
  },
  
  // 获取配置
  async getConfig() {
    const response = await client.get('/api/config')
    return response.data
  },
  
  // 更新配置
  async updateConfig(data) {
    const response = await client.post('/api/config', data)
    return response.data
  },
  
  // 获取主题列表
  async getThemes() {
    const response = await client.get('/api/themes')
    return response.data
  },
  
  // WebSocket相关
  ws: {
    connect: connectWebSocket,
    send: sendWebSocketMessage,
    on: onWebSocketMessage
  }
}

export default api
