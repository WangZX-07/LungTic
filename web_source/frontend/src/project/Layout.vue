<template>
  <div class="project-shell">
    <a class="skip-link" href="#project-main-content">跳到主要内容</a>
    <aside class="project-sidebar" aria-label="项目导航">
      <div class="project-brand">
        <img src="/logo.jpg" alt="" />
        <div><strong>LungTic</strong><span>项目进度</span></div>
      </div>
      <nav class="side-nav">
        <RouterLink v-for="item in desktopNav" :key="item.to" :to="item.to">
          <n-icon size="19"><component :is="item.icon" /></n-icon><span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-member">
        <n-avatar round :size="34" :src="store.member?.avatar_url || undefined">{{ store.member?.name?.slice(0, 1) }}</n-avatar>
        <div><strong>{{ store.member?.name }}</strong><span>{{ roleLabel }}</span></div>
      </div>
    </aside>

    <div class="project-main">
      <header class="project-topbar">
        <div><h1>{{ pageTitle }}</h1><p>{{ todayText }}</p></div>
        <n-space align="center">
          <n-tag v-if="store.member" size="small" :bordered="false" type="info">{{ roleLabel }}</n-tag>
          <n-button quaternary size="small" @click="doLogout">退出</n-button>
        </n-space>
      </header>
      <main id="project-main-content" class="project-content" tabindex="-1"><RouterView /></main>
      <IcpFooter class="project-footer" />
    </div>

    <nav class="bottom-nav" aria-label="移动端导航">
      <RouterLink v-for="item in mobileNav" :key="item.to" :to="item.to">
        <n-icon size="21"><component :is="item.icon" /></n-icon><span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAvatar, NButton, NIcon, NSpace, NTag } from "naive-ui";
import {
  AnalyticsOutline, AlertCircleOutline, CheckmarkDoneOutline, GitBranchOutline,
  HomeOutline, PersonCircleOutline, SettingsOutline,
} from "@vicons/ionicons5";
import IcpFooter from "@/components/IcpFooter.vue";
import { useProjectStore } from "./store";

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const baseNav = [
  { to: "/overview", label: "总览", icon: HomeOutline },
  { to: "/tasks", label: "任务", icon: CheckmarkDoneOutline },
  { to: "/progress", label: "进度", icon: AnalyticsOutline },
  { to: "/activity", label: "动态", icon: GitBranchOutline },
];
const desktopNav = computed(() => [
  ...baseNav,
  { to: "/risks", label: "风险与决策", icon: AlertCircleOutline },
  { to: "/profile", label: "我的", icon: PersonCircleOutline },
  ...(store.isAdmin ? [{ to: "/admin", label: "项目设置", icon: SettingsOutline }] : []),
]);
const mobileNav = [...baseNav, { to: "/profile", label: "我的", icon: PersonCircleOutline }];
const titles: Record<string, string> = {
  "/overview": "项目总览", "/tasks": "任务与里程碑", "/progress": "进度填报",
  "/activity": "GitHub 动态", "/risks": "风险与决策", "/profile": "我的项目页", "/admin": "项目设置",
};
const roleLabels: Record<string, string> = {
  project_admin: "项目管理员", project_lead: "项目负责人", team_lead: "小组负责人",
  contributor: "项目成员", observer: "观察者", unassigned: "未分配",
};
const pageTitle = computed(() => titles[route.path] || "LungTic 项目");
const roleLabel = computed(() => roleLabels[store.member?.role || "unassigned"]);
const todayText = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date());
async function doLogout() { await store.logout(); await router.replace("/login"); }
</script>
