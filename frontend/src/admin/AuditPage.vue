<template>
  <div class="audit-page">
    <div class="heading"><div><h1>访问审计</h1><p>查看最近的访问、授权和完整性校验事件。</p></div><n-button :loading="loading" @click="load">刷新</n-button></div>
    <n-card size="small">
      <n-space align="center" class="filter-row">
        <n-input-number v-model:value="patientId" :min="1" clearable placeholder="患者 ID（可选）" style="width:180px" />
        <n-button type="primary" @click="load">筛选</n-button>
        <span class="hint">最多显示最近 100 条</span>
      </n-space>
    </n-card>
    <n-alert v-if="error" type="error" style="margin-top:16px">{{ error }}</n-alert>
    <n-card size="small" style="margin-top:16px">
      <div class="table-wrap"><table>
        <thead><tr><th>时间</th><th>操作者 ID</th><th>患者 ID</th><th>动作</th><th>资源</th><th>结果</th></tr></thead>
        <tbody>
          <tr v-for="event in events" :key="event.id">
            <td>{{ formatTime(event.created_at) }}</td><td>{{ event.actor_user_id }}</td>
            <td>{{ event.patient_id ?? '—' }}</td><td>{{ event.action }}</td>
            <td>{{ event.resource_type }} {{ event.resource_id ?? '' }}</td>
            <td><n-tag size="small" :type="event.allowed ? 'success' : 'error'">{{ event.allowed ? '允许' : '拒绝' }}</n-tag></td>
          </tr>
          <tr v-if="!events.length"><td colspan="6" class="empty">暂无审计事件</td></tr>
        </tbody>
      </table></div>
    </n-card>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NAlert, NButton, NCard, NInputNumber, NSpace, NTag } from "naive-ui";
import api from "./api";
type Event = { id:number; created_at:string; actor_user_id:number; patient_id:number|null; action:string; resource_type:string; resource_id:number|null; allowed:boolean };
const events = ref<Event[]>([]);
const patientId = ref<number|null>(null);
const loading = ref(false);
const error = ref("");
function formatTime(value: string) { return new Date(value + (value.endsWith("Z") ? "" : "Z")).toLocaleString("zh-CN"); }
async function load() {
  loading.value = true; error.value = "";
  try { events.value = (await api.get("/organization/audit-events", { params: { limit: 100, ...(patientId.value ? { patient_id: patientId.value } : {}) } })).data; }
  catch (e: any) { error.value = e.response?.data?.detail || "无法读取审计事件"; }
  finally { loading.value = false; }
}
onMounted(load);
</script>
<style scoped>
.audit-page { max-width:1200px; }
.heading { display:flex; justify-content:space-between; align-items:start; margin-bottom:18px; }
h1 { font-size:20px; margin:0 0 4px; color:#1e293b; }
.heading p, .hint { color:#64748b; font-size:13px; margin:6px 0 0; }
.table-wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; min-width:850px; font-size:13px; }
th,td { padding:11px 12px; text-align:left; border-bottom:1px solid #e2e8f0; }
th { background:#f8fafc; color:#475569; font-weight:600; }
.empty { text-align:center; color:#64748b; padding:24px; }
@media (max-width: 640px) {
  .heading { align-items: flex-start; gap: 12px; }
  .filter-row { width: 100%; align-items: stretch !important; flex-direction: column; }
  .filter-row :deep(.n-input-number) { width: 100% !important; }
  .table-wrap { max-width: calc(100vw - 50px); overscroll-behavior-x: contain; }
}
@media (pointer: coarse) {
  .audit-page :deep(.n-button) { min-height: 44px; }
}
</style>
