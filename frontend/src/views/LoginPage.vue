<template>
  <div class="login-page">
    <main class="login-shell">
      <section class="identity-panel" :class="{ 'is-configuring': showServerConfig }" :aria-labelledby="showServerConfig ? 'connection-title' : 'brand-title'">
        <div v-if="connectionLoading" class="connection-loading">正在读取医院连接配置…</div>
        <template v-else-if="showServerConfig">
          <div class="panel-eyebrow">首次使用 · 第 1 步</div>
          <h1 id="connection-title">配置医院连接</h1>
          <p class="panel-intro">请填写医院管理员提供的 HTTPS 服务地址与服务器公钥指纹。保存后，下次打开无需重复填写。</p>
          <div class="server-config">
            <label for="server-origin">医院服务端 HTTPS 地址</label>
            <n-input id="server-origin" v-model:value="serverOrigin" placeholder="https://clinical.example.org" :disabled="savingServer" />
            <label for="server-pin">服务器公钥 SHA-256 指纹</label>
            <n-input id="server-pin" v-model:value="serverPin" placeholder="64 位十六进制指纹" :disabled="savingServer" class="pin-input" />
            <p class="server-hint">请通过医院认可的可信渠道核对指纹。客户端仅连接证书有效且公钥指纹匹配的服务端。</p>
            <n-button type="primary" size="large" block :disabled="!serverOrigin.trim() || !serverPin.trim()" :loading="savingServer" @click="saveServer">保存连接配置</n-button>
          </div>
          <p v-if="connectionError" class="panel-error" role="alert">{{ connectionError }}</p>
        </template>
        <template v-else>
          <div class="brand-content">
            <img src="/logo.jpg" alt="LungTic 标志" class="logo" />
            <h1 id="brand-title" class="app-name">LungTic</h1>
            <p class="brand-subtitle">4D 肺癌诊断与预测系统</p>
          </div>
          <div class="brand-bottom">{{ standaloneViewer ? "本地阅片器" : "临床客户端" }}</div>
        </template>
      </section>

      <section class="login-panel" aria-labelledby="login-title">
        <div class="login-content">
          <div class="login-eyebrow">{{ standaloneViewer ? "本地阅片器" : "医生 / 患者" }}</div>
          <h2 id="login-title">登录 LungTic</h2>
          <p class="login-intro">{{ showServerConfig || connectionLoading ? "完成左侧连接配置后，即可使用医院账号登录。" : "请输入账号信息，进入临床工作台。" }}</p>
          <n-form :model="form" :rules="rules" size="large" class="login-form">
            <n-form-item path="role" label="登录身份">
              <n-select v-model:value="form.role" :options="roleOptions" placeholder="选择身份" :disabled="!serverReady" />
            </n-form-item>
            <n-form-item path="username" label="用户名">
              <n-input v-model:value="form.username" placeholder="请输入用户名" clearable :disabled="!serverReady" @keyup.enter="focusPassword">
                <template #prefix><n-icon><PersonOutline /></n-icon></template>
              </n-input>
            </n-form-item>
            <n-form-item path="password" label="密码">
              <n-input ref="pwdRef" v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" :disabled="!serverReady" @keyup.enter="handleLogin">
                <template #prefix><n-icon><LockClosedOutline /></n-icon></template>
              </n-input>
            </n-form-item>
            <n-form-item v-if="serverReady" label="验证码">
              <TextCaptcha ref="captchaRef" @update:token="captchaToken = $event" @update:code="captchaCode = $event" />
            </n-form-item>
          </n-form>
          <n-button type="primary" block size="large" class="login-button" :disabled="!serverReady" :loading="loading" @click="handleLogin">登录</n-button>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="login-footer-links">
            <n-button text size="small" :disabled="!serverReady" @click="showResetModal = true">忘记密码？</n-button>
          </div>
        </div>
      </section>
    </main>
    <ResetPasswordModal v-model:show="showResetModal" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NForm, NFormItem, NInput, NButton, NIcon, NSelect } from "naive-ui";
import { PersonOutline, LockClosedOutline } from "@vicons/ionicons5";
import { useAuthStore } from "@/stores/auth";
import { getServerConnection, isPackagedClinicalClient, saveServerConnection } from "@/api/server";
import TextCaptcha from "@/components/TextCaptcha.vue";
import ResetPasswordModal from "@/components/ResetPasswordModal.vue";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const standaloneViewer = import.meta.env.VITE_STANDALONE_VIEWER === "true";
const loading = ref(false);
const error = ref("");
const connectionError = ref("");
const connectionLoading = ref(isPackagedClinicalClient);
const captchaRef = ref<any>(null);
const captchaToken = ref("");
const captchaCode = ref("");
const showResetModal = ref(false);
const pwdRef = ref<any>(null);
const serverOrigin = ref("");
const serverPin = ref("");
const savingServer = ref(false);
const serverReady = ref(!isPackagedClinicalClient);
const showServerConfig = computed(() => isPackagedClinicalClient && !connectionLoading.value && !serverReady.value);

