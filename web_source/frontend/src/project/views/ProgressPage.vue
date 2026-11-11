<template>
  <div class="page-stack">
    <header class="page-heading"><div><h2>进度填报</h2><p>记录已完成事项、下一步和阻塞点；关联任务后可同步更新完成度。</p></div></header>
    <div class="two-column progress-layout">
      <section v-if="store.canContribute" class="surface progress-form">
        <div class="section-header"><div><h3>提交本次进展</h3><p>只填写真实、可验证的进展</p></div></div>
        <n-form label-placement="top" @submit.prevent="submit">
          <n-form-item label="关联任务"><n-select v-model:value="form.task_id" clearable :options="taskOptions" placeholder="可选；成员仅能选择自己的任务" /></n-form-item>
          <n-form-item label="当前完成度"><n-slider v-model:value="form.progress" :step="5" :format-tooltip="(value) => `${value}%`" /></n-form-item>
          <n-form-item label="本次完成" required><n-input v-model:value="form.completed" type="textarea" :rows="4" maxlength="10000" placeholder="说明本次完成了什么，以及可验证的结果" /></n-form-item>
          <n-form-item label="下一步"><n-input v-model:value="form.next_steps" type="textarea" :rows="2" maxlength="10000" /></n-form-item>
          <n-form-item label="阻塞点"><n-input v-model:value="form.blockers" type="textarea" :rows="2" maxlength="10000" placeholder="没有阻塞可留空" /></n-form-item>
          <n-form-item label="证据链接"><n-input v-model:value="form.evidence_url" placeholder="GitHub PR、文档或演示地址" /></n-form-item>
          <n-button type="primary" block attr-type="submit" :loading="saving" :disabled="!form.completed.trim()">提交进度</n-button>
        </n-form>
      </section>
      <section v-else class="surface observer-note"><strong>当前角色为只读观察者</strong><p>你可以查看团队进展，但不能提交或修改任务数据。</p></section>

      <section class="surface feed">
        <div class="section-header"><div><h3>团队进展流</h3><p>最新记录优先</p></div></div>
        <n-skeleton v-if="loading" text :repeat="7" />
        <div v-else-if="!updates.length" class="empty-state"><div><strong>还没有进展记录</strong>完成第一项工作后提交进展。</div></div>
        <article v-for="item in updates" :key="item.id" class="update-card">
          <div class="update-head"><n-avatar round :size="32">{{ item.member_name.slice(0, 1) }}</n-avatar><div><strong>{{ item.member_name }}</strong><span>{{ formatTime(item.created_at) }}</span></div><n-tag v-if="item.progress != null" size="small" :bordered="false" type="info">{{ item.progress }}%</n-tag></div>
          <p v-if="item.task_title" class="task-ref">关联：{{ item.task_title }}</p>
          <p class="completed">{{ item.completed }}</p>
          <dl v-if="item.next_steps || item.blockers">
            <template v-if="item.next_steps"><dt>下一步</dt><dd>{{ item.next_steps }}</dd></template>
            <template v-if="item.blockers"><dt>阻塞点</dt><dd class="text-danger">{{ item.blockers }}</dd></template>
          </dl>
          <a v-if="item.evidence_url" class="safe-link" :href="item.evidence_url" target="_blank" rel="noopener noreferrer">查看证据链接</a>
        </article>
      </section>
    </div>
    <n-alert v-if="message" :type="messageType" :show-icon="true">{{ message }}</n-alert>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NAlert, NAvatar, NButton, NForm, NFormItem, NInput, NSelect, NSkeleton, NSlider, NTag } from "naive-ui";
import api, { errorMessage } from "../api";
import { useProjectStore } from "../store";
import type { ProgressUpdate, ProjectTask } from "../types";
const store = useProjectStore();
const loading = ref(true); const saving = ref(false); const updates = ref<ProgressUpdate[]>([]); const tasks = ref<ProjectTask[]>([]);
const message = ref(""); const messageType = ref<"success" | "error">("success");
const form = ref({ task_id: null as number | null, progress: 0, completed: "", next_steps: "", blockers: "", evidence_url: "" });
const taskOptions = computed(() => tasks.value.filter((task) => store.canLead || task.assignee_member_id === store.member?.id).map((task) => ({ label: task.title, value: task.id })));
const formatTime = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
async function load() {
  loading.value = true;
  try { const [progressRes, taskRes] = await Promise.all([api.get("/progress"), api.get("/tasks")]); updates.value = progressRes.data; tasks.value = taskRes.data; }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "进度记录加载失败"); }
  finally { loading.value = false; }
}
async function submit() {
  saving.value = true; message.value = "";
  try {
    await api.post("/progress", { ...form.value, progress: form.value.task_id ? form.value.progress : null, evidence_url: form.value.evidence_url || null });
    form.value = { task_id: null, progress: 0, completed: "", next_steps: "", blockers: "", evidence_url: "" };
    messageType.value = "success"; message.value = "进度已提交。"; await load();
  } catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "进度提交失败"); }
  finally { saving.value = false; }
}
onMounted(load);
</script>
<style scoped>
.progress-layout { grid-template-columns: minmax(300px, .8fr) minmax(0, 1.2fr); }
.progress-form :deep(.n-form) { padding: 4px 20px 22px; }
.feed > .n-skeleton { padding: 12px 20px 20px; }
.update-card { padding: 16px 20px; border-top: 1px solid #edf1f5; }
.update-head { display: flex; align-items: center; gap: 10px; }
.update-head > div { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.update-head strong { color: #1e293b; font-size: 13px; }
.update-head span { color: #64748b; font-size: 11px; }
.task-ref { margin: 12px 0 5px; color: #1565c0; font-size: 12px; }
.completed { color: #334155; font-size: 14px; line-height: 1.65; white-space: pre-wrap; }
dl { margin: 12px 0; padding: 10px 12px; border-radius: 7px; background: #f8fafc; font-size: 12px; }
dt { color: #64748b; font-weight: 600; } dd { margin: 2px 0 8px; color: #334155; white-space: pre-wrap; } dd:last-child { margin-bottom: 0; }
.observer-note { padding: 24px; } .observer-note strong { color: #334155; } .observer-note p { margin-top: 5px; color: #64748b; line-height: 1.6; }
@media (max-width: 900px) { .progress-layout { grid-template-columns: 1fr; } }
</style>
