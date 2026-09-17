<template>
  <div class="model-manager">
    <n-space vertical :size="24">
      <ModelUpload @uploaded="fetchModels" />

      <div>
        <h2 class="section-title">我的模型</h2>
        <n-spin :show="loading">
          <div v-if="models.length === 0 && !loading" class="empty">
            <n-icon size="48" color="#CBD5E1"><CubeOutline /></n-icon>
            <p>暂无模型</p>
            <p class="hint">请上传 .pth 或 .onnx 文件以添加自定义 AI 模型</p>
          </div>
          <div v-else class="model-grid">
            <ModelCard
              v-for="m in models"
              :key="m.id"
              :model="m"
              @changed="fetchModels"
            />
          </div>
        </n-spin>
      </div>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { NSpace, NSpin, NIcon } from "naive-ui";
import { CubeOutline } from "@vicons/ionicons5";
import api from "@/api";
import ModelUpload from "@/components/ModelUpload.vue";
import ModelCard from "@/components/ModelCard.vue";

interface ModelItem {
  id: number;
  model_name: string;
  model_type: string;
  task_type: string;
  is_active: boolean;
}

const models = ref<ModelItem[]>([]);
const loading = ref(false);

async function fetchModels() {
  loading.value = true;
  try {
    const res = await api.get("/models/");
    models.value = res.data;
  } catch {
    models.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(fetchModels);
</script>

<style scoped>
.model-manager {
  max-width: 1024px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #1E293B;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.empty {
  padding: 64px 48px;
  text-align: center;
  color: #64748B;
  background: #FFFFFF;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
}

.empty p {
  margin-top: 16px;
  font-size: 14px;
}

.hint {
  font-size: 12px !important;
  color: #94A3B8 !important;
  margin-top: 8px !important;
}
</style>