<template>
  <div class="org-page">
    <div class="page-heading">
      <div><h1>科室与授权</h1><p>科主任可读取本科患者病历；临时授权按时到期。</p></div>
      <n-button @click="loadAll">刷新数据</n-button>
    </div>
    <n-alert v-if="error" type="error" style="margin-bottom:16px">{{ error }}</n-alert>
    <n-tabs type="line" animated>
      <n-tab-pane name="departments" tab="科室成员">
        <n-card title="科室" size="small">
          <n-space align="center">
            <n-input v-model:value="newDepartment" placeholder="新科室名称" style="width:240px" @keyup.enter="createDepartment" />
            <n-button type="primary" :disabled="!newDepartment.trim()" :loading="saving" @click="createDepartment">创建科室</n-button>
          </n-space>
          <div class="selection"><label>当前科室</label><n-select v-model:value="departmentId" :options="departmentOptions" placeholder="选择科室" style="width:280px" /></div>
        </n-card>
        <n-card v-if="departmentId" title="医师与科主任" size="small" class="section">
          <n-space align="center" class="form-row">
            <n-select v-model:value="memberDoctorId" filterable :options="doctorOptions" placeholder="选择医生" style="width:220px" />
            <n-checkbox v-model:checked="memberIsHead">科主任</n-checkbox>
            <n-button type="primary" :disabled="!memberDoctorId" :loading="saving" @click="saveMember">添加或更新</n-button>
          </n-space>
          <div class="table-wrap">
            <table><thead><tr><th>医生</th><th>身份</th><th>状态</th><th>操作</th></tr></thead>
              <tbody><tr v-for="row in members" :key="row.user_id">
                <td>{{ row.username }}</td><td>{{ row.is_head ? '科主任' : '成员' }}</td><td>{{ row.active ? '在岗' : '停用' }}</td>
                <td><n-button size="small" @click="updateMember(row, { is_head: !row.is_head })">{{ row.is_head ? '取消主任' : '设为主任' }}</n-button>
                    <n-button size="small" style="margin-left:8px" @click="updateMember(row, { active: !row.active })">{{ row.active ? '停用' : '启用' }}</n-button></td>
              </tr><tr v-if="!members.length"><td colspan="4" class="empty">尚无科室成员</td></tr></tbody>
            </table>
          </div>
        </n-card>
      </n-tab-pane>
      <n-tab-pane name="care" tab="诊疗团队">
        <n-card title="选择患者" size="small">
          <n-space align="center">
            <n-select v-model:value="patientId" filterable :options="patientOptions" placeholder="患者编码" style="width:280px" />
            <n-button v-if="hasMorePatients" @click="loadMorePatients">加载更多患者</n-button>
          </n-space>
          <p v-if="selectedPatient" class="hint">主诊科室：{{ departmentName(selectedPatient.primary_department_id) }}</p>
        </n-card>
        <n-card v-if="patientId" title="分配医生" size="small" class="section">
          <n-space align="center" class="form-row">
            <n-select v-model:value="careDoctorId" filterable :options="doctorOptions" placeholder="医生" style="width:180px" />
            <n-select v-model:value="careDepartmentId" :options="departmentOptions" placeholder="所属科室" style="width:180px" />
            <n-checkbox v-model:checked="setPrimary">设为主诊科室</n-checkbox>
            <n-button type="primary" :disabled="!careDoctorId || !careDepartmentId" :loading="saving" @click="saveCare">分配</n-button>
          </n-space>
          <p class="hint">医生须先加入该科室。停用分配后，其相应病例访问权限立即失效。</p>
          <div class="table-wrap">
            <table><thead><tr><th>医生</th><th>科室</th><th>状态</th><th>操作</th></tr></thead>
              <tbody><tr v-for="row in careTeam" :key="row.user_id + '-' + row.department_id">
                <td>{{ row.username }}</td><td>{{ departmentName(row.department_id) }}</td><td>{{ row.active ? '有效' : '停用' }}</td>
                <td><n-button size="small" @click="updateCare(row, !row.active)">{{ row.active ? '停用' : '恢复' }}</n-button></td>
              </tr><tr v-if="!careTeam.length"><td colspan="4" class="empty">尚无诊疗团队</td></tr></tbody>
            </table>
          </div>
        </n-card>
      </n-tab-pane>
      <n-tab-pane name="grants" tab="临时授权">
        <n-card title="选择患者" size="small">
          <n-space align="center">
            <n-select v-model:value="patientId" filterable :options="patientOptions" placeholder="患者编码" style="width:280px" />
            <n-button v-if="hasMorePatients" @click="loadMorePatients">加载更多患者</n-button>
          </n-space>
        </n-card>
        <n-card v-if="patientId" title="发放临时授权" size="small" class="section">
          <n-space align="center" class="form-row">
            <n-select v-model:value="grantDoctorId" filterable :options="doctorOptions" placeholder="获授权医生" style="width:190px" />
            <n-input v-model:value="grantPurpose" placeholder="授权目的" style="width:200px" />
            <n-input-number v-model:value="grantHours" :min="1" :max="720" style="width:135px"><template #suffix>小时</template></n-input-number>
            <n-checkbox v-model:checked="grantCanWrite">允许写入</n-checkbox>
            <n-button type="primary" :disabled="!grantDoctorId || !grantPurpose.trim()" :loading="saving" @click="createGrant">授权</n-button>
          </n-space>
          <p class="hint">默认只读。授权的访问和撤销均记录在审计日志中。</p>
          <div class="table-wrap">
            <table><thead><tr><th>医生</th><th>目的</th><th>权限</th><th>截止时间</th><th>状态</th><th>操作</th></tr></thead>
              <tbody><tr v-for="row in grants" :key="row.id">
                <td>{{ row.grantee_username }}</td><td>{{ row.purpose }}</td><td>{{ row.can_write ? '读写' : '只读' }}</td>
                <td>{{ formatTime(row.expires_at) }}</td><td>{{ grantStatus(row) }}</td>
                <td><n-button v-if="grantStatus(row) === '有效'" size="small" type="warning" @click="revokeGrant(row.id)">撤销</n-button></td>
              </tr><tr v-if="!grants.length"><td colspan="6" class="empty">尚无临时授权</td></tr></tbody>
            </table>
          </div>
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NAlert, NButton, NCard, NCheckbox, NInput, NInputNumber, NSelect, NSpace, NTabPane, NTabs, useMessage } from "naive-ui";
import api from "./api";

