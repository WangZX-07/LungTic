<template>
  <n-card title="上传模型" size="small">
    <n-upload
      :max="1"
      accept=".pth,.onnx"
      :show-file-list="true"
      :custom-request="handleUpload"
      class="upload-area"
    >
      <n-upload-dragger>
        <div class="dragger-content">
          <n-icon size="48" :depth="3"><CloudUploadOutline /></n-icon>
          <p class="dragger-title">点击或拖拽上传模型文件</p>
          <p class="dragger-hint">支持 .pth (PyTorch) 和 .onnx (ONNX) 格式</p>
        </div>
      </n-upload-dragger>
    </n-upload>

    <n-space vertical :size="12" class="upload-form">
      <n-input
        v-model:value="modelName"
        placeholder="模型名称（如: My-Attention-UNet-v2）"
        clearable
      >
        <template #prefix>
          <n-icon><DocumentTextOutline /></n-icon>
        </template>
      </n-input>

      <n-select
        v-model:value="taskType"
        :options="taskOptions"
        placeholder="选择任务类型"
      />

      <n-button
        type="primary"
        block
        :loading="uploading"
        :disabled="!canUpload"
        @click="submitUpload"
      >
        <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
        确认上传
      </n-button>
    </n-space>
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import {
  NUpload, NUploadDragger, NIcon, NSpace,
  NInput, NSelect, NButton, NCard, useMessage,
} from "naive-ui";
import {
  CloudUploadOutline, DocumentTextOutline, CheckmarkCircleOutline,
} from "@vicons/ionicons5";
import api from "@/api";

const emit = defineEmits(["uploaded"]);
const message = useMessage();

const modelName = ref("");
const taskType = ref<string | null>(null);
const fileRef = ref<File | null>(null);
const uploading = ref(false);

const taskOptions = [
  { label: "分割 (分割)", value: "segmentation" },
  { label: "预测 (预测)", value: "prediction" },
];

const canUpload = computed(
  () => modelName.value.trim() && taskType.value && fileRef.value
);

function handleUpload({ file }: { file: any }) {
  fileRef.value = file.file as File;
}

async function submitUpload() {
  if (!fileRef.value || !taskType.value) return;
  uploading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", fileRef.value);
    formData.append("model_name", modelName.value.trim());
    formData.append("task_type", taskType.value);

    await api.post("/models/upload", formData);

    message.success("模型上传成功");
    modelName.value = "";
    taskType.value = null;
    fileRef.value = null;
    emit("uploaded");
  } catch (e: any) {
    message.error(e.response?.data?.detail || "上传失败，请检查文件格式");
  } finally {
    uploading.value = false;
  }
}
</script>

<style scoped>
.upload-area {
  margin-bottom: 4px;
}

.dragger-content {
  padding: 16px 0;
}

.dragger-title {
  font-size: 16px;
  margin-top: 12px;
  color: #1E293B;
}

.dragger-hint {
  font-size: 12px;
  color: #64748B;
  margin-top: 6px;
}

.upload-form {
  max-width: 480px;
  margin-top: 16px;
}
</style>