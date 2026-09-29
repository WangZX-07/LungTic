<template>
  <div class="patient-list">
    <!-- Doctor/Admin view -->
    <template v-if="!auth.isPatient">
      <n-space justify="space-between" align="center" style="margin-bottom:24px">
        <h2 style="font-size:20px">患者列表</h2>
        <n-space>
          <n-input v-if="auth.isDoctor && !auth.isAdmin" v-model:value="overridePatientId" placeholder="患者编码" style="width:180px" size="small" clearable />
          <n-button v-if="auth.isDoctor && !auth.isAdmin" size="small" @click="createPatient">创建病例</n-button>
          <n-upload v-if="auth.isDoctor && !auth.isAdmin" accept=".dcm,.nii,.nii.gz,.tici" :show-file-list="true" :custom-request="handleFileUpload">
            <n-button type="primary"><template #icon><n-icon><CloudUploadOutline /></n-icon></template>上传单个文件</n-button>
          </n-upload>
          <input
            v-if="auth.isDoctor && !auth.isAdmin"
            ref="folderInput"
            class="folder-input"
            type="file"
            accept=".dcm"
            multiple
            webkitdirectory
            directory
            @change="handleFolderSelection"
          />
          <n-button
            v-if="auth.isDoctor && !auth.isAdmin"
            type="info"
            :loading="folderUploading"
            :disabled="folderUploading"
            @click="chooseDicomFolder"
          >
            <template #icon><n-icon><FolderOpenOutline /></n-icon></template>
            {{ folderUploading ? `正在上传 ${folderFileCount} 个文件（${folderUploadProgress}%）` : "上传 DICOM 文件夹" }}
          </n-button>
        </n-space>
      </n-space>
      <n-spin :show="loading">
        <div v-if="patients.length === 0 && !loading" class="empty">
          <n-icon size="48" color="#CBD5E1"><FolderOpenOutline /></n-icon>
          <p>暂无患者数据</p>
          <p class="hint">{{ auth.isAdmin ? "管理员管理科室与成员后，由医师上传病例。" : "创建病例或上传 DICOM / NIfTI / TICI 文件以开始分析。" }}</p>
        </div>
        <n-data-table v-else :columns="doctorColumns" :data="patients" :row-key="(row: any) => row.id" :row-props="getRowProps" :bordered="false" :single-line="false" striped class="patients-table" />
      </n-spin>
      <n-drawer v-model:show="showDetail" :width="520" placement="right">
        <n-drawer-content v-if="selectedPatient" :title="selectedPatient.patient_code" closable>
          <n-card size="small" title="患者信息" style="margin-bottom:16px">
            <n-space vertical :size="4">
              <div class="detail-row"><span class="detail-label">编码</span><span>{{ selectedPatient.patient_code }}</span></div>
              <div class="detail-row"><span class="detail-label">性别</span><span>{{ selectedPatient.gender || "未知" }}</span></div>
              <div class="detail-row" v-if="selectedPatient.doctor_name"><span class="detail-label">医生</span><span>{{ selectedPatient.doctor_name }}</span></div>
            </n-space>
          </n-card>
          <h4 class="section-label">检查记录 ({{ selectedStudies.length }})</h4>
          <n-list v-if="selectedStudies.length > 0" hoverable clickable>
            <n-list-item v-for="s in selectedStudies" :key="s.id">
              <n-thing>
                <template #header>
                  <n-space justify="space-between" align="center">
                    <span>Study {{ (s.study_uid || "").substring(0, 16) }}...</span>
                    <n-space :size="4">
                      <n-tag size="tiny" :bordered="false" type="info">{{ s.phase_count || 0 }} 时相</n-tag>
                      <n-tag v-if="s.has_tici" size="tiny" :bordered="false" type="success">TICI OK</n-tag>
                    </n-space>
                  </n-space>
                </template>
                <template #description>
                  <n-space :size="8">
                    <span>{{ s.study_date || "日期未知" }}</span>
                  </n-space>
                </template>
                <template #action>
                  <n-space :size="4">
                    <n-button size="tiny" @click.stop="openStudy(s.id)">浏览</n-button>
                    <n-button size="tiny" type="info" @click.stop="downloadTici(s.id)" :disabled="!s.has_tici">下载 TICI</n-button>
                    <n-button size="tiny" @click.stop="viewTiciInfo(s.id)">TICI 信息</n-button>
                  </n-space>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无检查记录" style="margin-top:24px" />
          <ClinicalRecords :patient-id="selectedPatient.id" />
        </n-drawer-content>
      </n-drawer>
    </template>

    <!-- Patient view -->
    <template v-else>
      <n-space justify="space-between" align="center" style="margin-bottom:24px">
        <h2 style="font-size:20px">我的检查</h2>

      </n-space>
      <n-card size="small" style="margin-bottom:16px">
        <n-space align="center" :size="24">
          <div class="detail-row"><span class="detail-label">编码</span><span>{{ patientInfo?.patient_code || "-" }}</span></div>
          <div class="detail-row"><span class="detail-label">性别</span><span>{{ patientInfo?.gender || "未知" }}</span></div>
          <div class="detail-row"><span class="detail-label">检查数</span><n-tag size="tiny" :bordered="false" type="info">{{ myStudies.length }}</n-tag></div>
        </n-space>
      </n-card>
      <n-card title="我的医生" size="small" style="margin-bottom:16px">
        <div v-if="myDoctors.length === 0" class="text-muted">暂无关聨医生</div>
        <n-space v-else><n-tag v-for="d in myDoctors" :key="d.id" type="info" size="small">{{ d.username }}</n-tag></n-space>
      </n-card>
      <h4 class="section-label">检查记录 ({{ myStudies.length }})</h4>
      <n-spin :show="loading">
        <n-list v-if="myStudies.length > 0" hoverable clickable>
          <n-list-item v-for="s in myStudies" :key="s.id" @click="openStudy(s.id)">
            <n-thing>
              <template #header>
                <n-space justify="space-between">
                  <span>Study {{ (s.study_uid || "").substring(0, 16) }}...</span>
                  <n-tag v-if="s.has_tici" size="tiny" :bordered="false" type="success">TICI</n-tag>
                </n-space>
              </template>
              <template #description><n-space :size="8"><span>{{ s.study_date || "日期未知" }}</span><n-tag size="tiny" :bordered="false" type="info">{{ s.phase_count || 0 }} 时相</n-tag></n-space></template>
            </n-thing>
          </n-list-item>
        </n-list>
        <n-empty v-else description="暂无检查记录" />
      </n-spin>
      <ClinicalRecords v-if="patientInfo" :patient-id="patientInfo.id" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from "vue";
