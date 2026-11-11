<template>
  <div class="page-stack">
    <header class="page-heading">
      <div><h2>任务与里程碑</h2><p>任务进度参与项目加权计算；Issue 和 PR 可作为自动完成依据。</p></div>
      <n-space v-if="store.canLead">
        <n-button v-if="store.canManageProject" @click="showMilestone = true">新建里程碑</n-button>
        <n-button type="primary" @click="showTask = true">新建任务</n-button>
      </n-space>
    </header>

    <section class="surface filter-panel">
      <div class="filter-row">
        <n-checkbox v-model:checked="mine" @update:checked="loadTasks">只看我的任务</n-checkbox>
        <n-select v-model:value="statusFilter" clearable placeholder="全部状态" :options="statusOptions" style="width: 150px" @update:value="loadTasks" />
        <span class="text-muted">共 {{ tasks.length }} 项</span>
      </div>
    </section>

    <n-skeleton v-if="loading" text :repeat="8" />
    <section v-else class="surface task-list">
      <div v-if="!tasks.length" class="empty-state"><div><strong>没有符合条件的任务</strong>负责人可以新建任务，成员也可切换筛选查看全部。</div></div>
      <article v-for="task in tasks" :key="task.id" class="task-row list-row">
        <span class="status-dot" :class="statusDot(task.status)" />
        <div class="list-row__main">
          <div class="task-title-line">
            <div class="list-row__title">{{ task.title }}</div>
            <n-tag size="small" :bordered="false" :type="priorityType(task.priority)">{{ priorityLabel(task.priority) }}</n-tag>
          </div>
          <div class="list-row__meta">
            {{ task.assignee_name || "未分配" }} · {{ statusLabel(task.status) }} · {{ task.due_date ? `截止 ${task.due_date}` : "无截止日期" }}
            <template v-if="task.github_issue_number"> · Issue #{{ task.github_issue_number }}</template>
            <template v-if="task.github_pr_number"> · PR #{{ task.github_pr_number }}</template>
          </div>
          <n-progress class="task-progress" type="line" :percentage="task.progress" :height="6" :show-indicator="false" />
        </div>
        <n-button v-if="canUpdate(task)" size="small" @click="openUpdate(task)">更新</n-button>
      </article>
    </section>

    <section class="surface">
      <div class="section-header"><div><h3>里程碑</h3><p>阶段权重独立展示，整体进度仍由任务权重汇总</p></div></div>
      <div v-if="!milestones.length" class="empty-state"><div><strong>暂未建立里程碑</strong>项目负责人可创建交付阶段。</div></div>
      <div v-for="item in milestones" :key="item.id" class="list-row">
        <div class="list-row__main"><div class="list-row__title">{{ item.title }}</div><div class="list-row__meta">{{ statusLabel(item.status) }} · {{ item.due_date || "无截止日期" }}</div></div>
        <n-progress type="line" :percentage="item.progress" style="width: min(240px, 35vw)" />
      </div>
    </section>
    <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>

    <n-modal v-model:show="showTask" preset="card" title="新建任务" class="form-modal">
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item class="span-2" label="任务名称" required><n-input v-model:value="taskForm.title" maxlength="240" /></n-form-item>
          <n-form-item label="负责人"><n-select v-model:value="taskForm.assignee_member_id" clearable :options="memberOptions" /></n-form-item>
          <n-form-item label="里程碑"><n-select v-model:value="taskForm.milestone_id" clearable :options="milestoneOptions" /></n-form-item>
          <n-form-item label="优先级"><n-select v-model:value="taskForm.priority" :options="priorityOptions" /></n-form-item>
          <n-form-item label="截止日期"><n-date-picker v-model:formatted-value="taskForm.due_date" value-format="yyyy-MM-dd" type="date" clearable style="width: 100%" /></n-form-item>
          <n-form-item label="任务权重"><n-input-number v-model:value="taskForm.weight" :min="0.1" :max="1000" style="width: 100%" /></n-form-item>
          <n-form-item label="GitHub Issue"><n-input-number v-model:value="taskForm.github_issue_number" clearable :min="1" style="width: 100%" /></n-form-item>
          <n-form-item label="GitHub PR"><n-input-number v-model:value="taskForm.github_pr_number" clearable :min="1" style="width: 100%" /></n-form-item>
          <n-form-item class="span-2" label="说明"><n-input v-model:value="taskForm.description" type="textarea" :rows="3" maxlength="20000" /></n-form-item>
        </div>
        <n-space justify="end"><n-button @click="showTask = false">取消</n-button><n-button type="primary" :loading="saving" :disabled="!taskForm.title.trim()" @click="createTask">保存任务</n-button></n-space>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showMilestone" preset="card" title="新建里程碑" class="form-modal">
      <n-form label-placement="top">
        <n-form-item label="名称" required><n-input v-model:value="milestoneForm.title" maxlength="200" /></n-form-item>
        <div class="form-grid">
          <n-form-item label="开始日期"><n-date-picker v-model:formatted-value="milestoneForm.start_date" value-format="yyyy-MM-dd" type="date" clearable style="width: 100%" /></n-form-item>
          <n-form-item label="截止日期"><n-date-picker v-model:formatted-value="milestoneForm.due_date" value-format="yyyy-MM-dd" type="date" clearable style="width: 100%" /></n-form-item>
          <n-form-item class="span-2" label="说明"><n-input v-model:value="milestoneForm.description" type="textarea" :rows="3" /></n-form-item>
        </div>
        <n-space justify="end"><n-button @click="showMilestone = false">取消</n-button><n-button type="primary" :loading="saving" :disabled="!milestoneForm.title.trim()" @click="createMilestone">保存里程碑</n-button></n-space>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showUpdate" preset="card" title="更新任务" class="small-modal">
      <n-form label-placement="top">
        <n-form-item label="状态"><n-select v-model:value="updateForm.status" :options="statusOptions" /></n-form-item>
        <n-form-item label="完成度"><n-input-number v-model:value="updateForm.progress" :min="0" :max="100" :step="5" style="width: 100%"><template #suffix>%</template></n-input-number></n-form-item>
        <n-space justify="end"><n-button @click="showUpdate = false">取消</n-button><n-button type="primary" :loading="saving" @click="saveUpdate">保存</n-button></n-space>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NAlert, NButton, NCheckbox, NDatePicker, NForm, NFormItem, NInput, NInputNumber, NModal, NProgress, NSelect, NSkeleton, NSpace, NTag } from "naive-ui";
