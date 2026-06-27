import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'leads',
        name: 'Leads',
        component: () => import('../views/Leads.vue'),
        meta: { title: '客户线索' }
      },
      {
        path: 'leads/:id',
        name: 'LeadDetail',
        component: () => import('../views/LeadDetail.vue'),
        meta: { title: '线索详情' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 简单鉴权守卫（后续接入真实 JWT）
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router