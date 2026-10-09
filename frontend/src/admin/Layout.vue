<template>
  <n-layout has-sider class="admin-shell">
    <n-layout-sider bordered collapse-mode="width" :collapsed-width="64" :width="232" :collapsed="collapsed" class="sidebar">
      <div class="brand"><img src="/logo.jpg" alt="" /><span v-if="!collapsed">LungTic 管理</span></div>
      <n-menu inverted :collapsed="collapsed" :value="route.path" :options="menuOptions" @update:value="(key: string) => router.push(key)" />
      <n-button class="collapse-button" quaternary block @click="collapsed = !collapsed">{{ collapsed ? "展开" : "收起" }}</n-button>
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="topbar">
        <span>{{ pageTitle }}</span>
        <n-space align="center">
          <n-tag type="info" size="small">{{ store.username }}</n-tag>
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
import { computed, h, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu, NIcon, NButton, NSpace, NTag } from "naive-ui";
import { PeopleOutline, BusinessOutline, ShieldCheckmarkOutline, MailOutline } from "@vicons/ionicons5";
import { useAdminStore } from "./store";
import IcpFooter from "@/components/IcpFooter.vue";

const route = useRoute();
const router = useRouter();
const store = useAdminStore();
const collapsed = ref(false);
const menuOptions = [
  { label: "用户账号", key: "/users", icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }) },
  { label: "科室与授权", key: "/organization", icon: () => h(NIcon, null, { default: () => h(BusinessOutline) }) },
  { label: "访问审计", key: "/audit", icon: () => h(NIcon, null, { default: () => h(ShieldCheckmarkOutline) }) },
  { label: "邮件设置", key: "/smtp", icon: () => h(NIcon, null, { default: () => h(MailOutline) }) },
];
const pageTitle = computed(() => ({ "/users": "用户账号", "/organization": "科室与授权", "/audit": "访问审计", "/smtp": "密码重置邮件" } as Record<string, string>)[route.path] || "管理后台");
function logout() { store.logout(); router.replace("/login"); }
</script>
<style scoped>
.admin-shell { min-height: 100vh; }
.sidebar { background: #1e293b; }
.brand { height: 72px; padding: 18px 16px; display: flex; align-items: center; gap: 10px; color: #fff; font-size: 17px; font-weight: 650; white-space: nowrap; }
.brand img { width: 34px; height: 34px; border-radius: 5px; }
.collapse-button { position: absolute; bottom: 12px; left: 8px; width: calc(100% - 16px); color: #cbd5e1; }
.topbar { height: 60px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; background: #fff; font-weight: 600; }
.content { background: #f5f7fa; min-height: calc(100vh - 60px); }
.content-stack { min-height: calc(100vh - 60px); display: flex; flex-direction: column; }
.content-body { flex: 1 0 auto; padding: 24px; }
@media (max-width: 700px) { .content-body { padding: 12px; } .topbar { padding: 0 12px; } }
</style>
