<template>
  <main class="auth-complete" aria-live="polite">
    <n-spin size="large" />
    <h1>正在进入项目工作台</h1>
    <p>正在确认飞书身份与项目权限，请稍候。</p>
    <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>
  </main>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NAlert, NSpin } from "naive-ui";
import { useProjectStore } from "../store";
const store = useProjectStore();
const router = useRouter();
const error = ref("");
onMounted(async () => {
  if (await store.verify()) await router.replace("/overview");
  else { error.value = "登录未完成，请重新发起飞书登录。"; setTimeout(() => router.replace("/login"), 1800); }
});
</script>
<style scoped>
.auth-complete { min-height: 100vh; min-height: 100dvh; padding: 32px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #52647b; background: #f8fafc; text-align: center; }
.auth-complete h1 { color: #172033; font-size: 22px; }
.auth-complete :deep(.n-alert) { max-width: 440px; margin-top: 12px; }
</style>
