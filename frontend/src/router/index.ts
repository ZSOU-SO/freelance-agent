import { createRouter, createWebHistory } from 'vue-router'

import AnalysisView from '../views/AnalysisView.vue'
import CaseFormView from '../views/CaseFormView.vue'
import CaseListView from '../views/CaseListView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'analysis', component: AnalysisView },
    { path: '/cases', name: 'cases', component: CaseListView },
    { path: '/cases/new', name: 'case-new', component: CaseFormView },
    { path: '/cases/:id/edit', name: 'case-edit', component: CaseFormView },
  ],
})

