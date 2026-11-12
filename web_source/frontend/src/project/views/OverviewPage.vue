<template>
  <div class="page-stack">
    <header class="page-heading">
      <div><h2>LungTic 当前进展</h2><p>进度由任务权重计算，代码活动仅作为可追溯证据。</p></div>
      <n-button v-if="store.canContribute" type="primary" @click="router.push('/progress')">填报进度</n-button>
    </header>

    <n-skeleton v-if="loading" text :repeat="8" />
    <template v-else-if="dashboard">
      <section class="progress-band surface" aria-label="项目整体进度">
        <div><span>任务完成度</span><strong>{{ dashboard.project.has_tasks ? `${dashboard.project.progress}%` : "—" }}</strong></div>
        <n-progress v-if="dashboard.project.has_tasks" type="line" :percentage="dashboard.project.progress" :show-indicator="false" :height="10" />
        <div v-else class="progress-empty">尚无任务，暂不计算百分比</div>
        <p>{{ dashboard.project.has_tasks ? `依据 ${dashboard.project.task_count} 个任务汇总 · ${dashboard.project.github_evidence_count} 条 GitHub 证据` : `已同步 ${dashboard.project.github_evidence_count} 条 GitHub 证据；创建任务后再计算完成度` }}</p>
      </section>
      <section class="metric-strip" aria-label="项目指标">
        <div class="metric-item"><span>进行中任务</span><strong>{{ dashboard.metrics.open_tasks }}</strong></div>
        <div class="metric-item"><span>我的待办</span><strong>{{ dashboard.metrics.my_open_tasks }}</strong></div>
        <div class="metric-item"><span>已逾期</span><strong :class="{ 'text-danger': dashboard.metrics.overdue_tasks }">{{ dashboard.metrics.overdue_tasks }}</strong></div>
        <div class="metric-item"><span>开放风险</span><strong>{{ dashboard.metrics.open_risks }}</strong></div>
      </section>

      <div class="two-column">
        <section class="surface">
          <div class="section-header"><div><h3>里程碑</h3><p>按交付阶段观察任务完成度</p></div><n-button text @click="router.push('/tasks')">查看任务</n-button></div>
          <div v-if="!dashboard.milestones.length" class="empty-state"><div><strong>还没有里程碑</strong>由项目负责人创建第一个交付阶段。</div></div>
          <div v-for="item in dashboard.milestones" :key="item.id" class="milestone-row list-row">
            <div class="list-row__main"><div class="list-row__title">{{ item.title }}</div><div class="list-row__meta">{{ statusLabel(item.status) }} · {{ formatDate(item.due_date) }}</div></div>
            <n-progress type="circle" :percentage="item.progress" :width="46" :stroke-width="8" />
          </div>
        </section>
        <section class="surface">
          <div class="section-header"><div><h3>最近填报</h3><p>团队成员的最新推进记录</p></div></div>
          <div v-if="!dashboard.recent_updates.length" class="empty-state"><div><strong>暂无进度记录</strong>完成工作后在“进度”页提交第一条记录。</div></div>
          <article v-for="item in dashboard.recent_updates" :key="item.id" class="list-row update-row">
            <n-avatar round :size="30">{{ item.member_name.slice(0, 1) }}</n-avatar>
            <div class="list-row__main"><div class="list-row__title">{{ item.member_name }}<span v-if="item.progress != null"> · {{ item.progress }}%</span></div><div class="list-row__meta">{{ item.completed }} · {{ relativeTime(item.created_at) }}</div></div>
          </article>
        </section>
      </div>
    </template>
    <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NAlert, NAvatar, NButton, NProgress, NSkeleton } from "naive-ui";
import api, { errorMessage } from "../api";
import { useProjectStore } from "../store";
const router = useRouter();
const store = useProjectStore();
const loading = ref(true);
const error = ref("");
const dashboard = ref<any>(null);
const labels: Record<string, string> = { planned: "待开始", active: "进行中", completed: "已完成", paused: "已暂停" };
const statusLabel = (value: string) => labels[value] || value;
const formatDate = (value?: string | null) => value ? `截止 ${value}` : "未设截止时间";
function relativeTime(value: string) {
  const delta = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.floor(delta / 60000));
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours} 小时前` : `${Math.floor(hours / 24)} 天前`;
}
onMounted(async () => {
  try { dashboard.value = (await api.get("/dashboard")).data; }
  catch (reason) { error.value = errorMessage(reason, "项目总览加载失败"); }
  finally { loading.value = false; }
});
</script>
<style scoped>
.progress-band { padding: 20px; display: grid; grid-template-columns: 190px minmax(160px, 1fr) auto; align-items: center; gap: 20px; }
.progress-band span { color: #52647b; font-size: 12px; }
.progress-band strong { display: block; color: #172033; font-size: 28px; line-height: 36px; font-variant-numeric: tabular-nums; }
.progress-band p { color: #64748b; font-size: 12px; }
.progress-empty { min-height: 10px; border-radius: 5px; background: #e9eef4; color: #64748b; font-size: 12px; line-height: 32px; text-align: center; }
.milestone-row :deep(.n-progress) { flex: 0 0 auto; }
.update-row { align-items: flex-start; }
@media (max-width: 767px) { .progress-band { grid-template-columns: 1fr; gap: 10px; } .progress-band p { display: none; } }
</style>
