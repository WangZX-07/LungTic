<template>
  <div class="page-stack">
    <header class="page-heading"><div><h2>项目设置</h2><p>仅影响 LungTic 项目门户，不会授予任何临床系统或病例权限。</p></div></header>

    <section class="metric-strip integration-strip" v-if="integrations">
      <div class="metric-item"><span>飞书身份</span><strong class="integration-value"><span class="status-dot" :class="integrations.feishu.configured ? 'status-dot--success' : 'status-dot--danger'" />{{ integrations.feishu.configured ? "已配置" : "未配置" }}</strong></div>
      <div class="metric-item"><span>GitHub Webhook</span><strong class="integration-value"><span class="status-dot" :class="integrations.github.configured ? 'status-dot--success' : 'status-dot--danger'" />{{ integrations.github.configured ? "已配置" : "未配置" }}</strong></div>
      <div class="metric-item integration-wide"><span>同步仓库</span><strong class="integration-value">{{ integrations.github.repository || "未设置" }}</strong></div>
    </section>

    <section class="surface">
      <div class="section-header"><div><h3>飞书部门与职位映射</h3><p>数值越大优先级越高；同一规则内的多个条件需同时满足</p></div><n-button type="primary" @click="showRule = true">新增规则</n-button></div>
      <n-skeleton v-if="loading" text :repeat="5" />
      <div v-else-if="!rules.length" class="empty-state"><div><strong>尚未配置自动映射</strong>创建规则后，成员下次登录会按飞书部门与职位获得角色。</div></div>
      <div v-for="rule in rules" :key="rule.id" class="rule-row list-row">
        <span class="status-dot" :class="rule.active ? 'status-dot--success' : ''" />
        <div class="list-row__main"><div class="list-row__title">{{ rule.name }} · {{ roleLabel(rule.role) }}</div><div class="list-row__meta">{{ rule.department_id ? `部门 ${rule.department_id}` : "任意部门" }} · {{ rule.job_title_id || rule.job_title_name ? `职位 ${rule.job_title_id || rule.job_title_name}` : "任意职位" }} · 优先级 {{ rule.priority }}</div></div>
        <n-popconfirm @positive-click="deleteRule(rule.id)"><template #trigger><n-button size="small" tertiary type="error">删除</n-button></template>删除后将立即重新计算全部成员的自动角色，确认继续？</n-popconfirm>
      </div>
    </section>

    <section class="surface">
      <div class="section-header"><div><h3>项目成员</h3><p>手动角色优先于自动映射；GitHub 账号用于关联代码动态</p></div></div>
      <div v-if="!members.length && !loading" class="empty-state"><div><strong>还没有成员登录</strong>成员首次通过飞书登录后会出现在这里。</div></div>
      <div v-for="member in members" :key="member.id" class="member-row list-row">
        <n-avatar round :size="36" :src="member.avatar_url || undefined">{{ member.name.slice(0, 1) }}</n-avatar>
        <div class="member-identity">
          <strong>{{ member.name }}</strong>
          <span>{{ positionSummary(member) }} · 自动角色 {{ roleLabel(member.mapped_role) }}</span>
          <div v-if="member.department_ids.length" class="member-departments">
            <code v-for="departmentId in member.department_ids" :key="departmentId">{{ departmentId }}</code>
            <n-button size="tiny" text type="primary" @click="copyDepartmentIds(member)">复制部门 ID</n-button>
          </div>
          <span v-else class="sync-warning">部门也未同步：请检查通讯录权限、应用可用范围，并让成员重新登录</span>
        </div>
        <n-select :value="member.manual_role || null" clearable placeholder="使用自动映射" :options="roleOptions" style="width: 150px" @update:value="(value) => updateMember(member.id, { manual_role: value })" />
        <n-input v-model:value="draftGithub[member.id]" placeholder="GitHub 登录名" style="width: 170px" @keyup.enter="saveGithub(member.id)" />
        <n-button size="small" :loading="savingMember === member.id" @click="saveGithub(member.id)">保存</n-button>
      </div>
    </section>
    <n-alert v-if="message" :type="messageType" :show-icon="true">{{ message }}</n-alert>

    <n-modal v-model:show="showRule" preset="card" title="新增权限映射规则" class="project-modal project-modal--standard">
      <n-form label-placement="top">
        <n-form-item label="规则名称" required><n-input v-model:value="ruleForm.name" maxlength="128" placeholder="例如：研发部项目成员" /></n-form-item>
        <div class="form-grid">
          <n-form-item label="飞书部门 open_department_id"><n-input v-model:value="ruleForm.department_id" placeholder="od-...（从成员列表复制）" /></n-form-item>
          <n-form-item label="飞书职位 ID"><n-input v-model:value="ruleForm.job_title_id" placeholder="职位 ID，不能填写 od-..." /></n-form-item>
          <n-form-item label="职位名称"><n-input v-model:value="ruleForm.job_title_name" placeholder="无职位 ID 时可按完整名称匹配" /></n-form-item>
          <n-form-item label="项目角色"><n-select v-model:value="ruleForm.role" :options="roleOptions" /></n-form-item>
          <n-form-item label="优先级"><n-input-number v-model:value="ruleForm.priority" :min="-100000" :max="100000" style="width: 100%" /></n-form-item>
        </div>
        <n-alert type="info" :bordered="false">至少填写一个匹配条件。部门 ID 必须是本页成员信息中的 od-...；同一规则填写多个条件时，成员必须同时满足。</n-alert>
        <n-space justify="end" style="margin-top: 18px"><n-button @click="showRule = false">取消</n-button><n-button type="primary" :loading="saving" :disabled="!ruleForm.name.trim()" @click="createRule">保存规则</n-button></n-space>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { NAlert, NAvatar, NButton, NForm, NFormItem, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSkeleton, NSpace } from "naive-ui";