import { useRouter } from "vue-router";
import { NSpace, NButton, NIcon, NUpload, NSpin, NDataTable, NDrawer, NDrawerContent, NList, NListItem, NThing, NEmpty, NTag, NCard, NInput, useMessage } from "naive-ui";
import { CloudUploadOutline, FolderOpenOutline } from "@vicons/ionicons5";
import ClinicalRecords from "@/components/ClinicalRecords.vue";
import type { DataTableColumns } from "naive-ui";
import api from "@/api";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const message = useMessage();
const auth = useAuthStore();

const loading = ref(false);
const patients = ref<any[]>([]);
const showDetail = ref(false);
const selectedPatient = ref<any>(null);
const selectedStudies = ref<any[]>([]);
const overridePatientId = ref("");
const folderInput = ref<HTMLInputElement | null>(null);
const folderUploading = ref(false);
const folderFileCount = ref(0);
const folderUploadProgress = ref(0);

const patientInfo = ref<any>(null);
const myStudies = ref<any[]>([]);
const myDoctors = ref<any[]>([]);

const doctorColumns: DataTableColumns<any> = [
  { title: "患者编码", key: "patient_code", ellipsis: { tooltip: true } },
  { title: "性别", key: "gender", width: 60 },
  { title: "医生", key: "doctor_name", width: 80 },
  { title: "检查数", key: "study_count", width: 80, align: "center" },
  { title: "创建时间", key: "created_at", width: 160 },
  { title: "操作", key: "actions", width: 80, align: "center", render(row: any) { return h(NButton, { size: "small", onClick: () => openPatient(row) }, "查看"); } },
];

