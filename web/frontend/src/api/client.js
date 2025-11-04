import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// 创建axios实例，配置弱网优化
const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json',
    'Accept-Encoding': 'gzip, deflate'  // 启用压缩
  },
  // 启用keepalive
  httpAgent: {
    keepAlive: true,
    keepAliveMsecs: 1000
  },
  httpsAgent: {
    keepAlive: true,
    keepAliveMsecs: 1000
  }
})

// 请求重试配置
const MAX_RETRIES = 2
const RETRY_DELAY = 1000 // 1秒

// 判断是否应该重试
function shouldRetry(error) {
  // 网络错误、超时、或服务器5xx错误时重试
  if (!error.response) {
    return true // 网络错误
  }
  const status = error.response.status
  return status >= 500 || status === 408 || status === 429
}

// 延迟函数
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// 请求拦截器：添加重试逻辑
client.interceptors.response.use(
  response => response,
  async error => {
    const config = error.config
    
    // 如果没有配置重试次数，初始化为0
    if (!config.__retryCount) {
      config.__retryCount = 0
    }
    
    // 判断是否应该重试
    if (config.__retryCount < MAX_RETRIES && shouldRetry(error)) {
      config.__retryCount++
      
      // 计算退避延迟：第1次重试1秒，第2次重试2秒
      const backoffDelay = RETRY_DELAY * config.__retryCount
      
      console.log(`请求失败，${backoffDelay}ms后进行第${config.__retryCount}次重试...`)
      
      // 等待后重试
      await delay(backoffDelay)
      
      // 重新发起请求
      return client.request(config)
    }
    
    // 超过重试次数或不应重试，抛出错误
    return Promise.reject(error)
  }
)

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
      console.log('WebSocket连接已关闭，3秒后重连...')
      wsReconnectTimer = setTimeout(() => {
        connectWebSocket()
      }, 3000)  // 减少重连延迟到3秒，提高弱网环境下的响应速度
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
