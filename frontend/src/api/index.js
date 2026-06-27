import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器：自动附加 token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器：401 跳转登录
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// 线索来源
export const getSources = () => api.get('/leads/sources')
export const createSource = (data) => api.post('/leads/sources', data)

// 客户线索
export const getLeads = (params) => api.get('/leads/', { params })
export const getLead = (id) => api.get(`/leads/${id}`)
export const createLead = (data) => api.post('/leads/', data)
export const updateLead = (id, data) => api.put(`/leads/${id}`, data)
export const deleteLead = (id) => api.delete(`/leads/${id}`)

export default api