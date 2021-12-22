import Vue from 'vue';
import VueRouter, { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

import Home from '../views/Home.vue';

const routes = [
    {
        path: '/',
        name: 'home',
        component: Home,
    },
]

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes,
});

export default router;