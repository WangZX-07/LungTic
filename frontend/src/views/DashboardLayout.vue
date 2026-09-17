<template>
  <n-layout has-sider style="height:100vh">
    <n-layout-sider bordered collapse-mode="width" :collapsed-width="64" :width="256" :collapsed="collapsed" style="background:#1E293B">
      <div style="display:flex;align-items:center;gap:8px;padding:24px 16px">
        <img src="/logo.jpg" style="width:32px;height:32px;border-radius:4px" />
        <span v-if="!collapsed" style="color:#fff;font-size:20px;font-weight:600">LungTic</span>
      </div>
      <n-menu :collapsed="collapsed" :inverted="true" :value="activeMenu" :options="visibleMenuOptions" @update:value="onMenuChange" />
      <div style="position:absolute;bottom:0;width:100%;padding:8px">
        <n-button quaternary block @click="collapsed = !collapsed">
          <template #icon><n-icon><ChevronBack v-if="!collapsed" /><ChevronForward v-else /></n-icon></template>
        </n-button>
      </div>
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered style="display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:56px;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <n-button v-if="isStudyPage" text size="small" @click="router.push('/dashboard/patients')">
            <template #icon><n-icon><ArrowBack /></n-icon></template>
            返回患者列表
          </n-button>
          <span style="font-size:16px;font-weight:600;color:#1E293B">{{ pageTitle }}</span>
        </div>
        <n-space align="center" :size="12">
          <n-tag size="small" :type="roleTagType">{{ roleLabel }}</n-tag>
          <n-tag size="small" type="info">{{ auth.user?.username }}</n-tag>
          <n-button text @click="handleLogout">退出</n-button>
        </n-space>
      </n-layout-header>
      <n-layout-content style="padding:24px;background:#F5F7FA">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NButton, NIcon, NTag, NSpace } from "naive-ui";
import { PeopleOutline, CubeOutline, ScanOutline, SettingsOutline, PeopleCircleOutline, ChevronBack, ChevronForward, ArrowBack } from "@vicons/ionicons5";
import { useAuthStore } from "@/stores/auth";
import type { MenuOption } from "naive-ui";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const standaloneViewer = import.meta.env.VITE_STANDALONE_VIEWER === "true";
const collapsed = ref(false);
const isStudyPage = computed(() => route.path.startsWith("/dashboard/study"));
const activeMenu = computed(() => route.path.startsWith("/dashboard/study") ? "/dashboard/patients" : route.path);

const roleLabel = computed(() => {
  if (auth.isAdmin) return "管理员";
  if (auth.isPatient) return "患者";
  return "医生";
});

const roleTagType = computed(() => {
  if (auth.isAdmin) return "error" as const;
  if (auth.isPatient) return "success" as const;
  return "info" as const;
});

const pageTitle = computed(() => {
  if (route.path.startsWith("/dashboard/study")) return "影像浏览";
  if (route.path === "/dashboard/tici-viewer") return "TICI 查看器";
  if (route.path === "/dashboard/models") return "模型管理";
  if (route.path === "/dashboard/patients") return "患者列表";
  if (route.path === "/dashboard/users") return "用户管理";
  if (route.path === "/dashboard/settings") return "设置";
  return "LungTic";
});

const fullMenuOptions: MenuOption[] = [
  { label: "患者列表", key: "/dashboard/patients", icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }) },
  { label: "TICI 查看器", key: "/dashboard/tici-viewer", icon: () => h(NIcon, null, { default: () => h(ScanOutline) }) },
  { label: "模型管理", key: "/dashboard/models", icon: () => h(NIcon, null, { default: () => h(CubeOutline) }) },
  { label: "用户管理", key: "/dashboard/users", icon: () => h(NIcon, null, { default: () => h(PeopleCircleOutline) }) },
  { label: "设置", key: "/dashboard/settings", icon: () => h(NIcon, null, { default: () => h(SettingsOutline) }) },
];

const visibleMenuOptions = computed(() => {
  if (standaloneViewer) {
    return fullMenuOptions.filter(
      m => m.key === "/dashboard/tici-viewer" || m.key === "/dashboard/settings",
    );
  }
  if (auth.isAdmin) return fullMenuOptions;
  if (auth.isPatient) return fullMenuOptions.filter(m => m.key === "/dashboard/patients" || m.key === "/dashboard/settings");
  // doctor
  return fullMenuOptions.filter(m => m.key !== "/dashboard/users");
});

function onMenuChange(key: string) { router.push(key); }
function handleLogout() { auth.logout(); router.replace("/login"); }
onMounted(() => { if (!auth.user) { auth.fetchMe().catch(() => { auth.logout(); router.replace("/login"); }); } });
</script>
<style>.n-menu{background:transparent!important}</style>
