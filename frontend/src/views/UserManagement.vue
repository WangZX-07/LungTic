<template>
  <div class="user-management">
    <div class="page-heading">
      <h2 style="font-size:20px">用户管理</h2>
      <div class="page-actions">
        <n-button type="primary" @click="openAddModal">
          <template #icon><n-icon><PersonAddOutline /></n-icon></template>
          添加用户
        </n-button>
        <n-upload class="batch-upload" accept=".csv" :show-file-list="false" :custom-request="handleCsvUpload">
          <n-button>
            <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
            批量导入 CSV
          </n-button>
        </n-upload>
      </div>
    </div>

    <n-card size="small" style="margin-bottom:16px">
      <n-space align="center">
        <span>筛选角色：</span>
        <n-select v-model:value="filterRole" :options="roleFilterOptions" clearable style="width:140px" size="small" @update:value="fetchUsers" />
        <n-button size="small" @click="fetchUsers">刷新</n-button>
      </n-space>
    </n-card>

    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="users"
        :row-key="(row: any) => row.id"
        :bordered="false"
        :single-line="false"
        striped
        :scroll-x="1100"
        class="users-table"
      />
    </n-spin>

    <!-- Add user modal -->
    <n-modal v-model:show="showAddModal" preset="card" title="添加用户" style="width:min(480px, calc(100vw - 24px))">
      <n-form ref="addFormRef" :model="addForm" :rules="addRules" label-placement="left" label-width="80">
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="addForm.username" placeholder="登录用户名" />
        </n-form-item>
        <n-form-item path="password" label="密码">
          <n-input v-model:value="addForm.password" type="password" placeholder="至少6位" />
        </n-form-item>
        <n-form-item path="role" label="角色">
          <n-select v-model:value="addForm.role" :options="editRoleOptions" />
        </n-form-item>
        <n-form-item label="患者编码">
          <n-input v-model:value="addForm.patient_code" placeholder="仅患者角色需要" />
        </n-form-item>
        <n-form-item label="邮箱">
          <n-input v-model:value="addForm.email" placeholder="用于密码重置" />
        </n-form-item>
        <n-form-item label="手机号">
          <n-input v-model:value="addForm.phone" placeholder="联系方式" />
        </n-form-item>
        <n-space justify="end">
          <n-button @click="showAddModal = false">取消</n-button>
          <n-button type="primary" :loading="adding" @click="handleAddUser">添加</n-button>
        </n-space>
      </n-form>
    </n-modal>

    <!-- Edit user modal -->
    <n-modal v-model:show="showEditModal" preset="card" title="编辑用户" style="width:min(480px, calc(100vw - 24px))">
      <n-form v-if="editingUser" :model="editForm" label-placement="left" label-width="80">
        <n-form-item label="用户名">
          <n-input :value="editingUser.username" disabled />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="editForm.role" :options="editRoleOptions" />
        </n-form-item>
        <n-form-item label="患者编码">
          <n-input v-model:value="editForm.patient_code" placeholder="仅患者角色需要" />
        </n-form-item>
        <n-form-item label="邮箱">
          <n-input v-model:value="editForm.email" placeholder="用于密码重置" />
        </n-form-item>
        <n-form-item label="手机号">
          <n-input v-model:value="editForm.phone" placeholder="联系方式" />
        </n-form-item>
        <n-space justify="end">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSaveUser">保存</n-button>
        </n-space>
      </n-form>
    </n-modal>

    <!-- Batch result modal -->
    <n-modal v-model:show="showBatchResult" preset="card" title="导入结果" style="width:min(560px, calc(100vw - 24px))">
      <div v-if="batchResult">
        <p>成功创建 <b>{{ batchResult.created }}</b> 个用户</p>
        <div v-if="batchResult.errors.length > 0" style="margin-top:12px">
          <p style="color:#EF4444">错误 ({{ batchResult.errors.length }})：</p>
          <ul class="error-list">
            <li v-for="(err, i) in batchResult.errors" :key="i">{{ err }}</li>
          </ul>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from "vue";
import {
  NSpace, NButton, NIcon, NUpload, NSpin, NDataTable, NCard, NSelect, NModal, NTag, NForm, NFormItem, NInput,
  useMessage, useDialog,
} from "naive-ui";
import { PersonAddOutline, CloudUploadOutline } from "@vicons/ionicons5";
import type { DataTableColumns } from "naive-ui";
import api from "@/admin/api";

const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const users = ref<any[]>([]);
const filterRole = ref<string | null>(null);
const showBatchResult = ref(false);
const batchResult = ref<any>(null);

// Add modal
const showAddModal = ref(false);
const adding = ref(false);
const addFormRef = ref<any>(null);
const addForm = ref({ username: "", password: "", role: "doctor", patient_code: "", email: "", phone: "" });
const addRules = {
  username: { required: true, message: "请输入用户名", trigger: "blur" },
  password: { required: true, min: 6, message: "密码至少6位", trigger: "blur" },
  role: { required: true, message: "请选择角色", trigger: "blur" },
};

// Edit modal
const showEditModal = ref(false);
const editingUser = ref<any>(null);
const saving = ref(false);
const editForm = ref({ role: "", patient_code: "", email: "", phone: "" });

const editRoleOptions = [
  { label: "医生", value: "doctor" },
  { label: "患者", value: "patient" },
  { label: "管理员", value: "admin" },
];

const roleFilterOptions = [
  { label: "医生", value: "doctor" },
  { label: "患者", value: "patient" },
  { label: "管理员", value: "admin" },
];

