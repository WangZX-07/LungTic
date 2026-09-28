<template>
  <main class="admin-login">
    <section class="login-panel" aria-labelledby="admin-title">
      <img src="/logo.jpg" alt="" class="logo" />
      <p class="eyebrow">LUNGTIC · 管理后台</p>
      <h1 id="admin-title">管理员登录</h1>
      <p class="intro">管理账号、诊疗团队和病例访问授权</p>
      <n-form :model="form" size="large" @submit.prevent="submit">
        <n-form-item label="用户名"><n-input v-model:value="form.username" autocomplete="username" /></n-form-item>
        <n-form-item label="密码"><n-input v-model:value="form.password" type="password" show-password-on="click" autocomplete="current-password" /></n-form-item>
        <n-form-item label="验证码">
          <TextCaptcha ref="captchaRef" :api-client="api" @update:token="captchaToken = $event" @update:code="captchaCode = $event" />
        </n-form-item>
        <n-button type="primary" block size="large" :loading="loading" :disabled="!form.username || !form.password || !captchaCode" attr-type="submit">
          登录管理后台
        </n-button>
      </n-form>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
    <IcpFooter />
  </main>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NForm, NFormItem, NInput, NButton } from "naive-ui";
import TextCaptcha from "@/components/TextCaptcha.vue";
import IcpFooter from "@/components/IcpFooter.vue";
import api from "./api";
import { useAdminStore } from "./store";

const router = useRouter();
const store = useAdminStore();
const form = ref({ username: "", password: "" });
const captchaToken = ref("");
const captchaCode = ref("");
const captchaRef = ref<InstanceType<typeof TextCaptcha> | null>(null);
const loading = ref(false);
const error = ref("");

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    await store.login(form.value.username, form.value.password, captchaToken.value, captchaCode.value);
    await router.replace("/users");
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || "登录失败";
    captchaRef.value?.refresh();
  } finally {
    loading.value = false;
  }
}
</script>
<style scoped>
.admin-login { min-height: 100vh; display: flex; flex-direction: column; align-items: center; background: #f1f5f9; padding: 24px; }
.login-panel { width: min(100%, 420px); padding: 40px; border-radius: 12px; background: #fff; box-shadow: 0 8px 32px #0f172a15; margin: auto; }
.logo { width: 48px; height: 48px; border-radius: 9px; }
.eyebrow { margin: 20px 0 8px; color: #1565c0; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
h1 { margin: 0; color: #172033; font-size: 25px; }
.intro { margin: 8px 0 28px; color: #64748b; font-size: 14px; }
.error { color: #b91c1c; background: #fef2f2; padding: 10px 12px; border-radius: 6px; font-size: 13px; }
</style>
