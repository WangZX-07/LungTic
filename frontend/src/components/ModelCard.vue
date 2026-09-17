<template>
  <n-card :title="model.model_name" size="small" class="model-card" hoverable>
    <template #header-extra>
      <n-tag
        :type="model.is_active ? 'success' : 'default'"
        size="small"
        round
      >
        {{ model.is_active ? "已激活" : "未激活" }}
      </n-tag>
    </template>

    <n-space vertical :size="8">
      <div class="info-row">
        <span class="label">格式</span>
        <n-tag :bordered="false" size="tiny" type="info">
          {{ model.model_type?.toUpperCase() || "未知" }}
        </n-tag>
      </div>
      <div class="info-row">
        <span class="label">任务</span>
        <span class="value">{{ model.task_type === "segmentation" ? "分割" : "预测" }}</span>
      </div>
    </n-space>

    <template #action>
      <n-space>
        <n-button
          size="small"
          :type="model.is_active ? 'default' : 'primary'"
          :loading="activating"
          @click="handle激活"
        >
          {{ model.is_active ? "停用" : "激活" }}
        </n-button>
        <n-popconfirm @positive-click="handle删除">
          <template #trigger>
            <n-button size="small" type="error" ghost>删除</n-button>
          </template>
          确定删除此模型？
        </n-popconfirm>
      </n-space>
    </template>
  </n-card>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { NCard, NTag, NSpace, NButton, NPopconfirm, useMessage } from "naive-ui";
import api from "@/api";

const props = defineProps<{
  model: {
    id: number;
    model_name: string;
    model_type: string;
    task_type: string;
    is_active: boolean;
  };
}>();
const emit = defineEmits(["changed"]);
const message = useMessage();
const activating = ref(false);

async function handle激活() {
  activating.value = true;
  try {
    await api.put(`/models/${props.model.id}/activate`);
    message.success(props.model.is_active ? "已停用" : "已激活");
    emit("changed");
  } catch (e: any) {
    message.error(e.response?.data?.detail || "操作失败");
  } finally {
    activating.value = false;
  }
}

async function handle删除() {
  try {
    await api.delete(`/models/${props.model.id}`);
    message.success("已删除");
    emit("changed");
  } catch (e: any) {
    message.error("删除失败");
  }
}
</script>

<style scoped>
.model-card {
  width: 100%;
  transition: box-shadow 0.2s ease, transform 0.15s ease;
}

.model-card:hover {
  transform: translateY(-2px);
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.label {
  color: #64748B;
  width: 28px;
}

.value {
  color: #1E293B;
}
</style>