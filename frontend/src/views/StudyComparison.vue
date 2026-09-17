<template>
  <div class="comparison-page">
    <n-space justify="space-between" align="center" style="margin-bottom:16px">
      <n-space align="center">
        <n-button text size="small" @click="router.push('/dashboard/patients')">
          <template #icon><n-icon><ArrowBack /></n-icon></template>
          返回
        </n-button>
        <span class="page-label">对比阅片</span>
      </n-space>
      <n-space>
        <n-tag v-if="studyA" size="small" :type="studyASegStatus === 'completed' ? 'success' : 'default'">
          Study A: #{{ studyA }}
        </n-tag>
        <n-tag v-if="studyB" size="small" :type="studyBSegStatus === 'completed' ? 'success' : 'default'">
          Study B: #{{ studyB }}
        </n-tag>
        <n-button size="small" @click="exportComparison">导出对比报告</n-button>
      </n-space>
    </n-space>

    <!-- Side-by-side viewport -->
    <div class="comparison-grid">
      <!-- Left: Study A -->
      <div class="panel panel-left">
        <div class="panel-header">
          <span>Study A</span>
          <n-tag v-if="!studyA" size="tiny" type="warning">未选择</n-tag>
        </div>
        <div v-if="!studyA" class="panel-empty">
          <p>请从患者列表选择 Study A</p>
        </div>
        <div v-else class="panel-content">
          <img
            v-if="studyAImage"
            :src="'data:image/png;base64,' + studyAImage"
            class="comparison-image"
          />
          <div v-else class="panel-loading">
            <n-spin size="small" />
          </div>
        </div>
        <div v-if="studyA" class="panel-footer">
          <span>{{ studyAInfo }}</span>
          <n-tag v-if="studyASegStatus === 'completed'" size="tiny" type="success" style="margin-left:8px">已分割</n-tag>
        </div>
      </div>

      <!-- Divider -->
      <div class="panel-divider">
        <div class="divider-line" />
        <n-button
          quaternary
          circle
          size="small"
          @click="syncScroll = !syncScroll"
          :type="syncScroll ? 'primary' : 'default'"
        >
          <template #icon><n-icon><LinkOutline /></n-icon></template>
        </n-button>
        <div class="divider-line" />
      </div>

      <!-- Right: Study B -->
      <div class="panel panel-right">
        <div class="panel-header">
          <span>Study B</span>
          <n-tag v-if="!studyB" size="tiny" type="warning">未选择</n-tag>
        </div>
        <div v-if="!studyB" class="panel-empty">
          <p>请从患者列表选择 Study B</p>
        </div>
        <div v-else class="panel-content">
          <img
            v-if="studyBImage"
            :src="'data:image/png;base64,' + studyBImage"
            class="comparison-image"
          />
          <div v-else class="panel-loading">
            <n-spin size="small" />
          </div>
        </div>
        <div v-if="studyB" class="panel-footer">
          <span>{{ studyBInfo }}</span>
          <n-tag v-if="studyBSegStatus === 'completed'" size="tiny" type="success" style="margin-left:8px">已分割</n-tag>
        </div>
      </div>
    </div>

    <!-- Unassigned studies picker + TICI import -->
    <div v-if="!studyA || !studyB" class="study-picker">
      <n-space justify="space-between" align="center">
        <h4 class="picker-title">选择检查进行对比</h4>
        <n-button size="small" type="info" @click="triggerTiciImport">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          从 TICI 文件加载
        </n-button>
      </n-space>
      <input
        ref="ticiInputRef"
        type="file"
        accept=".tici"
        style="display:none"
        @change="handleTiciImport"
      />
      <n-space style="margin-top:8px">
        <div v-for="s in availableStudies" :key="s.id" class="picker-item">
          <n-button
            size="small"
            :type="studyA === s.id ? 'primary' : studyB === s.id ? 'info' : 'default'"
            @click="assignStudy(s.id)"
            :disabled="studyA === s.id || studyB === s.id"
          >
            Study #{{ s.id }}
          </n-button>
          <span class="picker-date">{{ s.study_date || "-" }}</span>
          <n-tag v-if="s.tici_path" size="tiny" :bordered="false" type="success">TICI</n-tag>
        </div>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NSpace, NButton, NIcon, NTag, NSpin, useMessage } from "naive-ui";
import { ArrowBack, LinkOutline, AddOutline } from "@vicons/ionicons5";
import api from "@/api";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const studyA = ref<number | null>(null);
const studyB = ref<number | null>(null);
const studyAImage = ref("");
const studyBImage = ref("");
const studyAInfo = ref("");
const studyBInfo = ref("");
const studyASegStatus = ref<string | null>(null);
const studyBSegStatus = ref<string | null>(null);
const syncScroll = ref(true);
const availableStudies = ref<any[]>([]);
const ticiInputRef = ref<HTMLInputElement | null>(null);

async function loadStudies() {
  try {
    const res = await api.get("/dicom/patients");
    const patients = res.data || [];
    const allStudies: any[] = [];
    for (const p of patients) {
      try {
        const studiesRes = await api.get(`/dicom/patients/${p.id}/studies`);
        for (const s of (studiesRes.data || [])) {
          allStudies.push({ ...s, patient_code: p.patient_code });
        }
      } catch {}
    }
    availableStudies.value = allStudies;

    // Check query params for pre-selected studies
    const a = route.query.a;
    const b = route.query.b;
    if (a) { studyA.value = Number(a); await loadStudyA(); }
    if (b) { studyB.value = Number(b); await loadStudyB(); }
  } catch {}
}

