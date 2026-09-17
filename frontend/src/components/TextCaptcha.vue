<template>
  <div class="text-captcha">
    <div class="captcha-row">
      <n-input v-model:value="inputCode" placeholder="请输入验证码" size="large" :maxlength="4" style="flex:1" />
      <div class="captcha-img-wrapper" @click="refresh">
        <img v-if="imageBase64" :src="'data:image/png;base64,' + imageBase64" class="captcha-img" alt="验证码" />
        <n-spin v-else size="small" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { NInput, NSpin } from "naive-ui";
import api from "@/api";

const emit = defineEmits<{ "update:token": [token: string]; "update:code": [code: string] }>();

const imageBase64 = ref("");
const captchaToken = ref("");
const inputCode = ref("");

async function refresh() {
  inputCode.value = "";
  emit("update:code", "");
  try {
    const res = await api.post("/auth/captcha/generate");
    imageBase64.value = res.data.image_base64;
    captchaToken.value = res.data.token;
    emit("update:token", res.data.token);
  } catch {}
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
  background: #f0f0f5; border: 1px solid #E2E8F0; flex-shrink: 0;
  transition: border-color 0.2s;
}
.captcha-img-wrapper:hover { border-color: #1E88E5; }
.captcha-img { width: 100%; height: 100%; object-fit: cover; }
</style>