<template>
  <n-card size="small" title="DICOM 元数据" class="metadata-card">
    <n-spin :show="loading" size="small">
      <div v-if="!hasData" class="metadata-empty">
        <p class="text-muted">加载中...</p>
      </div>
      <div v-else class="metadata-list">
        <div class="metadata-group">
          <h4 class="group-title">患者信息</h4>
          <div class="metadata-row" v-for="item in patientTags" :key="item.key">
            <span class="tag-key">{{ item.label }}</span>
            <span class="tag-value" :title="item.value">{{ item.value || "-" }}</span>
          </div>
        </div>
        <n-divider style="margin:8px 0" />
        <div class="metadata-group">
          <h4 class="group-title">检查信息</h4>
          <div class="metadata-row" v-for="item in studyTags" :key="item.key">
            <span class="tag-key">{{ item.label }}</span>
            <span class="tag-value" :title="item.value">{{ item.value || "-" }}</span>
          </div>
        </div>
        <n-divider style="margin:8px 0" />
        <div class="metadata-group">
          <h4 class="group-title">采集参数</h4>
          <div class="metadata-row" v-for="item in acquisitionTags" :key="item.key">
            <span class="tag-key">{{ item.label }}</span>
            <span class="tag-value" :title="item.value">{{ item.value || "-" }}</span>
          </div>
        </div>
      </div>
    </n-spin>
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { NCard, NSpin, NDivider } from "naive-ui";
import api from "@/api";

const props = defineProps<{ studyId: number }>();

const loading = ref(false);
const metadata = ref<Record<string, any>>({});
const hasData = ref(false);

const patientTags = computed(() => [
  { label: "患者 ID", key: "PatientID", value: metadata.value?.PatientID },
  { label: "姓名", key: "PatientName", value: metadata.value?.PatientName },
  { label: "性别", key: "PatientSex", value: metadata.value?.PatientSex },
  { label: "出生日期", key: "PatientBirthDate", value: metadata.value?.PatientBirthDate },
  { label: "年龄", key: "PatientAge", value: metadata.value?.PatientAge },
]);

const studyTags = computed(() => [
  { label: "Study UID", key: "StudyInstanceUID", value: (metadata.value?.StudyInstanceUID || "").substring(0, 20) + "..." },
  { label: "检查日期", key: "StudyDate", value: metadata.value?.StudyDate },
  { label: "检查描述", key: "StudyDescription", value: metadata.value?.StudyDescription },
  { label: "设备", key: "Modality", value: metadata.value?.Modality },
  { label: "机构", key: "InstitutionName", value: metadata.value?.InstitutionName },
]);

const acquisitionTags = computed(() => [
  { label: "层厚 (mm)", key: "SliceThickness", value: metadata.value?.SliceThickness },
  { label: "间距 (mm)", key: "SpacingBetweenSlices", value: metadata.value?.SpacingBetweenSlices },
  { label: "kVp", key: "KVP", value: metadata.value?.KVP },
  { label: "曝光 (mAs)", key: "Exposure", value: metadata.value?.Exposure },
  { label: "卷积核", key: "ConvolutionKernel", value: metadata.value?.ConvolutionKernel },
  { label: "像素间距", key: "PixelSpacing", value: metadata.value?.PixelSpacing },
  { label: "行 × 列", key: "Dimensions", value: metadata.value?.Rows && metadata.value?.Columns ? `${metadata.value.Rows} × ${metadata.value.Columns}` : null },
]);

async function loadMetadata() {
  loading.value = true;
  try {
    const res = await api.get(`/dicom/studies/${props.studyId}/phases`);
    // Extract metadata from the study or first series
    if (res.data?.length > 0) {
      const firstSeries = res.data[0];
      metadata.value = firstSeries.metadata || firstSeries;
    }
    // Try dedicated metadata endpoint
    try {
      const metaRes = await api.get(`/dicom/studies/${props.studyId}`);
      if (metaRes.data) {
        metadata.value = { ...metadata.value, ...metaRes.data };
      }
    } catch {}
    hasData.value = Object.keys(metadata.value).length > 0;
  } catch {
    hasData.value = false;
  } finally {
    loading.value = false;
  }
}

onMounted(loadMetadata);
watch(() => props.studyId, loadMetadata);
</script>

<style scoped>
.metadata-card {
  font-size: 12px;
}

.metadata-empty {
  padding: 16px;
  text-align: center;
}

.metadata-list {
  max-height: 400px;
  overflow-y: auto;
}

.metadata-group {
  margin-bottom: 4px;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.metadata-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 0;
}

.tag-key {
  color: #64748B;
  width: 68px;
  flex-shrink: 0;
  font-size: 11px;
}

.tag-value {
  color: #1E293B;
  word-break: break-all;
  font-size: 11px;
  font-family: "Consolas", "Courier New", monospace;
}

.text-muted {
  color: #94A3B8;
  font-size: 12px;
}
</style>