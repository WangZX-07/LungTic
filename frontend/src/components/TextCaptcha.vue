<template>
  <div class="text-captcha">
    <div class="captcha-row">
      <n-input v-model:value="inputCode" placeholder="请输入验证码" size="large" :maxlength="4" style="flex:1" />
      <button type="button" class="captcha-img-wrapper" aria-label="刷新验证码" @click="refresh">
        <img v-if="imageBase64" :src="'data:image/png;base64,' + imageBase64" class="captcha-img" alt="验证码" />
        <span v-else-if="loadError" class="captcha-error">加载失败，点击重试</span>
        <n-spin v-else size="small" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { NInput, NSpin } from "naive-ui";
import api from "@/api";
import type { AxiosInstance } from "axios";
const props = defineProps<{ apiClient?: AxiosInstance }>();

const emit = defineEmits<{ "update:token": [token: string]; "update:code": [code: string] }>();

const imageBase64 = ref("");
const captchaToken = ref("");
const inputCode = ref("");
const loadError = ref(false);

async function refresh() {
  inputCode.value = "";
  imageBase64.value = "";
  loadError.value = false;
  emit("update:code", "");
  emit("update:token", "");
  try {
    const res = await (props.apiClient || api).post("/auth/captcha/generate");
    imageBase64.value = res.data.image_base64;
    captchaToken.value = res.data.token;
    emit("update:token", res.data.token);
  } catch { loadError.value = true; }
}

watch(inputCode, (val) => {
  emit("update:code", val);
});

defineExpose({ refresh });

onMounted(refresh);
</script>

<style scoped>
.text-captcha { width: 100%; }
.captcha-row { display: flex; gap: 8px; align-items: stretch; }
.captcha-img-wrapper {
  width: 120px; height: 42px; border-radius: 4px; overflow: hidden;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  background: #f0f0f5; border: 1px solid #E2E8F0; flex-shrink: 0; padding: 0;
  transition: border-color 0.2s;
}
.captcha-img-wrapper:hover, .captcha-img-wrapper:focus-visible { border-color: #1E88E5; outline: 2px solid #1E88E5; outline-offset: 2px; }
.captcha-error { color: #334155; font-size: 11px; line-height: 1.2; }
.captcha-img { width: 100%; height: 100%; object-fit: cover; }
</style>
