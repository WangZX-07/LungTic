<template>
  <div class="workspace">
    <n-space justify="space-between" align="center" style="margin-bottom:16px">
      <n-space align="center">
        <n-tag type="info" size="small">Study #{{ studyId }}</n-tag>
        <n-tag v-if="segStatus" :type="statusTagType" size="small">{{ statusLabel }}</n-tag>
        <n-button quaternary size="small" @click="showMetadata = !showMetadata" :type="showMetadata ? 'primary' : 'default'">
          <template #icon><n-icon><InformationCircleOutline /></n-icon></template>
          DICOM 信息
        </n-button>
      </n-space>
      <n-space>
        <n-dropdown trigger="click" :options="exportOptions" @select="handleExportSelect">
          <n-button size="small">
            <template #icon><n-icon><DownloadOutline /></n-icon></template>导出结果
            <n-icon style="margin-left:4px"><ChevronDownOutline /></n-icon>
          </n-button>
        </n-dropdown>
        <n-button size="small" type="primary" @click="runSegmentation" :loading="segRunning" :disabled="segRunning">
          <template #icon><n-icon><FlashOutline /></n-icon></template>执行分割
        </n-button>
      </n-space>
    </n-space>
    <n-alert v-if="segRunning" type="info" :bordered="false" style="margin-bottom:12px">
      <template #header><n-space align="center"><n-spin size="small" /><span>AI 分割进行中...</span></n-space></template>
    </n-alert>
    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="axial" tab="横断面"><AxialView :study-id="studyId" :key="'axial-'+studyId" /></n-tab-pane>
      <n-tab-pane name="cine" tab="4D 电影"><n-card size="small" title="4D Cine Player"><CinePlayer v-if="activeTab === 'cine'" :phases="cinePhases" :current-phase-index="cinePhaseIndex" @update:current-phase-index="cinePhaseIndex = $event" /></n-card></n-tab-pane>
      <n-tab-pane name="3d" tab="3D 靶区"><Target3DView v-if="activeTab === '3d'" :study-id="studyId" :key="'3d-'+studyId" /></n-tab-pane>
      <n-tab-pane name="trajectory" tab="运动轨迹"><TrajectoryView :study-id="studyId" :key="'traj-'+studyId" /></n-tab-pane>
    </n-tabs>
    <n-drawer v-model:show="showMetadata" :width="360" placement="right">
      <n-drawer-content title="DICOM 元数据" closable><DicomMetadata :study-id="studyId" /></n-drawer-content>
    </n-drawer>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { useRoute } from "vue-router";
import { NSpace, NButton, NIcon, NTag, NTabs, NTabPane, NAlert, NSpin, NCard, NDrawer, NDrawerContent, NDropdown, useMessage } from "naive-ui";
import { FlashOutline, InformationCircleOutline, DownloadOutline, ChevronDownOutline, DocumentTextOutline, CubeOutline, SaveOutline } from "@vicons/ionicons5";
import api from "@/api";
import AxialView from "@/components/AxialView.vue";
import Target3DView from "@/components/Target3DView.vue";
import TrajectoryView from "@/components/TrajectoryView.vue";
import DicomMetadata from "@/components/DicomMetadata.vue";
import CinePlayer from "@/components/CinePlayer.vue";

const route = useRoute();
const message = useMessage();
const studyId = Number(route.params.id);
const activeTab = ref("axial");
const segRunning = ref(false);
const segStatus = ref<string | null>(null);
const cinePhases = ref<any[]>([]);
const cinePhaseIndex = ref(0);
const showMetadata = ref(false);
const statusTagType = computed(() => segStatus.value === "completed" ? "success" : segStatus.value === "running" ? "warning" : "default");
const statusLabel = computed(() => segStatus.value === "completed" ? "已完成" : segStatus.value === "running" ? "运行中..." : "未分割");

const exportOptions = computed(() => [
  { label: "导出 TICI (.tici) — 推荐", key: "tici", icon: () => h(NIcon, null, { default: () => h(CubeOutline) }) },
  { label: "导出 JSON 报告 (.json)", key: "json", icon: () => h(NIcon, null, { default: () => h(DocumentTextOutline) }) },
  { label: "下载 TICI 文件 (已导出)", key: "download-tici", icon: () => h(NIcon, null, { default: () => h(SaveOutline) }) },
]);

async function checkSegStatus() { try { const r = await api.get(`/segmentation/${studyId}/result`); segStatus.value = r.data?.status || null; } catch { segStatus.value = null; } }
async function loadCinePhases() { try { const r = await api.get(`/dicom/studies/${studyId}/phases`); cinePhases.value = r.data || []; } catch { cinePhases.value = []; } }
async function runSegmentation() {
  segRunning.value = true; segStatus.value = "running";
  try { await api.post("/segmentation/run", { study_id: studyId }); message.success("分割已启动");
    let retries = 0;
    while (retries < 30) { await new Promise(r => setTimeout(r, 3000));
      try { const r = await api.get(`/segmentation/${studyId}/result`);
        if (r.data?.status === "completed") { segStatus.value = "completed"; message.success("分割完成"); break; }
        if (r.data?.status === "failed") { segStatus.value = null; break; }
      } catch {}; retries++;
    }
  } catch (e: any) { message.error("分割失败"); segStatus.value = null; }
  finally { segRunning.value = false; }
}

async function handleExportSelect(key: string) {
  switch (key) {
    case "tici":
      await exportTici();
      break;
    case "json":
      await exportJson();
      break;
    case "download-tici":
      await downloadTici();
      break;
  }
}

async function exportTici() {
  try {
    const res = await api.post(`/tici/export/${studyId}`);
    message.success(`TICI 导出成功: ${res.data.phase_count} 时相`);
    // Offer download after export
    setTimeout(() => downloadTici(), 500);
  } catch (e: any) {
    message.error("TICI 导出失败");
  }
}

async function exportJson() {
  const report: any = { study_id: studyId, exported_at: new Date().toISOString() };
  try { const r = await api.get(`/segmentation/${studyId}/result`); report.segmentation = r.data; } catch {}
  try { const r = await api.get(`/igtv/${studyId}`); report.igtv = r.data; } catch {}
  try { const r = await api.get(`/trajectory/${studyId}`); report.trajectory = r.data; } catch {}
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob); const a = document.createElement("a");
  a.href = url; a.download = `lungtic-study-${studyId}-report.json`; a.click(); URL.revokeObjectURL(url);
  message.success("JSON 报告已导出");
}

async function downloadTici() {
  try {
    const res = await api.get(`/tici/download/${studyId}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `study_${studyId}.tici`;
    a.click();
    URL.revokeObjectURL(url);
    message.success("TICI 文件已下载");
  } catch (e: any) {
    message.error("下载失败，请先导出 TICI");
  }
}

onMounted(() => { checkSegStatus(); loadCinePhases(); });
</script>
<style scoped>
.workspace { height: 100%; display: flex; flex-direction: column; }
.workspace :deep(.n-tabs) { flex: 1; display: flex; flex-direction: column; }
.workspace :deep(.n-tabs .n-tab-pane) { flex: 1; overflow: auto; }
</style>