onMounted(async () => {
  if (!isPackagedClinicalClient) return;
  try {
    const connection = await getServerConnection();
    if (connection) {
      serverOrigin.value = connection.origin;
      serverPin.value = connection.pin;
      serverReady.value = true;
    }
  } catch (e: any) {
    connectionError.value = e.message || "读取医院连接配置失败";
  } finally {
    connectionLoading.value = false;
  }
});

async function saveServer() {
  savingServer.value = true;
  connectionError.value = "";
  try {
    const connection = await saveServerConnection(serverOrigin.value, serverPin.value);
    serverOrigin.value = connection.origin;
    serverPin.value = connection.pin;
    serverReady.value = true;
  } catch (e: any) {
    connectionError.value = e.message || "保存连接配置失败";
  } finally {
    savingServer.value = false;
  }
}

const roleOptions = [
  { label: "医生", value: "doctor" },
  { label: "患者", value: "patient" },
  ...(standaloneViewer ? [{ label: "本地阅片器管理员", value: "admin" }] : []),
];
const form = ref({ username: "", password: "", role: "doctor" });
const rules = {
  username: { required: true, message: "请输入用户名", trigger: "blur" },
  password: { required: true, message: "请输入密码", trigger: "blur" },
};

function focusPassword() { pwdRef.value?.focus(); }
async function handleLogin() {
  error.value = "";
  if (!serverReady.value) { error.value = "请先配置医院连接"; return; }
  loading.value = true;
  try {
    await authStore.login(form.value.username, form.value.password, form.value.role, captchaToken.value, captchaCode.value);
    const redirect = (route.query.redirect as string)
      || (standaloneViewer ? "/dashboard/tici-viewer" : "/dashboard");
    router.replace(redirect);
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || "登录失败，请检查用户名和密码";
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
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px;
  background: linear-gradient(135deg, #155eac 0%, #237fd0 58%, #53a3e8 100%);
}
.login-shell {
  display: grid;
  grid-template-columns: minmax(340px, 0.9fr) minmax(420px, 1.1fr);
  width: min(100%, 980px);
  min-height: 620px;
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 22px 65px rgba(12, 49, 95, 0.22);
}
.identity-panel {
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 52px;
  color: #fff;
  background: linear-gradient(155deg, #174f96 0%, #1366b8 60%, #1586cc 100%);
}
.identity-panel.is-configuring { justify-content: flex-start; }
.panel-eyebrow, .login-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 0.06em; }
.panel-eyebrow { color: #d2e9ff; }
.identity-panel h1 { margin: 12px 0 10px; font-size: 28px; line-height: 1.25; }
.panel-intro { margin: 0 0 28px; color: #e4f2ff; font-size: 14px; line-height: 1.75; }
.server-config { display: flex; flex-direction: column; gap: 10px; }
.server-config label { font-size: 13px; font-weight: 600; color: #fff; }
.server-config :deep(.n-input) { margin-bottom: 8px; }
.server-config .pin-input :deep(input) { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.server-hint { margin: 0 0 14px; color: #e4f2ff; font-size: 12px; line-height: 1.65; }
.panel-error { color: #fff; background: rgba(114, 16, 30, 0.58); padding: 9px 12px; border-radius: 6px; font-size: 12px; line-height: 1.5; }
.connection-loading { color: #e4f2ff; font-size: 14px; }
.brand-content { text-align: center; }
.logo { width: 92px; height: 92px; object-fit: cover; border-radius: 20px; background: #fff; box-shadow: 0 12px 30px rgba(7, 40, 82, 0.2); }
.app-name { font-size: 34px !important; letter-spacing: -0.02em; }
.brand-subtitle { color: #e4f2ff; font-size: 15px; }
.brand-bottom { position: absolute; left: 52px; bottom: 40px; font-size: 12px; color: #d2e9ff; }
.login-panel { display: flex; align-items: center; justify-content: center; padding: 48px 64px; min-width: 0; }
.login-content { width: 100%; max-width: 360px; }
.login-eyebrow { color: #176dc1; }
.login-content h2 { margin: 10px 0 8px; font-size: 27px; font-weight: 700; color: #172b45; }
.login-intro { min-height: 42px; margin: 0 0 28px; font-size: 14px; line-height: 1.6; color: #52647b; }
.login-form :deep(.n-form-item) { margin-bottom: 8px; }
.login-form :deep(.n-form-item-label) { color: #32445d; font-weight: 600; }
.login-button { margin-top: 12px; }
.error { color: #b42331; font-size: 13px; margin-top: 12px; background: #fff1f2; padding: 9px 12px; border-radius: 6px; }
.login-footer-links { margin-top: 14px; text-align: right; }
@media (max-width: 800px) {
  .login-page { padding: 16px; }
  .login-shell { grid-template-columns: 1fr; width: min(100%, 560px); }
  .identity-panel { min-height: 220px; padding: 32px; }
  .identity-panel.is-configuring { min-height: 0; }
  .brand-bottom { left: 32px; bottom: 24px; }
  .logo { width: 68px; height: 68px; }
  .app-name { font-size: 26px !important; }
  .login-panel { padding: 36px 32px; }
}
</style>
