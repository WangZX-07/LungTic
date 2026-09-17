<template>
  <div class="login-page">
    <div class="login-card">
      <img src="/logo.jpg" alt="LungTic" class="logo" />
      <h1 class="app-name">LungTic</h1>
      <p class="subtitle">4D 肺癌诊断与预测系统</p>

      <n-form ref="formRef" :model="form" :rules="rules" size="large">
        <n-form-item path="role">
          <n-select v-model:value="form.role" :options="roleOptions" placeholder="选择角色" />
        </n-form-item>
        <n-form-item path="username">
          <n-input v-model:value="form.username" placeholder="用户名" clearable @keyup.enter="focusPassword">
            <template #prefix><n-icon><PersonOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item path="password">
          <n-input ref="pwdRef" v-model:value="form.password" type="password" placeholder="密码" show-password-on="click" @keyup.enter="handleLogin">
            <template #prefix><n-icon><LockClosedOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item>
          <TextCaptcha ref="captchaRef" @update:token="captchaToken = $event" @update:code="captchaCode = $event" />
        </n-form-item>
      </n-form>

      <n-button type="primary" block size="large" :loading="loading" @click="handleLogin">
        登录
      </n-button>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="login-footer-links">
        <n-button text size="small" @click="showResetModal = true">忘记密码？</n-button>
      </div>
    </div>

    <div class="login-footer">
      <span>LungTic v0.2.0</span>
    </div>

    <ResetPasswordModal v-model:show="showResetModal" />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NForm, NFormItem, NInput, NButton, NIcon, NSelect } from "naive-ui";
import { PersonOutline, LockClosedOutline } from "@vicons/ionicons5";
import { useAuthStore } from "@/stores/auth";
import TextCaptcha from "@/components/TextCaptcha.vue";
import ResetPasswordModal from "@/components/ResetPasswordModal.vue";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const loading = ref(false);
const error = ref("");
const captchaRef = ref<any>(null);
const captchaToken = ref("");
const captchaCode = ref("");
const showResetModal = ref(false);
const pwdRef = ref<any>(null);

const roleOptions = [
  { label: "医生", value: "doctor" },
  { label: "患者", value: "patient" },
  { label: "管理员", value: "admin" },
];

const form = ref({ username: "", password: "", role: "doctor" });
const rules = {
  username: { required: true, message: "请输入用户名", trigger: "blur" },
  password: { required: true, message: "请输入密码", trigger: "blur" },
};

function focusPassword() {
  pwdRef.value?.focus();
}

async function handleLogin() {
  error.value = "";
  loading.value = true;
  try {
    await authStore.login(form.value.username, form.value.password, form.value.role, captchaToken.value, captchaCode.value);
    const redirect = (route.query.redirect as string)
      || (import.meta.env.VITE_STANDALONE_VIEWER === "true"
        ? "/dashboard/tici-viewer"
        : "/dashboard");
    router.replace(redirect);
  } catch (e: any) {
    error.value = e.response?.data?.detail || "登录失败，请检查用户名和密码";
    captchaRef.value?.refresh();
    captchaToken.value = "";
    captchaCode.value = "";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100vh; position: relative; overflow: hidden;
  background: linear-gradient(135deg, #1565C0 0%, #1E88E5 50%, #42A5F5 100%);
}
.login-page::before {
  content: ""; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: radial-gradient(circle at 30% 70%, rgba(255,255,255,0.05) 0%, transparent 50%),
              radial-gradient(circle at 70% 30%, rgba(255,255,255,0.08) 0%, transparent 50%);
  pointer-events: none;
}
.login-card {
  width: 420px; padding: 40px 48px; background: #FFFFFF; border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15), 0 2px 8px rgba(0,0,0,0.1);
  text-align: center; z-index: 1; animation: fadeIn 0.4s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.logo { width: 64px; height: 64px; border-radius: 12px; margin-bottom: 8px; box-shadow: 0 4px 12px rgba(30,136,229,0.2); }
.app-name { font-size: 22px; color: #1565C0; margin-bottom: 2px; font-weight: 700; }
.subtitle { font-size: 13px; color: #64748B; margin-bottom: 24px; }
.error { color: #EF4444; font-size: 13px; margin-top: 12px; background: #FEF2F2; padding: 8px 12px; border-radius: 6px; }
.login-footer { position: absolute; bottom: 24px; color: rgba(255,255,255,0.6); font-size: 12px; z-index: 1; }
.login-footer-links { margin-top: 12px; text-align: right; }
</style>
