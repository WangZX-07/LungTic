<template>
  <n-layout has-sider class="admin-shell">
    <button v-if="isMobile && mobileMenuOpen" class="sidebar-backdrop" aria-label="关闭导航菜单" @click="mobileMenuOpen = false" />
    <n-layout-sider
      bordered collapse-mode="width" :collapsed-width="64" :width="232"
      :collapsed="sidebarCollapsed" class="sidebar" :class="{ 'sidebar--open': mobileMenuOpen }"
    >
      <div class="brand"><img src="/logo.jpg" alt="" /><span v-if="!sidebarCollapsed">LungTic 管理</span></div>
      <n-menu inverted :collapsed="sidebarCollapsed" :value="route.path" :options="menuOptions" @update:value="navigate" />
      <n-button class="collapse-button" quaternary block @click="toggleSidebar">
        {{ isMobile ? "关闭菜单" : collapsed ? "展开" : "收起" }}
      </n-button>
    </n-layout-sider>
    <n-layout class="main-layout">
      <n-layout-header bordered class="topbar">
        <div class="topbar-title">
          <n-button
            v-if="isMobile" text circle class="menu-button" aria-label="打开导航菜单"
            :aria-expanded="mobileMenuOpen" @click="mobileMenuOpen = true"
          ><template #icon><n-icon size="22"><MenuOutline /></n-icon></template></n-button>
          <span>{{ pageTitle }}</span>
        </div>
        <n-space align="center">
          <n-tag class="admin-user" type="info" size="small">{{ store.username }}</n-tag>
          <n-button text @click="logout">退出登录</n-button>
        </n-space>
      </n-layout-header>
      <n-layout-content class="content">
        <div class="content-stack">
          <main class="content-body"><router-view /></main>
          <IcpFooter />
        </div>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NIcon, NButton, NSpace, NTag } from "naive-ui";
import { PeopleOutline, BusinessOutline, ShieldCheckmarkOutline, MailOutline, MenuOutline } from "@vicons/ionicons5";
import { useAdminStore } from "./store";
import IcpFooter from "@/components/IcpFooter.vue";

const route = useRoute();
const router = useRouter();
const store = useAdminStore();
const collapsed = ref(false);
const isMobile = ref(false);
const mobileMenuOpen = ref(false);
let mobileQuery: MediaQueryList | null = null;
const sidebarCollapsed = computed(() => !isMobile.value && collapsed.value);
const menuOptions = [
  { label: "用户账号", key: "/users", icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }) },
  { label: "科室与授权", key: "/organization", icon: () => h(NIcon, null, { default: () => h(BusinessOutline) }) },
  { label: "访问审计", key: "/audit", icon: () => h(NIcon, null, { default: () => h(ShieldCheckmarkOutline) }) },
  { label: "邮件设置", key: "/smtp", icon: () => h(NIcon, null, { default: () => h(MailOutline) }) },
];
const pageTitle = computed(() => ({ "/users": "用户账号", "/organization": "科室与授权", "/audit": "访问审计", "/smtp": "密码重置邮件" } as Record<string, string>)[route.path] || "管理后台");
function navigate(key: string) { mobileMenuOpen.value = false; router.push(key); }
function toggleSidebar() {
  if (isMobile.value) mobileMenuOpen.value = false;
  else collapsed.value = !collapsed.value;
}
function logout() { store.logout(); router.replace("/login"); }
function syncMobile(event: MediaQueryListEvent | MediaQueryList) {
  isMobile.value = event.matches;
  if (!event.matches) mobileMenuOpen.value = false;
}
onMounted(() => {
  mobileQuery = window.matchMedia("(max-width: 767px)");
  syncMobile(mobileQuery);
  mobileQuery.addEventListener("change", syncMobile);
});
onBeforeUnmount(() => mobileQuery?.removeEventListener("change", syncMobile));
watch(() => route.path, () => { mobileMenuOpen.value = false; });
</script>
<style scoped>
.admin-shell { min-height: 100vh; min-height: 100dvh; }
.main-layout { min-width: 0; }
.sidebar { background: #1e293b; }
.brand { height: 72px; padding: 18px 16px; display: flex; align-items: center; gap: 10px; color: #fff; font-size: 17px; font-weight: 650; white-space: nowrap; }
.brand img { width: 34px; height: 34px; border-radius: 5px; }
.collapse-button { position: absolute; bottom: 12px; left: 8px; width: calc(100% - 16px); color: #cbd5e1; }
.topbar { height: 60px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; background: #fff; font-weight: 600; }
.topbar-title { min-width: 0; display: flex; align-items: center; gap: 8px; }
.menu-button { width: 44px; height: 44px; flex: 0 0 auto; }
.content { background: #f5f7fa; min-height: calc(100vh - 60px); }
.content-stack { min-height: calc(100vh - 60px); display: flex; flex-direction: column; }
.content-body { flex: 1 0 auto; padding: 24px; }
.sidebar-backdrop { display: none; }
@media (max-width: 767px) {
  .admin-shell { display: block; }
  .sidebar {
    position: fixed !important; inset: 0 auto 0 0; z-index: 110; width: min(82vw, 280px) !important;
    max-width: 280px; height: 100dvh; transform: translateX(-101%);
    transition: transform 180ms cubic-bezier(.22, 1, .36, 1); box-shadow: 4px 0 8px #0f172a26;
  }
  .sidebar--open { transform: translateX(0); }
  .sidebar-backdrop {
    display: block; position: fixed; inset: 0; z-index: 100; border: 0;
    background: rgba(15, 23, 42, .48); touch-action: none;
  }
  .topbar {
    position: sticky; top: 0; z-index: 40; height: 56px;
    padding: 0 max(12px, env(safe-area-inset-right)) 0 max(8px, env(safe-area-inset-left));
  }
  .content { min-height: calc(100dvh - 56px); }
  .content-stack { min-height: calc(100dvh - 56px); }
  .content-body { min-width: 0; padding: 14px 12px; }
  .collapse-button { min-height: 44px; bottom: max(12px, env(safe-area-inset-bottom)); }
}
@media (max-width: 390px) { .admin-user { display: none; } }
@media (prefers-reduced-motion: reduce) { .sidebar { transition: none; } }
</style>