function getRowProps(row: any) { return { style: "cursor: pointer", onClick: () => openPatient(row) }; }

async function fetchPatients() {
  loading.value = true;
  try { const res = await api.get("/dicom/patients"); patients.value = res.data; } finally { loading.value = false; }
}

async function createPatient() {
  const code = overridePatientId.value.trim();
  if (!code) { message.warning("请输入患者编码"); return; }
  try {
    await api.post("/patients", { patient_code: code });
    message.success("病例已创建");
    await fetchPatients();
    overridePatientId.value = "";
  } catch {
    message.error("创建失败：请检查编码是否已存在及科室分配");
  }
}

async function openPatient(patient: any) {
  selectedPatient.value = patient;
  try { const res = await api.get(`/dicom/patients/${patient.id}/studies`); selectedStudies.value = res.data; showDetail.value = true; } catch { message.error("获取检查记录失败"); }
}

function openStudy(studyId: number) { showDetail.value = false; router.push(`/dashboard/study/${studyId}`); }

async function downloadTici(studyId: number) {
  try {
    const res = await api.get(`/tici/download/${studyId}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `study_${studyId}.tici`;
    a.click();
    URL.revokeObjectURL(url);
    message.success("下载成功");
  } catch {
    message.error("下载失败，请先导出 TICI 文件");
  }
}

async function viewTiciInfo(studyId: number) {
  try {
    const res = await api.get(`/tici/info/${studyId}`);
    if (res.data?.status === "ready") {
      const info = res.data;
      message.info(
        `TICI v${info.format_version} | ${info.study.phase_count} 时相 | ${formatFileSize(info.file_size_bytes)}`
      );
    } else {
      message.warning("尚未导出 TICI 文件");
    }
  } catch {
    message.warning("无法获取 TICI 信息");
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function handleFileUpload({ file, onFinish, onError }: any) {
  const rawFile = file.file as File;
  if (!rawFile) { onError(); return; }
  const formData = new FormData();

  const isTici = rawFile.name.toLowerCase().endsWith(".tici");
  if (isTici) {
    // TICI import
    formData.append("file", rawFile);
    if (overridePatientId.value) formData.append("patient_code_override", overridePatientId.value);
    try {
      const res = await api.post("/tici/import", formData);
      message.success(`TICI 导入成功: Study #${res.data.study_id} (${res.data.phase_count} 时相)`);
      if (auth.isPatient) fetchMyData(); else fetchPatients();
      onFinish();
    } catch (e: any) {
      message.error(`TICI 导入失败: ${rawFile.name}`);
      onError();
    }
  } else {
    // DICOM / NIfTI upload
    formData.append("files", rawFile);
    if (overridePatientId.value) formData.append("patient_id_override", overridePatientId.value);
    try {
      await api.post("/dicom/upload", formData);
      message.success(`上传成功: ${rawFile.name}`);
      if (auth.isPatient) fetchMyData(); else fetchPatients();
      onFinish();
    } catch (e: any) { message.error(`上传失败: ${rawFile.name}`); onError(); }
  }
}

function chooseDicomFolder() {
  if (!folderUploading.value) folderInput.value?.click();
}

