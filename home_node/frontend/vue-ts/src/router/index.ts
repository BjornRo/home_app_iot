import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import HomeView from "../views/HomeView.vue";
import DashView from "../views/DashView.vue";
import AuthHeader from "@/services/auth-header";

const routes: Array<RouteRecordRaw> = [
    {
        path: "/",
        name: "home",
        component: HomeView,
    },
    {
        path: "/dash",
        name: "dash",
        component: DashView,
        beforeEnter: (to, from, next) => {
            if (AuthHeader.get_token() === null) next({ path: "/", replace: true });
            else next();
        },
    },
    {
        path: "/:pathMatch(.*)",
        name: "404",
        component: () => import("../views/ErrorView.vue"),
    },
];

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes,
});

export default router;
