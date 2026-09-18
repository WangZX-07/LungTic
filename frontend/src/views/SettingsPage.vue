<template>
  <div class="settings-page">
    <h2 class="page-title">设置</h2>

    <n-space vertical :size="24">
      <!-- 个人资料 -->
      <n-card title="个人资料" size="small">
        <n-space vertical :size="12">
          <div class="setting-row">
            <div>
              <div class="setting-label">邮箱</div>
              <div class="setting-desc">用于密码重置和通知</div>
            </div>
            <n-input v-model:value="profileEmail" placeholder="未设置" style="width:220px" size="small" />
          </div>
          <div class="setting-row">
            <div>
              <div class="setting-label">手机号</div>
              <div class="setting-desc">联系方式</div>
            </div>
            <n-input v-model:value="profilePhone" placeholder="未设置" style="width:220px" size="small" />
          </div>
          <n-button type="primary" size="small" :loading="profileSaving" @click="saveProfile">保存资料</n-button>
          <p v-if="profileMsg" :style="{ color: profileOk ? '#22C55E' : '#EF4444', fontSize: '13px' }">{{ profileMsg }}</p>
        </n-space>
      </n-card>

      <!-- 医院连接 -->
      <n-card v-if="isPackagedClinicalClient" title="医院连接" size="small">
        <n-space vertical :size="12">
          <div>
            <div class="setting-label">当前服务端</div>
            <div class="connection-value">{{ currentOrigin || "未配置" }}</div>
          </div>
          <div>
            <div class="setting-label">服务器公钥 SHA-256 指纹</div>
            <code class="connection-pin">{{ currentPin || "未配置" }}</code>
          </div>
          <n-button v-if="!editingConnection" size="small" @click="startConnectionEdit">重新配置连接</n-button>
          <div v-else class="connection-editor">
            <label for="settings-server-origin" class="setting-label">医院服务端 HTTPS 地址</label>
            <n-input id="settings-server-origin" v-model:value="serverOrigin" placeholder="https://clinical.example.org" :disabled="savingConnection" />
            <label for="settings-server-pin" class="setting-label">服务器公钥 SHA-256 指纹</label>
            <n-input id="settings-server-pin" v-model:value="serverPin" placeholder="64 位十六进制指纹" :disabled="savingConnection" />
            <p class="setting-desc">保存后将退出当前账号，并重新加载客户端以使用新连接。</p>
            <n-space>
              <n-button type="primary" size="small" :disabled="!serverOrigin.trim() || !serverPin.trim()" :loading="savingConnection" @click="saveConnection">保存并重新连接</n-button>
              <n-button size="small" :disabled="savingConnection" @click="editingConnection = false">取消</n-button>
            </n-space>
          </div>
          <p v-if="connectionError" class="connection-error" role="alert">{{ connectionError }}</p>
        </n-space>
      </n-card>
      <!-- 外观 -->
      <n-card title="外观" size="small">
        <n-space vertical :size="12">
          <div class="setting-row">
            <div>
              <div class="setting-label">侧边栏默认折叠</div>
              <div class="setting-desc">启动时自动折叠侧边栏</div>
            </div>
            <n-switch v-model:value="sidebarCollapsed" />
          </div>
          <div class="setting-row">
            <div>
              <div class="setting-label">暗色模式</div>
              <div class="setting-desc">切换深色/浅色主题</div>
            </div>
            <n-switch :value="themeStore.theme === 'dark'" @update:value="themeStore.setTheme($event ? 'dark' : 'light')" />
          </div>
          <div class="setting-row">
            <div>
              <div class="setting-label">动画效果</div>
              <div class="setting-desc">启用页面切换动画和过渡效果</div>
            </div>
            <n-switch v-model:value="animationsEnabled" />
          </div>
        </n-space>
      </n-card>

      <!-- AI 推理 (doctor/admin only) -->
      <n-card v-if="!authStore.isPatient" title="AI 推理" size="small">
        <n-space vertical :size="12">
          <div class="setting-row">
            <div>
              <div class="setting-label">分割模型</div>
              <div class="setting-desc">当前使用的肿瘤分割模型</div>
            </div>
            <n-tag type="info" size="small">内置 Attention U-Net</n-tag>
          </div>
          <div class="setting-row">
            <div>
              <div class="setting-label">预测模型</div>
              <div class="setting-desc">当前使用的轨迹预测模型</div>
            </div>
            <n-tag type="info" size="small">内置 BiLSTM + TCN</n-tag>
          </div>
          <n-divider style="margin:8px 0" />
          <div class="setting-row">
            <div>
              <div class="setting-label">推理超时</div>
              <div class="setting-desc">单次 AI 推理最大等待时间</div>
            </div>
            <n-input-number v-model:value="inferenceTimeout" :min="30" :max="600" style="width:100px"><template #suffix>秒</template></n-input-number>
          </div>
        </n-space>
      </n-card>

      <!-- 显示 (doctor/admin only) -->
      <n-card v-if="!authStore.isPatient" title="显示" size="small">
        <n-space vertical :size="12">
          <div class="setting-row">
            <div>
              <div class="setting-label">默认窗宽窗位</div>
              <div class="setting-desc">CT 图像默认显示参数</div>
            </div>
            <n-select v-model:value="defaultPreset" :options="presetOptions" style="width:140px" size="small" />
          </div>
          <div class="setting-row">
            <div>
              <div class="setting-label">Mask 默认透明度</div>
              <div class="setting-desc">分割结果叠加层的初始透明度</div>
            </div>
            <n-slider v-model:value="maskOpacity" :min="10" :max="100" :step="5" style="width:120px" />
          </div>
        </n-space>
      </n-card>

      <!-- 关于 -->
      <n-card title="关于" size="small">
        <n-space vertical :size="8">
          <div class="about-row"><span class="about-label">应用名称</span><span>LungTic</span></div>
          <div class="about-row"><span class="about-label">版本</span><n-tag size="tiny" :bordered="false">v0.2.0</n-tag></div>
          <div class="about-row"><span class="about-label">技术栈</span><span>Electron 30 + Vue 3 + FastAPI + PyTorch</span></div>
          <div class="about-row"><span class="about-label">设计系统</span><span>8pt Grid · Naive UI</span></div>
          <n-divider style="margin:8px 0" />
          <div class="about-row"><span class="about-label">AI 模型</span><span>Attention U-Net · BiLSTM + TCN</span></div>
          <div class="about-row"><span class="about-label">可视化</span><span>Three.js · ECharts · Cornerstone.js</span></div>
        </n-space>
      </n-card>

      <!-- 数据管理 -->
      <n-card title="数据管理" size="small">
        <n-space vertical :size="8">
          <p class="text-muted">清除本地缓存和临时文件</p>
          <n-button type="error" ghost size="small" @click="clearCache">清除缓存</n-button>
        </n-space>
      </n-card>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useThemeStore } from "@/stores/theme";
