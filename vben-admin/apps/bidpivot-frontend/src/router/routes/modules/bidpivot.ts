import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:home',
      order: 1,
      title: '首页',
    },
    name: 'Home',
    path: '/home',
    component: () => import('#/views/Home.vue'),
  },
  {
    meta: {
      icon: 'lucide:file-text',
      order: 2,
      title: '标书管理',
    },
    name: 'BidManagement',
    path: '/bid',
    redirect: '/bids',
    children: [
      {
        name: 'BidCreate',
        path: '/bid/create',
        component: () => import('#/views/BidCreate.vue'),
        meta: {
          icon: 'lucide:plus-circle',
          title: '创作标书',
        },
      },
      {
        name: 'MyBids',
        path: '/bids',
        component: () => import('#/views/MyBids.vue'),
        meta: {
          icon: 'lucide:list',
          title: '我的标书',
        },
      },
      {
        name: 'BidDetail',
        path: '/bid/:id',
        component: () => import('#/views/BidDetail.vue'),
        meta: {
          hideInMenu: true,
          title: '标书详情',
        },
      },
    ],
  },
  {
    meta: {
      icon: 'lucide:book-open',
      order: 3,
      title: '知识库',
    },
    name: 'KnowledgeBase',
    path: '/knowledge',
    redirect: '/knowledge/personal',
    children: [
      {
        name: 'MyKnowledge',
        path: '/knowledge/personal',
        component: () => import('#/views/Knowledge.vue'),
        meta: {
          icon: 'lucide:user',
          title: '我的知识库',
        },
      },
      {
        name: 'GlobalKnowledge',
        path: '/knowledge/global',
        component: () => import('#/views/Knowledge.vue'),
        meta: {
          icon: 'lucide:globe',
          title: '全局知识库',
        },
      },
    ],
  },
  {
    meta: {
      icon: 'lucide:building',
      order: 4,
      title: '竞品分析',
    },
    name: 'CompetitorAnalysis',
    path: '/competitors',
    component: () => import('#/views/CompetitorAnalysis.vue'),
  },
  {
    meta: {
      icon: 'lucide:bar-chart',
      order: 5,
      title: '丢标分析',
    },
    name: 'LossAnalysis',
    path: '/loss-analysis',
    component: () => import('#/views/LossAnalysis.vue'),
  },
  {
    meta: {
      icon: 'lucide:settings',
      order: 100,
      title: '系统设置',
      roles: ['admin'],
    },
    name: 'Settings',
    path: '/settings',
    component: () => import('#/views/Settings.vue'),
  },
];

export default routes;
