import { createRouter, createWebHashHistory } from "vue-router";
import { getClientToken, setClientToken } from "@/api/server";

type UserRole = "patient" | "doctor" | "viewer_admin";
const standaloneViewer = import.meta.env.VITE_STANDALONE_VIEWER === "true";

const roleRoutes: Record<UserRole, string[]> = {
  patient: ["PatientList", "StudyWorkspace", "Settings"],
  doctor: ["PatientList", "StudyWorkspace", "TiciViewer", "ModelManager", "StudyComparison", "Settings"],
  viewer_admin: ["TiciViewer", "Settings"],
};

function getUserRole(): UserRole | null {
  const token = getClientToken();
  if (!token) return null;
  try {
    const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")));
    if (payload.role === "doctor" || payload.role === "patient") return payload.role;
    if (standaloneViewer && payload.role === "admin") return "viewer_admin";
    return null;
  } catch {
    return null;
  }
}

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/login" },
    {
      path: "/login",
      name: "Login",
      component: () => import("@/views/LoginPage.vue"),
    },
    {
      path: "/dashboard",
      name: "Dashboard",
      component: () => import("@/views/DashboardLayout.vue"),
      redirect: standaloneViewer ? "/dashboard/tici-viewer" : "/dashboard/patients",
      children: [
        {
          path: "patients",
          name: "PatientList",
          component: () => import("@/views/PatientList.vue"),
        },
        {
          path: "models",
          name: "ModelManager",
          component: () => import("@/views/ModelManager.vue"),
        },
        {
          path: "tici-viewer",
          name: "TiciViewer",
          component: () => import("@/views/TiciViewer.vue"),
        },
        {
          path: "study/:id",
          name: "StudyWorkspace",
          component: () => import("@/views/StudyWorkspace.vue"),
        },
        {
          path: "compare",
          name: "StudyComparison",
          component: () => import("@/views/StudyComparison.vue"),
        },
        {
          path: "settings",
          name: "Settings",
          component: () => import("@/views/SettingsPage.vue"),
        },
      ],
    },
  ],
});

router.beforeEach((to, _from, next) => {
  const token = getClientToken();
  if (token && !getUserRole()) {
    setClientToken("");
    next({ name: "Login" });
    return;
  }

  if (to.name !== "Login" && !token) {
    next({ name: "Login", query: { redirect: to.fullPath } });
    return;
  }

  if (to.name === "Login" && token) {
    next({ name: standaloneViewer ? "TiciViewer" : "PatientList" });
    return;
  }

  if (
    standaloneViewer
    && token
    && to.name !== "Login"
    && to.name !== "TiciViewer"
    && to.name !== "Settings"
  ) {
    next({ name: "TiciViewer" });
    return;
  }

  // Role-based route guard
  if (to.name && to.name !== "Login" && token) {
    const role = getUserRole();
    if (role && roleRoutes[role]) {
      const nameStr = to.name as string;
      if (!roleRoutes[role].includes(nameStr)) {
        next({ name: standaloneViewer ? "TiciViewer" : "PatientList" });
        return;
      }
    }
  }

  next();
});

export default router;
