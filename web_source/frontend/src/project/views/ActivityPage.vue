<template>
  <div class="page-stack">
    <header class="page-heading"><div><h2>GitHub 项目动态</h2><p>由仓库 Webhook 自动同步；动态是进度证据，不直接等同于完成度。</p></div><n-button :loading="loading" @click="load">刷新</n-button></header>
    <section class="surface">
      <n-skeleton v-if="loading" text :repeat="8" />
      <div v-else-if="!events.length" class="empty-state"><div><strong>还没有 GitHub 动态</strong>管理员完成 Webhook 配置后，Push、PR、Issue 和工作流事件会显示在这里。</div></div>
      <article v-for="event in events" :key="event.id" class="activity-row list-row">
        <n-icon size="20" :color="eventColor(event.event_type)"><component :is="eventIcon(event.event_type)" /></n-icon>
        <div class="list-row__main">
          <a v-if="event.url" class="list-row__title activity-link" :href="event.url" target="_blank" rel="noopener noreferrer">{{ event.title }}</a>
          <div v-else class="list-row__title">{{ event.title }}</div>
          <div class="list-row__meta">{{ event.actor_login || "GitHub" }} · {{ eventLabel(event.event_type, event.action) }}<template v-if="event.reference"> · {{ event.reference }}</template> · {{ formatTime(event.occurred_at) }}</div>
        </div>
      </article>
    </section>
    <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NAlert, NButton, NIcon, NSkeleton } from "naive-ui";
import { GitCommitOutline, GitMergeOutline, GitPullRequestOutline, PricetagOutline, PulseOutline } from "@vicons/ionicons5";
import api, { errorMessage } from "../api";
const events = ref<any[]>([]); const loading = ref(true); const error = ref("");
const icons: Record<string, any> = { push: GitCommitOutline, pull_request: GitPullRequestOutline, issues: GitMergeOutline, workflow_run: PulseOutline, release: PricetagOutline };
const eventIcon = (value: string) => icons[value] || GitCommitOutline;
const eventColor = (value: string) => ({ pull_request: "#7c3aed", issues: "#d97706", workflow_run: "#1565c0", release: "#16a34a" } as Record<string,string>)[value] || "#52647b";
const eventLabel = (type: string, action?: string) => ({ push: "推送代码", pull_request: `Pull Request ${action || ""}`, issues: `Issue ${action || ""}`, workflow_run: `工作流 ${action || ""}`, release: `发布 ${action || ""}` } as Record<string,string>)[type] || type;
const formatTime = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
async function load() { loading.value = true; error.value = ""; try { events.value = (await api.get("/activity")).data; } catch (reason) { error.value = errorMessage(reason, "GitHub 动态加载失败"); } finally { loading.value = false; } }
onMounted(load);
</script>
<style scoped>
.activity-row > .n-icon { flex: 0 0 auto; margin-top: 2px; }
.activity-link:hover { color: #1565c0; text-decoration: underline; text-underline-offset: 2px; }
</style>