async function handleFolderSelection(event: Event) {
  const input = event.target as HTMLInputElement;
  const selectedFiles = Array.from(input.files || []);
  input.value = "";

  const dicomFiles = selectedFiles.filter((file) => file.name.toLowerCase().endsWith(".dcm"));
  if (dicomFiles.length === 0) {
    message.warning("所选文件夹中没有 .dcm 文件");
    return;
  }
  if (dicomFiles.length !== selectedFiles.length) {
    message.warning(`已忽略 ${selectedFiles.length - dicomFiles.length} 个非 DICOM 文件`);
  }
  if (dicomFiles.length > 512) {
    message.error(`文件夹包含 ${dicomFiles.length} 个 DICOM 文件，单次最多上传 512 个`);
    return;
  }
  const totalBytes = dicomFiles.reduce((sum, file) => sum + file.size, 0);
  if (totalBytes > 512 * 1024 * 1024) {
    message.error(`文件夹大小为 ${formatFileSize(totalBytes)}，单次上传不能超过 512 MB`);
    return;
  }

  const formData = new FormData();
  for (const file of dicomFiles) formData.append("files", file, file.name);
  if (overridePatientId.value) formData.append("patient_id_override", overridePatientId.value);
  folderUploading.value = true;
  folderFileCount.value = dicomFiles.length;
  folderUploadProgress.value = 0;
  try {
    const response = await api.post("/dicom/upload", formData, {
      timeout: 600_000,
      onUploadProgress(progressEvent) {
        if (progressEvent.total) {
          folderUploadProgress.value = Math.min(99, Math.round(progressEvent.loaded / progressEvent.total * 100));
        }
      },
    });
    folderUploadProgress.value = 100;
    const studyCount = Array.isArray(response.data?.studies) ? response.data.studies.length : 0;
    message.success(`已上传 ${response.data?.total_files || dicomFiles.length} 个 DICOM 文件，识别 ${studyCount} 项检查`);
    await fetchPatients();
  } catch (e: any) {
    const detail = e.response?.data?.detail;
    message.error(`文件夹上传失败${detail ? `：${detail}` : "，请检查文件和网络连接"}`);
  } finally {
    folderUploading.value = false;
    folderFileCount.value = 0;
    folderUploadProgress.value = 0;
  }
}

async function fetchMyData() {
  loading.value = true;
  try {
    const res = await api.get("/dicom/patients");
    const allPatients = res.data || [];
    const seen = new Set<string>();
    myDoctors.value = [];
    for (const p of allPatients) {
      if (p.doctor_name && !seen.has(p.doctor_name)) {
        seen.add(p.doctor_name);
        myDoctors.value.push({ id: p.doctor_id, username: p.doctor_name });
      }
    }
    if (allPatients.length > 0) {
      patientInfo.value = allPatients[0];
      const studyRes = await api.get(`/dicom/patients/${allPatients[0].id}/studies`);
      myStudies.value = studyRes.data || [];
    }
  } finally { loading.value = false; }
}

onMounted(() => {
  if (auth.isPatient) fetchMyData(); else fetchPatients();
});
</script>

<style scoped>
.patient-list { max-width: 1024px; }
.empty { padding: 64px 48px; text-align: center; color: var(--color-text-secondary); background: var(--color-surface); border-radius: 8px; border: 1px solid var(--color-border); }
.empty p { margin-top: 16px; font-size: 14px; }
.hint { font-size: 12px !important; color: #94A3B8 !important; margin-top: 8px !important; }
.patients-table { background: var(--color-surface); border-radius: 8px; border: 1px solid var(--color-border); }
.patients-table :deep(.n-data-table-th) { background: var(--color-surface); font-weight: 600; }
.detail-row { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 2px 0; }
.detail-label { color: #64748B; width: 56px; flex-shrink: 0; }
.section-label { font-size: 13px; font-weight: 600; color: #64748B; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.3px; }
.text-muted { font-size: 12px; color: #94A3B8; }
.folder-input { display: none; }
</style>