import api, { errorMessage } from "../api";
import type { ProjectMember } from "../types";
const loading = ref(true); const saving = ref(false); const savingMember = ref<number | null>(null); const showRule = ref(false);
const integrations = ref<any>(null); const rules = ref<any[]>([]); const members = ref<ProjectMember[]>([]); const draftGithub = reactive<Record<number,string>>({});
const message = ref(""); const messageType = ref<"success" | "error">("success");
const roleOptions = [
  { label: "项目管理员", value: "project_admin" }, { label: "项目负责人", value: "project_lead" },
  { label: "小组负责人", value: "team_lead" }, { label: "项目成员", value: "contributor" }, { label: "观察者", value: "observer" },
];
const ruleForm = ref({ name: "", department_id: "", job_title_id: "", job_title_name: "", role: "contributor", priority: 100, active: true });
const roleLabel = (value: string) => ({ project_admin: "项目管理员", project_lead: "项目负责人", team_lead: "小组负责人", contributor: "项目成员", observer: "观察者", unassigned: "未分配" } as Record<string,string>)[value] || value;
const positionSummary = (member: ProjectMember) => member.job_title_name || member.job_title_id || (member.department_ids.length ? "飞书资料未填写职位" : "职位未同步");
async function load() {
  loading.value = true; message.value = "";
  try {
    const [integrationRes, ruleRes, memberRes] = await Promise.all([api.get("/admin/integrations"), api.get("/admin/role-rules"), api.get("/admin/members")]);
    integrations.value = integrationRes.data; rules.value = ruleRes.data; members.value = memberRes.data;
    members.value.forEach((member) => { draftGithub[member.id] = member.github_login || ""; });
  } catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "项目设置加载失败"); }
  finally { loading.value = false; }
}
async function createRule() {
  const departmentId = ruleForm.value.department_id.trim();
  const jobTitleId = ruleForm.value.job_title_id.trim();
  const jobTitleName = ruleForm.value.job_title_name.trim();
  if (!departmentId && !jobTitleId && !jobTitleName) { messageType.value = "error"; message.value = "至少填写部门 ID、职位 ID 或职位名称之一。"; return; }
  if (departmentId && !departmentId.startsWith("od-")) { messageType.value = "error"; message.value = "部门 ID 应是以 od- 开头的 open_department_id。"; return; }
  if (jobTitleId.startsWith("od-")) { messageType.value = "error"; message.value = "od-... 是部门 ID，请填写到左侧的部门字段。"; return; }
  saving.value = true; message.value = "";
  try {
    await api.post("/admin/role-rules", { ...ruleForm.value, department_id: departmentId || null, job_title_id: jobTitleId || null, job_title_name: jobTitleName || null });
    showRule.value = false; ruleForm.value = { name: "", department_id: "", job_title_id: "", job_title_name: "", role: "contributor", priority: 100, active: true };
    messageType.value = "success"; message.value = "映射规则已创建。"; await load();
  } catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "规则保存失败"); }
  finally { saving.value = false; }
}
async function deleteRule(id: number) { try { await api.delete(`/admin/role-rules/${id}`); await load(); } catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "规则删除失败"); } }
async function updateMember(id: number, patch: Record<string, unknown>) {
  savingMember.value = id;
  try { await api.patch(`/admin/members/${id}`, patch); await load(); }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "成员更新失败"); }
  finally { savingMember.value = null; }
}
async function saveGithub(id: number) { await updateMember(id, { github_login: draftGithub[id] || null }); }
async function copyDepartmentIds(member: ProjectMember) {
  try {
    await navigator.clipboard.writeText(member.department_ids.join("\n"));
    messageType.value = "success"; message.value = `${member.name} 的部门 ID 已复制。`;
  } catch {
    messageType.value = "error"; message.value = "浏览器未允许复制，请手动选中部门 ID。";
  }
}
onMounted(load);
</script>
<style scoped>
.integration-strip { grid-template-columns: 1fr 1fr 2fr; }
.integration-value { display: flex !important; align-items: center; gap: 8px; font-size: 16px !important; line-height: 24px !important; overflow-wrap: anywhere; }
.member-row { align-items: center; }
.member-identity { min-width: 180px; flex: 1; display: flex; flex-direction: column; }
.member-identity strong { color: #1e293b; font-size: 13px; }
.member-identity span { color: #64748b; font-size: 11px; }
.member-departments { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.member-departments code { max-width: 290px; padding: 2px 6px; border-radius: 4px; background: #f1f5f9; color: #334155; font-size: 11px; overflow-wrap: anywhere; }
.member-identity .sync-warning { color: #b45309; margin-top: 3px; }
@media (max-width: 900px) { .integration-strip { grid-template-columns: 1fr 1fr; } .integration-wide { grid-column: 1 / -1; border-left: 0 !important; border-top: 1px solid var(--color-border); } .member-row { flex-wrap: wrap; } .member-identity { min-width: calc(100% - 54px); } .member-row > .n-select, .member-row > .n-input { flex: 1; width: auto !important; min-width: 140px; } }
@media (max-width: 520px) { .integration-strip { grid-template-columns: 1fr; } .integration-strip .metric-item { border-left: 0; border-top: 1px solid var(--color-border); } .integration-strip .metric-item:first-child { border-top: 0; } .integration-wide { grid-column: auto; } .member-row > .n-select, .member-row > .n-input, .member-row > .n-button { width: 100% !important; } }
</style>
