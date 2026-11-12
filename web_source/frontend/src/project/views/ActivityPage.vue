<template>
  <div class="page-stack">
    <header class="page-heading"><div><h2>GitHub 项目动态</h2><p>由仓库历史和 Webhook 同步；代码活动是进度证据，不直接等同于完成度。</p></div><n-button :loading="loading" @click="load">刷新</n-button></header>
    <section v-if="store.isAdmin" class="surface sync-panel">
      <div class="sync-copy"><strong>导入已有 GitHub 历史</strong><p>回填提交、Issue、PR、工作流和 Release。可把 Issue/PR 建成任务，让任务完成度有可计算的基础。</p></div>
      <div class="sync-controls">
        <n-select v-model:value="historyDays" :options="historyOptions" aria-label="历史回溯范围" />
        <n-checkbox v-model:checked="importTasks">同时导入 Issue/PR 为任务</n-checkbox>
        <n-button type="primary" :loading="syncing" @click="syncHistory">同步历史</n-button>
      </div>
      <p class="sync-note">最多扫描 20 个分支、每类读取 300 条并按提交 SHA 去重；已同步记录会更新而不会重复。提交数量不会直接换算成百分比。</p>
    </section>
    <section class="surface">
      <n-skeleton v-if="loading" text :repeat="8" />
      <div v-else-if="!events.length" class="empty-state"><div><strong>还没有 GitHub 动态</strong>管理员可先同步已有历史；之后的新事件由 Webhook 持续记录。</div></div>
      <article v-for="event in events" :key="event.id" class="activity-row list-row">
        <n-icon size="20" :color="eventColor(event.event_type)"><component :is="eventIcon(event.event_type)" /></n-icon>
        <div class="list-row__main">
          <a v-if="event.url" class="list-row__title activity-link" :href="event.url" target="_blank" rel="noopener noreferrer">{{ event.title }}</a>
          <div v-else class="list-row__title">{{ event.title }}</div>
          <div class="list-row__meta">{{ event.actor_login || "GitHub" }} · {{ eventLabel(event.event_type, event.action) }}<template v-if="event.reference"> · {{ event.reference }}</template> · {{ formatTime(event.occurred_at) }}</div>
        </div>
      </article>
    </section>
    <n-alert v-if="success" type="success" :show-icon="true">{{ success }}</n-alert>
    <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NAlert, NButton, NCheckbox, NIcon, NSelect, NSkeleton } from "naive-ui";
import { GitCommitOutline, GitMergeOutline, GitPullRequestOutline, PricetagOutline, PulseOutline } from "@vicons/ionicons5";
import api, { errorMessage } from "../api";
import { useProjectStore } from "../store";
const store = useProjectStore();
const events = ref<any[]>([]); const loading = ref(true); const syncing = ref(false); const error = ref(""); const success = ref("");
const historyDays = ref(365); const importTasks = ref(true);
const historyOptions = [
  { label: "最近 90 天", value: 90 }, { label: "最近 1 年", value: 365 },
  { label: "最近 3 年", value: 1095 }, { label: "最多 10 年", value: 3650 },
];
const icons: Record<string, any> = { commit: GitCommitOutline, push: GitCommitOutline, pull_request: GitPullRequestOutline, issues: GitMergeOutline, workflow_run: PulseOutline, release: PricetagOutline };
const eventIcon = (value: string) => icons[value] || GitCommitOutline;
const eventColor = (value: string) => ({ pull_request: "#7c3aed", issues: "#d97706", workflow_run: "#1565c0", release: "#16a34a" } as Record<string,string>)[value] || "#52647b";
const eventLabel = (type: string, action?: string) => ({ commit: "代码提交", push: "推送代码", pull_request: `Pull Request ${action || ""}`, issues: `Issue ${action || ""}`, workflow_run: `工作流 ${action || ""}`, release: `发布 ${action || ""}` } as Record<string,string>)[type] || type;
const formatTime = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
async function load() { loading.value = true; error.value = ""; try { events.value = (await api.get("/activity")).data; } catch (reason) { error.value = errorMessage(reason, "GitHub 动态加载失败"); } finally { loading.value = false; } }
async function syncHistory() {
  syncing.value = true; error.value = ""; success.value = "";
  try {
    const { data } = await api.post("/admin/github/sync-history", { days: historyDays.value, import_tasks: importTasks.value }, { timeout: 120000 });
    success.value = `同步完成：找到 ${data.events_found} 条动态，新增 ${data.events_inserted} 条，创建 ${data.tasks_created} 个任务，完成 ${data.tasks_completed} 个任务。`;
    await load();
  } catch (reason) { error.value = errorMessage(reason, "GitHub 历史同步失败"); }
  finally { syncing.value = false; }
}
onMounted(load);
</script>
<style scoped>
.sync-panel { padding: 18px 20px; display: flex; align-items: center; flex-wrap: wrap; gap: 14px 20px; }
.sync-copy { min-width: 260px; flex: 1; }
.sync-copy strong { color: #1e293b; font-size: 14px; }
.sync-copy p, .sync-note { color: #64748b; font-size: 12px; line-height: 18px; }
.sync-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.sync-controls .n-select { width: 140px; }
.sync-note { width: 100%; margin: 0; }
.activity-row > .n-icon { flex: 0 0 auto; margin-top: 2px; }
.activity-link:hover { color: #1565c0; text-decoration: underline; text-underline-offset: 2px; }
@media (max-width: 650px) { .sync-controls, .sync-controls .n-select, .sync-controls .n-button { width: 100%; } }
</style>
