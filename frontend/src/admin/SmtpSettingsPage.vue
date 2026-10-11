<template>
  <div class="smtp-page">
    <div class="page-heading">
      <div>
        <h1>密码重置邮件</h1>
        <p>配置用户找回密码和账号通知所使用的 SMTP 邮件通道。</p>
      </div>
      <n-tag :type="statusType">{{ statusText }}</n-tag>
    </div>

    <n-alert type="info" :show-icon="true" class="notice">
      SMTP 授权码使用服务器主密钥加密保存。页面不会显示已保存的授权码，留空表示保持原值。
    </n-alert>

    <n-card title="SMTP 配置" size="small">
      <n-spin :show="loading">
        <n-form label-placement="top">
          <div class="form-grid">
            <n-form-item label="启用邮件发送">
              <n-switch v-model:value="form.enabled" />
            </n-form-item>
            <div />
            <n-form-item label="SMTP 服务器">
              <n-input v-model:value="form.host" placeholder="smtp.qq.com" />
            </n-form-item>
            <n-form-item label="端口">
              <n-input-number v-model:value="form.port" :min="1" :max="65535" style="width:100%" />
            </n-form-item>
            <n-form-item label="连接加密">
              <n-select v-model:value="form.security" :options="securityOptions" />
            </n-form-item>
            <n-form-item label="SMTP 用户名">
              <n-input v-model:value="form.username" placeholder="通常为完整邮箱地址" />
            </n-form-item>
            <n-form-item label="发件人邮箱">
              <n-input v-model:value="form.from_address" placeholder="用于显示邮件发件人" />
            </n-form-item>
            <n-form-item label="授权码或密码">
              <n-input
                v-model:value="form.password"
                type="password"
                show-password-on="mousedown"
                :placeholder="passwordConfigured ? '已配置，留空保持原值' : '请输入邮箱 SMTP 授权码'"
              />
            </n-form-item>
          </div>
          <div class="actions">
            <span class="source">配置来源：{{ sourceLabel }}</span>
            <n-button type="primary" :loading="saving" @click="saveSettings">保存配置</n-button>
          </div>
        </n-form>
      </n-spin>
    </n-card>

    <n-card title="发送测试邮件" size="small" class="test-card">
      <p class="hint">先保存配置，再发送测试邮件。测试成功后即可用于“忘记密码”验证码。</p>
      <div class="test-row">
        <n-input v-model:value="testRecipient" placeholder="接收测试邮件的邮箱" @keyup.enter="sendTest" />
        <n-button :loading="testing" :disabled="!testRecipient.trim()" @click="sendTest">发送测试邮件</n-button>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  NAlert, NButton, NCard, NForm, NFormItem, NInput, NInputNumber,
  NSelect, NSpin, NSwitch, NTag, useMessage,
} from "naive-ui";
import api from "./api";

const message = useMessage();
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const passwordConfigured = ref(false);
const source = ref("unconfigured");
const testRecipient = ref("");
const form = reactive({
  enabled: true,
  host: "smtp.qq.com",
  port: 465,
  security: "ssl",
  username: "",
  from_address: "",
  password: "",
});
const securityOptions = [
  { label: "SSL/TLS（常用端口 465）", value: "ssl" },
  { label: "STARTTLS（常用端口 587）", value: "starttls" },
];
const sourceLabel = computed(() => ({
  database: "管理后台",
  environment: "服务器环境变量",
  unconfigured: "尚未配置",
} as Record<string, string>)[source.value] || "未知");
const statusText = computed(() => !form.enabled ? "已停用" : passwordConfigured.value ? "已配置" : "未配置");
const statusType = computed(() => !form.enabled ? "warning" : passwordConfigured.value ? "success" : "error");

function detail(error: any): string {
  const value = error?.response?.data?.detail;
  if (Array.isArray(value)) return value.map((item) => item.msg).join("；");
  return value || error?.message || "操作失败";
}

async function loadSettings() {
  loading.value = true;
  try {
    const { data } = await api.get("/admin/settings/smtp");
    form.enabled = data.enabled;
    form.host = data.host || "smtp.qq.com";
    form.port = data.port || 465;
    form.security = data.security || "ssl";
    form.username = data.username || "";
    form.from_address = data.from_address || "";
    form.password = "";
    passwordConfigured.value = Boolean(data.password_configured);
    source.value = data.source || "unconfigured";
  } catch (error) {
    message.error(detail(error));
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    const { data } = await api.put("/admin/settings/smtp", { ...form });
    form.password = "";
    passwordConfigured.value = Boolean(data.password_configured);
    source.value = data.source;
    message.success("SMTP 配置已保存并立即生效");
  } catch (error) {
    message.error(detail(error));
  } finally {
    saving.value = false;
  }
}

async function sendTest() {
  if (!testRecipient.value.trim()) return;
  testing.value = true;
  try {
    await api.post("/admin/settings/smtp/test", { recipient: testRecipient.value.trim() });
    message.success("测试邮件已发送，请检查收件箱和垃圾邮件目录");
  } catch (error) {
    message.error(detail(error));
  } finally {
    testing.value = false;
  }
}

onMounted(loadSettings);
</script>

<style scoped>
.smtp-page { max-width: 960px; margin: 0 auto; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
.page-heading h1 { margin: 0 0 6px; font-size: 24px; color: #0f172a; }
.page-heading p, .hint { margin: 0; color: #64748b; }
.notice { margin-bottom: 16px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 20px; }
.actions { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.source { color: #64748b; font-size: 13px; }
.test-card { margin-top: 16px; }
.test-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; margin-top: 14px; }
@media (max-width: 700px) {
  .form-grid { grid-template-columns: 1fr; }
  .form-grid > div:empty { display: none; }
  .page-heading { align-items: flex-start; }
  .actions { align-items: stretch; flex-direction: column; }
  .actions :deep(.n-button) { width: 100%; }
  .test-row { grid-template-columns: 1fr; }
}
@media (pointer: coarse) {
  .smtp-page :deep(.n-button), .smtp-page :deep(.n-switch) { min-height: 44px; }
}
</style>