import api, { errorMessage } from "../api";
import { useProjectStore } from "../store";
import type { Milestone, ProjectTask } from "../types";

const store = useProjectStore();
const loading = ref(true); const saving = ref(false); const error = ref("");
const tasks = ref<ProjectTask[]>([]); const milestones = ref<Milestone[]>([]); const members = ref<any[]>([]);
const mine = ref(false); const statusFilter = ref<string | null>(null);
const showTask = ref(false); const showMilestone = ref(false); const showUpdate = ref(false);
const activeTaskId = ref<number | null>(null);
const taskForm = ref({ title: "", description: "", assignee_member_id: null as number | null, milestone_id: null as number | null, priority: "medium", due_date: null as string | null, weight: 1, github_issue_number: null as number | null, github_pr_number: null as number | null });
const milestoneForm = ref({ title: "", description: "", start_date: null as string | null, due_date: null as string | null });
const updateForm = ref({ status: "in_progress", progress: 0 });
const statusOptions = [
  { label: "待开始", value: "todo" }, { label: "进行中", value: "in_progress" },
  { label: "受阻", value: "blocked" }, { label: "待验收", value: "review" }, { label: "已完成", value: "done" },
];
const priorityOptions = [
  { label: "低", value: "low" }, { label: "中", value: "medium" },
  { label: "高", value: "high" }, { label: "紧急", value: "urgent" },
];
const memberOptions = computed(() => members.value.map((item) => ({ label: item.name, value: item.id })));
const milestoneOptions = computed(() => milestones.value.map((item) => ({ label: item.title, value: item.id })));
const statusLabel = (value: string) => ({ todo: "待开始", in_progress: "进行中", blocked: "受阻", review: "待验收", done: "已完成", planned: "待开始", active: "进行中", completed: "已完成", paused: "已暂停" } as Record<string,string>)[value] || value;
const priorityLabel = (value: string) => ({ low: "低", medium: "中", high: "高", urgent: "紧急" } as Record<string,string>)[value] || value;
const priorityType = (value: string) => value === "urgent" ? "error" : value === "high" ? "warning" : value === "low" ? "default" : "info";
const statusDot = (value: string) => value === "done" ? "status-dot--success" : value === "blocked" ? "status-dot--danger" : value === "review" ? "status-dot--warning" : "";
const canUpdate = (task: ProjectTask) => store.canLead || task.assignee_member_id === store.member?.id;

async function loadTasks() {
  try { tasks.value = (await api.get("/tasks", { params: { mine: mine.value || undefined, status: statusFilter.value || undefined } })).data; }
  catch (reason) { error.value = errorMessage(reason); }
}
async function loadAll() {
  loading.value = true; error.value = "";
  try {
    const [taskRes, milestoneRes, memberRes] = await Promise.all([api.get("/tasks"), api.get("/milestones"), api.get("/members")]);
    tasks.value = taskRes.data; milestones.value = milestoneRes.data; members.value = memberRes.data;
  } catch (reason) { error.value = errorMessage(reason, "任务加载失败"); }
  finally { loading.value = false; }
}
async function createTask() {
  saving.value = true; error.value = "";
  try { await api.post("/tasks", taskForm.value); showTask.value = false; taskForm.value.title = ""; taskForm.value.description = ""; await loadAll(); }
  catch (reason) { error.value = errorMessage(reason, "任务保存失败"); }
  finally { saving.value = false; }
}
async function createMilestone() {
  saving.value = true; error.value = "";
  try { await api.post("/milestones", milestoneForm.value); showMilestone.value = false; milestoneForm.value.title = ""; milestoneForm.value.description = ""; await loadAll(); }
  catch (reason) { error.value = errorMessage(reason, "里程碑保存失败"); }
  finally { saving.value = false; }
}
function openUpdate(task: ProjectTask) { activeTaskId.value = task.id; updateForm.value = { status: task.status, progress: task.progress }; showUpdate.value = true; }
async function saveUpdate() {
  if (!activeTaskId.value) return;
  saving.value = true;
  try { await api.patch(`/tasks/${activeTaskId.value}`, updateForm.value); showUpdate.value = false; await loadTasks(); }
  catch (reason) { error.value = errorMessage(reason, "任务更新失败"); }
  finally { saving.value = false; }
}
onMounted(loadAll);
</script>
<style scoped>
.filter-panel { padding: 14px 18px; }
.task-title-line { display: flex; align-items: center; gap: 8px; }
.task-progress { max-width: 460px; margin-top: 9px; }
.form-modal { width: min(680px, calc(100vw - 24px)); }
.small-modal { width: min(440px, calc(100vw - 24px)); }
@media (max-width: 600px) { .task-row { flex-wrap: wrap; } .task-row > .n-button { width: 100%; } .task-progress { max-width: none; } }
</style>
