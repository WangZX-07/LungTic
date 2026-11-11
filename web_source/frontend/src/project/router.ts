import { createRouter, createWebHashHistory } from "vue-router";
import { useProjectStore } from "./store";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/login", name: "ProjectLogin", component: () => import("./views/LoginPage.vue") },
    { path: "/auth-complete", name: "AuthComplete", component: () => import("./views/AuthComplete.vue") },
    {
      path: "/", component: () => import("./Layout.vue"),
      children: [
        { path: "", redirect: "/overview" },
        { path: "overview", name: "ProjectOverview", component: () => import("./views/OverviewPage.vue") },
        { path: "tasks", name: "ProjectTasks", component: () => import("./views/TasksPage.vue") },
        { path: "progress", name: "ProjectProgress", component: () => import("./views/ProgressPage.vue") },
        { path: "activity", name: "ProjectActivity", component: () => import("./views/ActivityPage.vue") },
        { path: "risks", name: "ProjectRisks", component: () => import("./views/RisksPage.vue") },
        { path: "profile", name: "ProjectProfile", component: () => import("./views/ProfilePage.vue") },
        { path: "admin", name: "ProjectAdmin", component: () => import("./views/AdminPage.vue"), meta: { admin: true } },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const store = useProjectStore();
  if (to.name === "ProjectLogin" || to.name === "AuthComplete") return true;
  if (!store.member && !await store.verify()) return { name: "ProjectLogin", query: { next: to.fullPath } };
  if (to.meta.admin && !store.isAdmin) return { name: "ProjectOverview" };
  return true;
});

export default router;
