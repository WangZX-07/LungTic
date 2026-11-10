<template>
  <section class="records">
    <n-space justify="space-between" align="center" class="heading">
      <h4 class="section-label">病例附件 ({{ records.length }})</h4>
      <n-spin v-if="loading" size="small" />
    </n-space>
    <n-space v-if="canWrite" vertical :size="8" class="upload-form">
      <n-space :wrap="true">
        <n-input v-model:value="title" placeholder="标题（留空使用文件名）" style="width: 220px" />
        <n-select v-model:value="recordType" :options="recordTypes" style="width: 132px" />
        <n-upload
          accept=".pdf,.png,.jpg,.jpeg,.dcm,.tici"
          :show-file-list="false"
          :custom-request="upload"
        >
          <n-button type="primary" :loading="uploading">上传附件</n-button>
        </n-upload>
      </n-space>
      <span class="hint">支持 PDF、图片、DICOM、TICI，单文件最大 512 MB</span>
    </n-space>
    <n-list v-if="records.length" bordered>
      <n-list-item v-for="record in records" :key="record.id">
        <n-thing :title="record.title">
          <template #description>
            <n-space :size="8">
              <span>{{ record.original_filename }}</span>
              <span>{{ formatSize(record.size_bytes) }}</span>
              <span>{{ formatDate(record.created_at) }}</span>
              <span :title="record.sha256">SHA-256 {{ record.sha256.slice(0, 12) }}…</span>
            </n-space>
          </template>
          <template #header-extra>
            <n-space :size="4">
              <n-tag size="small" :bordered="false">{{ record.record_type }}</n-tag>
              <n-tag v-if="record.encryption === 'AES-256-GCM'" size="small" type="success" :bordered="false">已加密</n-tag>
            </n-space>
          </template>
          <template #action>
            <n-space align="center" :size="8">
              <n-button size="small" @click="verify(record)">校验</n-button>
              <n-button size="small" @click="download(record)">下载</n-button>
              <template v-if="canWrite">
                <span class="hint">患者可见</span>
                <n-switch
                  size="small"
                  :value="record.patient_visible"
                  @update:value="(value: boolean) => setVisibility(record, value)"
                />
              </template>
            </n-space>
          </template>
        </n-thing>
      </n-list-item>
    </n-list>
    <n-empty v-else-if="!loading" description="暂无病例附件" />
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { NButton, NEmpty, NInput, NList, NListItem, NSelect, NSpace, NSpin, NSwitch, NTag, NThing, NUpload, useMessage } from "naive-ui";
import api from "@/api";

type RecordItem = {
  id: number;
  title: string;
  record_type: string;
  original_filename: string;
  size_bytes: number;
  created_at: string;
  patient_visible: boolean;
  sha256: string;
  encryption: string;
};

const props = defineProps<{ patientId: number }>();
const message = useMessage();
const records = ref<RecordItem[]>([]);
const canWrite = ref(false);
const loading = ref(false);
const uploading = ref(false);
const title = ref("");
const recordType = ref("report");
const recordTypes = [
  { label: "报告", value: "report" },
  { label: "病程记录", value: "note" },
  { label: "图片", value: "image" },
  { label: "DICOM", value: "dicom" },
  { label: "TICI", value: "tici" },
  { label: "其他", value: "other" },
];

async function refresh() {
  const patientId = props.patientId;
  loading.value = true;
  records.value = [];
  canWrite.value = false;
  try {
    const [access, result] = await Promise.all([
      api.get(`/patients/${patientId}/access`),
      api.get(`/patients/${patientId}/records`),
    ]);
    if (props.patientId === patientId) {
      canWrite.value = access.data.can_write === true;
      records.value = result.data;
    }
  } catch {
    message.error("无法读取病例附件");
  } finally {
    loading.value = false;
  }
}

async function upload({ file, onFinish, onError }: any) {
  const raw = file.file as File;
  if (!raw) { onError(); return; }
  uploading.value = true;
  const form = new FormData();
  form.append("file", raw);
  form.append("title", title.value.trim() || raw.name);
  form.append("record_type", recordType.value);
  try {
    await api.post(`/patients/${props.patientId}/records`, form);
    title.value = "";
    message.success("病例附件已上传");
    await refresh();
    onFinish();
  } catch {
    message.error("上传失败，请检查文件类型或病例权限");
    onError();
  } finally {
    uploading.value = false;
  }
}

async function verify(record: RecordItem) {
  try {
    await api.get(`/records/${record.id}/integrity`);
    message.success("加密标签和 SHA-256 校验通过");
  } catch {
    message.error("完整性校验失败，请联系管理员");
  }
}

async function download(record: RecordItem) {
  try {
    const result = await api.get(`/records/${record.id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = record.original_filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch {
    message.error("下载失败，访问权限可能已变更");
  }
}

async function setVisibility(record: RecordItem, value: boolean) {
  try {
    const result = await api.put(`/records/${record.id}/visibility`, { patient_visible: value });
    record.patient_visible = result.data.patient_visible;
  } catch {
    message.error("更新患者可见范围失败");
  }
}

function formatSize(bytes: number) {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString("zh-CN") : "";
}

watch(() => props.patientId, refresh, { immediate: true });
</script>

<style scoped>
.records { margin-top: 24px; }
.heading { margin-bottom: 12px; }
.section-label { margin: 0; font-size: 14px; font-weight: 600; }
.upload-form { margin-bottom: 16px; }
.hint { color: #64748b; font-size: 12px; }
</style>