import { useAuthStore } from "@/stores/auth";
import api from "@/api";
import { getServerConnection, isPackagedClinicalClient, saveServerConnection } from "@/api/server";
import { NSpace, NCard, NSwitch, NTag, NDivider, NInputNumber, NInput, NSelect, NSlider, NButton, useMessage } from "naive-ui";

const message = useMessage();
const router = useRouter();
const themeStore = useThemeStore();
const authStore = useAuthStore();

const sidebarCollapsed = ref(false);
const animationsEnabled = ref(true);
const inferenceTimeout = ref(120);
const defaultPreset = ref("lung");
const maskOpacity = ref(50);
const profileEmail = ref("");
const profilePhone = ref("");
const profileSaving = ref(false);
const profileMsg = ref("");
const profileOk = ref(false);

const currentOrigin = ref("");
const currentPin = ref("");
const serverOrigin = ref("");
const serverPin = ref("");
const editingConnection = ref(false);
const savingConnection = ref(false);
const connectionError = ref("");

async function loadConnectionSettings() {
  if (!isPackagedClinicalClient) return;
  try {
    const connection = await getServerConnection();
    currentOrigin.value = connection?.origin || "";
    currentPin.value = connection?.pin || "";
  } catch (e: any) {
    connectionError.value = e.message || "读取医院连接配置失败";
  }
}

function startConnectionEdit() {
  serverOrigin.value = currentOrigin.value;
  serverPin.value = currentPin.value;
  connectionError.value = "";
  editingConnection.value = true;
}

async function saveConnection() {
  savingConnection.value = true;
  connectionError.value = "";
  try {
    await saveServerConnection(serverOrigin.value, serverPin.value);
    authStore.logout();
    await router.replace("/login");
  } catch (e: any) {
    connectionError.value = e.message || "保存连接配置失败";
  } finally {
    savingConnection.value = false;
  }
}
const presetOptions = [
  { label: "肺窗 (1500/-600)", value: "lung" },
  { label: "纵隔窗 (350/50)", value: "mediastinum" },
  { label: "骨窗 (2000/350)", value: "bone" },
  { label: "默认 (400/40)", value: "default" },
];

async function saveProfile() {
  profileSaving.value = true;
  profileMsg.value = "";
  try {
    await api.put("/auth/profile", { email: profileEmail.value || undefined, phone: profilePhone.value || undefined });
    profileMsg.value = "保存成功";
    profileOk.value = true;
    await authStore.fetchMe();
  } catch (e: any) {
    profileMsg.value = e.response?.data?.detail || "保存失败";
    profileOk.value = false;
  } finally { profileSaving.value = false; }
}

function clearCache() { localStorage.removeItem("lungtic_settings"); message.success("缓存已清除"); }

onMounted(async () => {
  await loadConnectionSettings();
  if (authStore.user) { profileEmail.value = authStore.user.email || ""; }
  else {
    await authStore.fetchMe();
    profileEmail.value = (authStore.user as { email?: string } | null)?.email || "";
  }
  profilePhone.value = (authStore.user as any)?.phone || "";
});
</script>

<style scoped>
.settings-page { max-width: 680px; }
.page-title { font-size: 20px; font-weight: 600; margin-bottom: 24px; }
.setting-row { display: flex; justify-content: space-between; align-items: center; }
.setting-label { font-size: 14px; color: #1E293B; font-weight: 500; }
.setting-desc { font-size: 12px; color: #94A3B8; margin-top: 2px; }
.about-row { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.about-label { color: #64748B; width: 64px; flex-shrink: 0; }
.text-muted { font-size: 12px; color: #94A3B8; }
.connection-value { margin-top: 4px; font-size: 13px; color: #334155; overflow-wrap: anywhere; }
.connection-pin { display: block; margin-top: 4px; color: #334155; font-size: 12px; overflow-wrap: anywhere; }
.connection-editor { display: flex; flex-direction: column; gap: 8px; padding-top: 8px; }
.connection-editor .setting-desc { color: #52647b; line-height: 1.5; }
.connection-editor :deep(input) { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.connection-error { color: #b42331; font-size: 13px; margin: 0; }
</style>