async function loadStudyA() {
  if (!studyA.value) return;
  try {
    const res = await api.get(`/dicom/studies/${studyA.value}/phases`);
    if (res.data?.length > 0) {
      const phase = res.data[0];
      const slicesRes = await api.get(`/dicom/series/${phase.id}/slices`);
      if (slicesRes.data?.length > 0) {
        const midSlice = slicesRes.data[Math.floor(slicesRes.data.length / 2)];
        const imgRes = await api.get(`/dicom/slice/${midSlice.id}/image`);
        studyAImage.value = imgRes.data?.image_base64 || imgRes.data;
        studyAInfo.value = `${slicesRes.data.length} 层 · ${res.data.length} 时相`;
      }
    }
    const segRes = await api.get(`/segmentation/${studyA.value}/result`);
    studyASegStatus.value = segRes.data?.status || null;
  } catch {}
}

async function loadStudyB() {
  if (!studyB.value) return;
  try {
    const res = await api.get(`/dicom/studies/${studyB.value}/phases`);
    if (res.data?.length > 0) {
      const phase = res.data[0];
      const slicesRes = await api.get(`/dicom/series/${phase.id}/slices`);
      if (slicesRes.data?.length > 0) {
        const midSlice = slicesRes.data[Math.floor(slicesRes.data.length / 2)];
        const imgRes = await api.get(`/dicom/slice/${midSlice.id}/image`);
        studyBImage.value = imgRes.data?.image_base64 || imgRes.data;
        studyBInfo.value = `${slicesRes.data.length} 层 · ${res.data.length} 时相`;
      }
    }
    const segRes = await api.get(`/segmentation/${studyB.value}/result`);
    studyBSegStatus.value = segRes.data?.status || null;
  } catch {}
}

function assignStudy(studyId: number) {
  if (!studyA.value) {
    studyA.value = studyId;
    loadStudyA();
  } else if (!studyB.value) {
    studyB.value = studyId;
    loadStudyB();
  }
}

function triggerTiciImport() {
  ticiInputRef.value?.click();
}

async function handleTiciImport(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await api.post("/tici/import", formData);
    const newStudyId = res.data.study_id;
    message.success(`TICI 导入成功: Study #${newStudyId}`);
    if (!studyA.value) {
      studyA.value = newStudyId;
      loadStudyA();
    } else if (!studyB.value) {
      studyB.value = newStudyId;
      loadStudyB();
    }
    loadStudies(); // Refresh the picker list
  } catch (e: any) {
    message.error("TICI 导入失败");
  }
  // Reset input
  input.value = "";
}

async function exportComparison() {
  if (!studyA.value && !studyB.value) {
    message.warning("请先选择检查");
    return;
  }

  // Export both studies as TICI
  const exportPromises = [];
  if (studyA.value) exportPromises.push(api.post(`/tici/export/${studyA.value}`));
  if (studyB.value) exportPromises.push(api.post(`/tici/export/${studyB.value}`));
  await Promise.all(exportPromises).catch(() => {});

  // Build comparison report
  const report: any = {
    compared_at: new Date().toISOString(),
    study_a: studyA.value,
    study_b: studyB.value,
  };

  if (studyA.value) {
    try { report.segmentation_a = (await api.get(`/segmentation/${studyA.value}/result`)).data; } catch {}
    try { report.igtv_a = (await api.get(`/igtv/${studyA.value}`)).data; } catch {}
    try { report.trajectory_a = (await api.get(`/trajectory/${studyA.value}`)).data; } catch {}
  }
  if (studyB.value) {
    try { report.segmentation_b = (await api.get(`/segmentation/${studyB.value}/result`)).data; } catch {}
    try { report.igtv_b = (await api.get(`/igtv/${studyB.value}`)).data; } catch {}
    try { report.trajectory_b = (await api.get(`/trajectory/${studyB.value}`)).data; } catch {}
  }

  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lungtic-comparison-${studyA.value || 'X'}-vs-${studyB.value || 'X'}.json`;
  a.click();
  URL.revokeObjectURL(url);
  message.success("对比报告已导出");
}

watch(() => route.query, () => {
  const a = route.query.a;
  const b = route.query.b;
  if (a && Number(a) !== studyA.value) { studyA.value = Number(a); loadStudyA(); }
  if (b && Number(b) !== studyB.value) { studyB.value = Number(b); loadStudyB(); }
});

onMounted(loadStudies);
</script>

<style scoped>
.comparison-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-label {
  font-size: 14px;
  font-weight: 600;
}

.comparison-grid {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
}

.panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #0F172A;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  padding: 8px 16px;
  background: #1E293B;
  color: #E2E8F0;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}

.panel-empty,
.panel-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748B;
  font-size: 13px;
}

.comparison-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.panel-footer {
  padding: 6px 16px;
  background: #1E293B;
  color: #94A3B8;
  font-size: 11px;
  display: flex;
  align-items: center;
}

.panel-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  justify-content: center;
}

.divider-line {
  width: 1px;
  flex: 1;
  background: #334155;
}

.study-picker {
  margin-top: 16px;
  padding: 16px;
  background: #FFFFFF;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
}

.picker-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  margin: 0;
}

.picker-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.picker-date {
  font-size: 10px;
  color: #94A3B8;
}
</style>
