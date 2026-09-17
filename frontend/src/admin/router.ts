import { createRouter, createWebHashHistory } from "vue-router";
import { useAdminStore } from "./store";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/users" },
    { path: "/login", name: "AdminLogin", component: () => import("./LoginPage.vue") },
    {
      path: "/admin",
      component: () => import("./Layout.vue"),
      children: [
        { path: "", redirect: "/users" },
        { path: "/users", name: "Users", component: () => import("@/views/UserManagement.vue") },
        { path: "/organization", name: "Organization", component: () => import("./OrganizationPage.vue") },
        { path: "/audit", name: "Audit", component: () => import("./AuditPage.vue") },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const store = useAdminStore();
  if (to.name === "AdminLogin") {
    return (store.token && await store.verify()) ? { name: "Users" } : true;
  }
  if (!store.token || !await store.verify()) return { name: "AdminLogin" };
  return true;
});

export default router;
