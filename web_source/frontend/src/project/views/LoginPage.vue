<template>
  <main class="project-login">
    <section class="login-brand" aria-label="LungTic 项目进度">
      <div class="brand-lockup"><img src="/logo.jpg" alt="" /><strong>LungTic</strong></div>
      <div>
        <h1>让每一次推进都有依据</h1>
        <p>里程碑、任务、人工填报与 GitHub 动态汇聚在一个只服务于 LungTic 项目的工作空间。</p>
      </div>
      <span>项目协作门户</span>
    </section>
    <section class="login-action" aria-labelledby="login-title">
      <div class="login-card">
        <p class="login-context">飞书组织身份</p>
        <h2 id="login-title">登录项目工作台</h2>
        <p class="login-copy">权限会依据你的飞书部门与职位自动分配；项目账号与临床系统账号完全隔离。</p>
        <n-alert v-if="!store.configured" type="warning" :show-icon="true" :bordered="false">
          服务器尚未配置飞书应用，请联系项目管理员完成接入。
        </n-alert>
        <n-button
          type="primary" size="large" block :loading="loading" :disabled="!store.configured"
          @click="startLogin"
        >{{ insideFeishu ? "使用当前飞书账号进入" : "飞书扫码登录" }}</n-button>
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <p class="login-help">在飞书工作台内打开时将优先免登；普通浏览器会进入飞书官方授权页。</p>
      </div>
      <IcpFooter />
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAlert, NButton } from "naive-ui";
import IcpFooter from "@/components/IcpFooter.vue";
import { errorMessage } from "../api";
import { useProjectStore } from "../store";

const store = useProjectStore();
const route = useRoute();
const router = useRouter();
const loading = ref(false);
const error = ref(typeof route.query.error === "string" ? route.query.error : "");
const insideFeishu = Boolean(window.tt?.requestAccess || window.tt?.requestAuthCode);

function legacyLogin() {
  if (!window.tt?.requestAuthCode) {
    window.location.assign("/api/project/auth/start");
    return;
  }
  window.tt.requestAuthCode({
    appId: store.appId,
    success: ({ code }) => finishClientLogin(code),
    fail: (reason) => { loading.value = false; error.value = reason.errString || "飞书免登失败"; },
  });
}

async function finishClientLogin(code: string) {
  try {
    await store.loginWithCode(code);
    await router.replace(typeof route.query.next === "string" ? route.query.next : "/overview");
  } catch (reason) {
    error.value = errorMessage(reason, "飞书登录失败");
  } finally {
    loading.value = false;
  }
}

function startLogin() {
  error.value = "";
  loading.value = true;
  if (window.tt?.requestAccess) {
    window.tt.requestAccess({
      appID: store.appId, scopeList: [],
      success: ({ code }) => finishClientLogin(code),
      fail: (reason) => {
        if (reason.errno === 103) legacyLogin();
        else { loading.value = false; error.value = reason.errString || "飞书授权失败"; }
      },
    });
    return;
  }
  if (window.tt?.requestAuthCode) return legacyLogin();
  window.location.assign("/api/project/auth/start");
}

onMounted(async () => {
  try {
    await store.loadConfig();
    if (await store.verify()) await router.replace("/overview");
  } catch (reason) {
    error.value = errorMessage(reason, "无法读取登录配置");
  }
});
</script>

<style scoped>
.project-login { min-height: 100vh; min-height: 100dvh; display: grid; grid-template-columns: minmax(360px, .9fr) minmax(480px, 1.1fr); background: #fff; }
.login-brand { padding: 56px 64px; display: flex; flex-direction: column; justify-content: space-between; color: #e2e8f0; background: #1e293b; }
.brand-lockup { display: flex; align-items: center; gap: 12px; color: #fff; font-size: 19px; }
.brand-lockup img { width: 42px; height: 42px; border-radius: 8px; }
.login-brand h1 { max-width: 10ch; color: #fff; font-size: 38px; line-height: 1.2; letter-spacing: -.025em; text-wrap: balance; }
.login-brand p { max-width: 52ch; margin-top: 18px; color: #cbd5e1; font-size: 15px; line-height: 1.75; text-wrap: pretty; }
.login-brand > span { color: #94a3b8; font-size: 12px; }
.login-action { min-width: 0; padding: 36px; display: flex; flex-direction: column; justify-content: center; background: #f8fafc; }
.login-card { width: 100%; max-width: 430px; margin: auto; padding: 36px; border-radius: 12px; background: #fff; box-shadow: 0 4px 8px #0f172a12; }
.login-context { color: #1565c0; font-size: 12px; font-weight: 700; }
.login-card h2 { margin-top: 8px; color: #172033; font-size: 25px; line-height: 34px; }
.login-copy { margin: 10px 0 26px; color: #52647b; font-size: 14px; line-height: 1.65; }
.login-card :deep(.n-alert) { margin-bottom: 18px; }
.login-error { margin-top: 14px; padding: 10px 12px; border-radius: 7px; color: #991b1b; background: #fef2f2; font-size: 13px; line-height: 20px; }
.login-help { margin-top: 16px; color: #64748b; font-size: 12px; line-height: 19px; }
@media (max-width: 820px) {
  .project-login { grid-template-columns: 1fr; background: #f8fafc; }
  .login-brand { min-height: 210px; padding: max(28px, env(safe-area-inset-top)) 24px 28px; justify-content: flex-start; gap: 30px; }
  .login-brand h1 { max-width: none; font-size: 27px; }
  .login-brand p { display: none; }
  .login-brand > span { display: none; }
  .login-action { min-height: calc(100svh - 210px); padding: 20px max(16px, env(safe-area-inset-right)) max(8px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); }
  .login-card { padding: 26px 20px; }
}
@media (pointer: coarse) { .login-card :deep(.n-button) { min-height: 48px; } }
</style>