type Department = { id: number; name: string };
type Patient = { id: number; patient_code: string; primary_department_id: number | null };
type Member = { user_id: number; username: string; is_head: boolean; active: boolean };
type Care = { user_id: number; username: string; department_id: number; active: boolean };
type Grant = { id: number; grantee_username: string; purpose: string; can_write: boolean; expires_at: string; revoked_at: string | null };
const message = useMessage();
const error = ref("");
const saving = ref(false);
const departments = ref<Department[]>([]);
const doctors = ref<{ id: number; username: string }[]>([]);
const patients = ref<Patient[]>([]);
const hasMorePatients = ref(false);
const departmentId = ref<number | null>(null);
const patientId = ref<number | null>(null);
const members = ref<Member[]>([]);
const careTeam = ref<Care[]>([]);
const grants = ref<Grant[]>([]);
const newDepartment = ref("");
const memberDoctorId = ref<number | null>(null);
const memberIsHead = ref(false);
const careDoctorId = ref<number | null>(null);
const careDepartmentId = ref<number | null>(null);
const setPrimary = ref(false);
const grantDoctorId = ref<number | null>(null);
const grantPurpose = ref("");
const grantHours = ref(24);
const grantCanWrite = ref(false);
const departmentOptions = computed(() => departments.value.map(d => ({ label: d.name, value: d.id })));
const doctorOptions = computed(() => doctors.value.map(d => ({ label: d.username, value: d.id })));
const patientOptions = computed(() => patients.value.map(p => ({ label: p.patient_code, value: p.id })));
const selectedPatient = computed(() => patients.value.find(p => p.id === patientId.value));
function departmentName(id: number | null) { return departments.value.find(d => d.id === id)?.name || "未指定"; }
function formatTime(value: string) { return value ? new Date(value + (value.endsWith("Z") ? "" : "Z")).toLocaleString("zh-CN") : ""; }
function grantStatus(row: Grant) { return row.revoked_at ? "已撤销" : Date.parse(row.expires_at + (row.expires_at.endsWith("Z") ? "" : "Z")) <= Date.now() ? "已到期" : "有效"; }
function showError(e: any) { error.value = e.response?.data?.detail || e.message || "操作失败"; message.error(error.value); }
async function loadAll() {
  error.value = "";
  try {
    const [dept, users, patient] = await Promise.all([
      api.get("/organization/departments"),
      api.get("/auth/users", { params: { role: "doctor" } }),
      api.get("/organization/patients", { params: { limit: 100, offset: 0 } }),
    ]);
    departments.value = dept.data;
    doctors.value = users.data;
    patients.value = patient.data;
    hasMorePatients.value = patient.data.length === 100;
    if (departmentId.value) await loadMembers();
    if (patientId.value) await loadPatient();
  } catch (e) { showError(e); }
}
async function loadMorePatients() {
  try {
    const { data } = await api.get("/organization/patients", { params: { limit: 100, offset: patients.value.length } });
    patients.value.push(...data);
    hasMorePatients.value = data.length === 100;
  } catch (e) { showError(e); }
}
async function loadMembers() {
  if (!departmentId.value) { members.value = []; return; }
  try { members.value = (await api.get("/organization/departments/" + departmentId.value + "/members")).data; }
  catch (e) { showError(e); }
}
async function loadPatient() {
  if (!patientId.value) { careTeam.value = []; grants.value = []; return; }
  try {
    const [care, currentGrants] = await Promise.all([
      api.get("/organization/patients/" + patientId.value + "/care-team"),
      api.get("/organization/patients/" + patientId.value + "/grants"),
    ]);
    careTeam.value = care.data; grants.value = currentGrants.data;
  } catch (e) { showError(e); }
}
async function run(action: () => Promise<any>, refresh: () => Promise<any>) {
  saving.value = true; error.value = "";
  try { await action(); await refresh(); message.success("已保存"); }
  catch (e) { showError(e); }
  finally { saving.value = false; }
}
function createDepartment() {
  const name = newDepartment.value.trim();
  if (!name) return;
  run(() => api.post("/organization/departments", { name }), async () => { newDepartment.value = ""; await loadAll(); });
}
function saveMember() {
  if (!departmentId.value || !memberDoctorId.value) return;
  run(() => api.put('/organization/departments/' + departmentId.value + '/members/' + memberDoctorId.value,
    { is_head: memberIsHead.value, active: true }), loadMembers);
}
function updateMember(row: Member, changes: Partial<Member>) {
  run(() => api.put('/organization/departments/' + departmentId.value + '/members/' + row.user_id,
    { is_head: row.is_head, active: row.active, ...changes }), loadMembers);
}
function saveCare() {
  if (!patientId.value || !careDoctorId.value || !careDepartmentId.value) return;
  run(() => api.put('/organization/patients/' + patientId.value + '/care-team/' + careDoctorId.value,
    { department_id: careDepartmentId.value, active: true, set_primary: setPrimary.value }), loadAll);
}
function updateCare(row: Care, active: boolean) {
  run(() => api.put('/organization/patients/' + patientId.value + '/care-team/' + row.user_id,
    { department_id: row.department_id, active }), loadPatient);
}
function createGrant() {
  if (!patientId.value || !grantDoctorId.value || !grantPurpose.value.trim()) return;
  run(() => api.post('/organization/patients/' + patientId.value + '/grants', {
    grantee_user_id: grantDoctorId.value, purpose: grantPurpose.value.trim(),
    hours: grantHours.value, can_write: grantCanWrite.value,
  }), async () => { grantPurpose.value = ""; await loadPatient(); });
}
function revokeGrant(id: number) { run(() => api.delete("/organization/grants/" + id), loadPatient); }
watch(departmentId, loadMembers);
watch(patientId, loadPatient);
onMounted(loadAll);
</script>
<style scoped>
.org-page { max-width: 1200px; }
.page-heading { display:flex; justify-content:space-between; align-items:start; gap:16px; margin-bottom:18px; }
h1 { font-size:20px; margin:0 0 4px; color:#1e293b; }
.page-heading p, .hint { color:#64748b; font-size:13px; margin:6px 0 0; }
.section { margin-top:16px; }
.selection { display:flex; align-items:center; gap:12px; margin-top:20px; }
.selection label { color:#475569; font-size:13px; }
.form-row { margin-bottom:16px; }
.table-wrap { overflow-x:auto; margin-top:16px; }
table { border-collapse:collapse; width:100%; min-width:600px; font-size:13px; background:#fff; }
th,td { padding:11px 12px; text-align:left; border-bottom:1px solid #e2e8f0; }
th { background:#f8fafc; color:#475569; font-weight:600; }
.empty { text-align:center; color:#64748b; padding:24px; }
</style>