const columns: DataTableColumns<any> = [
  { title: "ID", key: "id", width: 60 },
  { title: "用户名", key: "username", ellipsis: { tooltip: true } },
  { title: "角色", key: "role", width: 80,
    render(row: any) {
      const roleMap: Record<string, { type: any; label: string }> = {
        admin: { type: "error", label: "管理员" },
        doctor: { type: "info", label: "医生" },
        patient: { type: "success", label: "患者" },
      };
      const r = roleMap[row.role] || { type: "default", label: row.role };
      return h(NTag, { size: "small", type: r.type, bordered: false }, r.label);
    },
  },
  { title: "患者编码", key: "patient_code", width: 120 },
  { title: "邮箱", key: "email", ellipsis: { tooltip: true }, width: 180 },
  { title: "手机号", key: "phone", width: 120 },
  { title: "创建时间", key: "created_at", width: 160 },
  {
    title: "操作", key: "actions", width: 160, align: "center",
    render(row: any) {
      return h(NSpace, { size: 4 }, [
        h(NButton, { size: "tiny", onClick: () => handleResetPassword(row) }, "重置密码"),
        h(NButton, { size: "tiny", type: "warning", onClick: () => handleEditUser(row) }, "编辑"),
        h(NButton, { size: "tiny", type: "error", onClick: () => handleDeleteUser(row) }, "删除"),
      ]);
    },
  },
];

async function fetchUsers() {
  loading.value = true;
  try {
    const res = await api.get("/auth/users", { params: filterRole.value ? { role: filterRole.value } : {} });
    users.value = res.data;
  } catch { users.value = []; }
  finally { loading.value = false; }
}

function openAddModal() {
  addForm.value = { username: "", password: "", role: "doctor", patient_code: "", email: "", phone: "" };
  showAddModal.value = true;
}

async function handleAddUser() {
  adding.value = true;
  try {
    await api.post("/auth/users", {
      username: addForm.value.username,
      password: addForm.value.password,
      role: addForm.value.role,
      patient_code: addForm.value.patient_code || undefined,
      email: addForm.value.email || undefined,
      phone: addForm.value.phone || undefined,
    });
    message.success("用户创建成功");
    showAddModal.value = false;
    fetchUsers();
  } catch (e: any) {
    message.error(e.response?.data?.detail || "创建失败");
  } finally { adding.value = false; }
}

function handleEditUser(row: any) {
  editingUser.value = row;
  editForm.value = { role: row.role || "", patient_code: row.patient_code || "", email: row.email || "", phone: row.phone || "" };
  showEditModal.value = true;
}

async function handleSaveUser() {
  if (!editingUser.value) return;
  saving.value = true;
  try {
    await api.put(`/auth/users/${editingUser.value.id}`, {
      role: editForm.value.role || undefined,
      patient_code: editForm.value.patient_code || undefined,
      email: editForm.value.email || undefined,
      phone: editForm.value.phone || undefined,
    });
    message.success("保存成功");
    showEditModal.value = false;
    fetchUsers();
  } catch (e: any) {
    message.error(e.response?.data?.detail || "保存失败");
  } finally { saving.value = false; }
}

async function handleDeleteUser(row: any) {
  dialog.warning({
    title: "确认删除",
    content: `确定要删除用户"${row.username}"吗？此操作不可撤销。`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try { await api.delete(`/auth/users/${row.id}`); message.success("删除成功"); fetchUsers(); }
      catch (e: any) { message.error(e.response?.data?.detail || "删除失败"); }
    },
  });
}

async function handleResetPassword(row: any) {
  if (!row.email) { message.warning("该用户未设置邮箱"); return; }
  try { await api.post("/auth/reset-password", { email: row.email }); message.success(`密码重置邮件已发送至 ${row.email}`); }
  catch (e: any) { message.error(e.response?.data?.detail || "发送失败"); }
}

async function handleCsvUpload({ file, onFinish, onError }: any) {
  const rawFile = file.file as File;
  if (!rawFile) { onError(); return; }
  const formData = new FormData();
  formData.append("file", rawFile);
  try {
    const res = await api.post("/auth/batch-create", formData);
    batchResult.value = res.data;
    showBatchResult.value = true;
    message.success(`成功创建 ${res.data.created} 个用户`);
    fetchUsers();
    onFinish();
  } catch (e: any) { message.error(e.response?.data?.detail || "导入失败"); onError(); }
}

onMounted(fetchUsers);
</script>

<style scoped>
.user-management { max-width: 1100px; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 24px; }
.page-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.users-table { background: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; }
.users-table :deep(.n-data-table-th) { background: #F8FAFC; font-weight: 600; }
.error-list { max-height: 200px; overflow-y: auto; font-size: 12px; color: #EF4444; padding-left: 20px; }
.error-list li { margin-bottom: 2px; }
@media (max-width: 640px) {
  .page-heading { align-items: flex-start; flex-direction: column; margin-bottom: 16px; }
  .page-actions { width: 100%; }
  .page-actions > :deep(.n-button), .batch-upload { flex: 1 1 140px; }
  .batch-upload :deep(.n-upload-trigger), .batch-upload :deep(.n-button) { width: 100%; }
  .users-table { max-width: calc(100vw - 24px); }
}
@media (pointer: coarse) {
  .page-actions :deep(.n-button), .users-table :deep(.n-button) { min-height: 44px; }
}
</style>
