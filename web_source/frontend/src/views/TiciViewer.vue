<template>
  <section
    ref="pageRef"
    class="tici-page"
    tabindex="-1"
    @keydown="handleKeyboard"
  >
    <template v-if="!viewerInfo">
      <header class="page-intro">
        <div>
          <h1>TICI 查看器</h1>
          <p>直接检查时序影像、相位结构与封装元数据，不写入患者数据库。</p>
        </div>
        <n-tag type="info" size="small">TICI v1.0</n-tag>
      </header>

      <div
        class="open-panel"
        :class="{ dragging: isDragging }"
        @dragenter.prevent="isDragging = true"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <div class="open-icon" aria-hidden="true">
          <n-icon :size="32"><FolderOpenOutline /></n-icon>
        </div>
        <h2>打开一个 TICI 文件</h2>
        <p>文件将在当前账户的临时查看会话中读取，关闭页面后自动清理。</p>
        <input
          ref="fileInputRef"
          class="visually-hidden"
          type="file"
          accept=".tici"
          @change="handleFileInput"
        />
        <n-button
          type="primary"
          size="large"
          :loading="opening"
          @click="chooseFile"
        >
          <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
          选择 .tici 文件
        </n-button>
        <span class="drop-hint">或将文件拖到这里 · 最大 2 GB</span>

        <div v-if="opening" class="upload-progress" role="status" aria-live="polite">
          <n-progress
            type="line"
            :percentage="uploadProgress"
            :show-indicator="false"
            processing
          />
          <span>正在校验并打开文件 {{ uploadProgress }}%</span>
        </div>
      </div>

      <n-alert v-if="openError" type="error" class="open-error" closable @close="openError = ''">
        {{ openError }}
      </n-alert>

      <div class="capability-row" aria-label="当前查看能力">
        <div><n-icon><LayersOutline /></n-icon><span>多时相浏览</span></div>
        <div><n-icon><ScanOutline /></n-icon><span>逐层惰性读取</span></div>
        <div><n-icon><EyeOutline /></n-icon><span>Mask 叠加检查</span></div>
        <div><n-icon><InformationCircleOutline /></n-icon><span>元数据核验</span></div>
      </div>
    </template>

    <template v-else>
      <header class="viewer-header">
        <div class="file-identity">
          <n-icon :size="22"><ScanOutline /></n-icon>
          <div>
            <h1>{{ filename }}</h1>
            <p>
              {{ viewerInfo.study.modality || "未知模态" }} ·
              {{ viewerInfo.phases.length }} 时相 ·
              {{ formatBytes(viewerInfo.file_size_bytes) }}
            </p>
          </div>
        </div>
        <div class="header-actions">
          <input
            ref="replaceInputRef"
            class="visually-hidden"
            type="file"
            accept=".tici"
            @change="handleFileInput"
          />
          <n-button :disabled="opening" @click="chooseReplacement">
            <template #icon><n-icon><FolderOpenOutline /></n-icon></template>
            打开其他文件
          </n-button>
          <n-button quaternary @click="closeViewer">
            <template #icon><n-icon><CloseOutline /></n-icon></template>
            关闭
          </n-button>
        </div>
      </header>

      <n-alert v-if="viewError" type="error" class="viewer-alert" closable @close="viewError = ''">
        {{ viewError }}
      </n-alert>

      <div class="viewer-shell">
        <aside class="phase-panel" aria-label="时相列表">
          <div class="panel-heading">
            <h2>时相</h2>
            <span>{{ currentPhasePosition + 1 }}/{{ viewerInfo.phases.length }}</span>
          </div>
          <div class="phase-list">
            <button
              v-for="(phase, position) in viewerInfo.phases"
              :key="phase.phase"
              class="phase-item"
              :class="{ active: position === currentPhasePosition }"
              type="button"
              :aria-current="position === currentPhasePosition ? 'true' : undefined"
              @click="selectPhase(position)"
            >
              <span class="phase-thumb">
                <img
                  v-if="phaseThumbnails[phase.phase]"
                  :src="`data:image/png;base64,${phaseThumbnails[phase.phase]}`"
                  alt=""
                />
                <n-skeleton v-else width="100%" height="100%" />
              </span>
              <span class="phase-copy">
                <strong>Phase {{ getPhaseIndex(phase) }}</strong>
                <small>{{ phase.shape?.[0] || 0 }} 层</small>
              </span>
              <span v-if="phase.has_masks" class="mask-dot" title="包含 Mask" />
            </button>
          </div>
        </aside>

        <main class="image-workspace">
          <div class="viewport-wrap" @wheel.prevent="handleWheel">
            <TiciViewport
              :image-base64="imageBase64"
              :mask-base64="maskBase64"
              :show-mask="showMask"
              :mask-opacity="maskOpacity"
              :zoom="zoom"
              :loading="sliceLoading"
            />
            <div class="viewport-label top-left">
              <span>{{ viewerInfo.patient.patient_id || "匿名" }}</span>
              <span>{{ viewerInfo.study.study_uid || "无 Study UID" }}</span>
            </div>
            <div class="viewport-label top-right">
              <span>Phase {{ currentPhaseNumber }}</span>
              <span>Slice {{ currentSlice + 1 }} / {{ currentSliceCount }}</span>
            </div>
            <div class="viewport-label bottom-left">
              <span>W {{ displayWindowWidth }}</span>
              <span>L {{ displayWindowCenter }}</span>
            </div>
            <div class="viewport-label bottom-right">
              <span>{{ currentDimensions }}</span>
              <span>{{ Math.round(zoom * 100) }}%</span>
            </div>
          </div>

          <div class="slice-toolbar" aria-label="切片浏览工具">
            <n-button
              quaternary
              circle
              :disabled="currentSlice <= 0"
              aria-label="上一层"
              @click="stepSlice(-1)"
            >
              <template #icon><n-icon><ChevronBackOutline /></n-icon></template>
            </n-button>
            <span class="toolbar-value">{{ currentSlice + 1 }}</span>
            <n-slider
              v-model:value="currentSlice"
              :min="0"
              :max="Math.max(0, currentSliceCount - 1)"
              :step="1"
              :disabled="currentSliceCount <= 1"
              :tooltip="false"
              aria-label="切片位置"
              @update:value="scheduleSliceLoad"
            />
            <span class="toolbar-value muted">{{ currentSliceCount }}</span>
            <n-button
              quaternary
              circle
              :disabled="currentSlice >= currentSliceCount - 1"
              aria-label="下一层"
              @click="stepSlice(1)"
            >
              <template #icon><n-icon><ChevronForwardOutline /></n-icon></template>
            </n-button>
            <span class="toolbar-divider" />
            <n-button quaternary circle aria-label="缩小" @click="changeZoom(-0.1)">
              <template #icon><n-icon><RemoveOutline /></n-icon></template>
            </n-button>
            <n-button quaternary class="zoom-reset" @click="zoom = 1">
              {{ Math.round(zoom * 100) }}%
            </n-button>
            <n-button quaternary circle aria-label="放大" @click="changeZoom(0.1)">
              <template #icon><n-icon><AddOutline /></n-icon></template>
            </n-button>
          </div>

          <div class="cine-toolbar" aria-label="时相播放工具">
            <n-button
              type="primary"
              circle
              :aria-label="playing ? '暂停时相播放' : '播放时相'"
              @click="playing = !playing"
            >
              <template #icon>
                <n-icon><PauseOutline v-if="playing" /><PlayOutline v-else /></n-icon>
              </template>
            </n-button>
            <n-button quaternary circle aria-label="上一时相" @click="stepPhase(-1)">
              <template #icon><n-icon><PlayBackOutline /></n-icon></template>
            </n-button>
            <span class="toolbar-value">P{{ currentPhaseNumber }}</span>
            <n-slider
              v-model:value="currentPhasePosition"
              :min="0"
              :max="Math.max(0, viewerInfo.phases.length - 1)"
              :step="1"
              :tooltip="false"
              aria-label="时相位置"
              @update:value="selectPhase"
            />
            <n-button quaternary circle aria-label="下一时相" @click="stepPhase(1)">
              <template #icon><n-icon><PlayForwardOutline /></n-icon></template>
            </n-button>
            <n-select
              v-model:value="playbackFps"
              class="fps-select"
              size="small"
              :options="fpsOptions"
              aria-label="播放速度"
            />
          </div>
        </main>

        <aside class="inspector-panel" aria-label="查看器设置和元数据">
          <section class="inspector-section">
            <div class="panel-heading"><h2>显示</h2></div>
            <div class="control-row">
              <label for="show-mask">Mask 叠加</label>
              <n-switch id="show-mask" v-model:value="showMask" :disabled="!maskBase64" />
            </div>
            <div class="stacked-control" :class="{ disabled: !maskBase64 }">
              <div><label>Mask 透明度</label><span>{{ Math.round(maskOpacity * 100) }}%</span></div>
              <n-slider v-model:value="maskOpacity" :min="0.1" :max="1" :step="0.05" :disabled="!maskBase64" />
            </div>
            <div class="window-grid">
              <label>
                <span>窗位</span>
                <n-input-number v-model:value="windowCenter" size="small" :precision="2" :show-button="false" />
              </label>
              <label>
                <span>窗宽</span>
                <n-input-number v-model:value="windowWidth" size="small" :min="0.0001" :precision="2" :show-button="false" />
              </label>
            </div>
            <div class="window-actions">
              <n-button size="small" type="primary" @click="applyWindow">应用窗宽窗位</n-button>
              <n-button size="small" quaternary @click="resetWindow">
                <template #icon><n-icon><ReloadOutline /></n-icon></template>
                自动
              </n-button>
            </div>
          </section>

          <section class="inspector-section">
            <div class="panel-heading"><h2>检查信息</h2></div>
            <dl class="metadata-list">
              <div><dt>患者</dt><dd>{{ viewerInfo.patient.patient_id || "匿名" }}</dd></div>
              <div><dt>模态</dt><dd>{{ viewerInfo.study.modality || "—" }}</dd></div>
              <div><dt>矩阵</dt><dd>{{ viewerInfo.study.cols }} × {{ viewerInfo.study.rows }}</dd></div>
              <div><dt>体素间距</dt><dd>{{ spacingLabel }}</dd></div>
              <div><dt>层厚</dt><dd>{{ viewerInfo.study.slice_thickness.toFixed(2) }} mm</dd></div>
              <div><dt>格式</dt><dd>TICI {{ viewerInfo.format_version }}</dd></div>
            </dl>
          </section>

          <section class="inspector-section">
            <div class="panel-heading"><h2>封装内容</h2></div>
            <div class="content-flags">
              <n-tag :type="hasAnyMask ? 'success' : 'default'" size="small">
                {{ hasAnyMask ? "包含 Mask" : "无 Mask" }}
              </n-tag>
              <n-tag :type="viewerInfo.has_igtv ? 'success' : 'default'" size="small">
                {{ viewerInfo.has_igtv ? "包含 IGTV" : "无 IGTV" }}
              </n-tag>
              <n-tag :type="viewerInfo.has_trajectory ? 'success' : 'default'" size="small">
                {{ viewerInfo.has_trajectory ? "包含轨迹" : "无轨迹" }}
              </n-tag>
            </div>
            <dl class="metadata-list provenance">
              <div><dt>来源</dt><dd>{{ viewerInfo.provenance.source_type || "—" }}</dd></div>
              <div><dt>转换器</dt><dd>{{ viewerInfo.provenance.converter_version || "—" }}</dd></div>
            </dl>
          </section>

          <footer class="shortcut-help">
            <strong>快捷键</strong>
            <span>↑ ↓ 切片</span>
            <span>PageUp / PageDown 时相</span>
            <span>空格 播放或暂停</span>
          </footer>
        </aside>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NIcon,
  NInputNumber,
  NProgress,
  NSelect,
  NSkeleton,
  NSlider,
  NSwitch,
  NTag,
  useMessage,
} from "naive-ui";
import {
  AddOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CloseOutline,
  CloudUploadOutline,
  EyeOutline,
  FolderOpenOutline,
  InformationCircleOutline,
  LayersOutline,
  PauseOutline,
  PlayBackOutline,
  PlayForwardOutline,
  PlayOutline,
  ReloadOutline,
  RemoveOutline,
  ScanOutline,
} from "@vicons/ionicons5";
import TiciViewport from "@/components/tici/TiciViewport.vue";
import { closeTiciFile, loadTiciSlice, openTiciFile } from "@/features/tici/api";
import { getPhaseIndex, type TiciViewerInfo } from "@/features/tici/types";
import { readClientPreferences } from "@/stores/preferences";

const message = useMessage();
const initialPreferences = readClientPreferences();
const pageRef = ref<HTMLElement>();
const fileInputRef = ref<HTMLInputElement>();
const replaceInputRef = ref<HTMLInputElement>();

const viewerInfo = ref<TiciViewerInfo | null>(null);
const filename = ref("");
const opening = ref(false);
const uploadProgress = ref(0);
const openError = ref("");
const viewError = ref("");
const isDragging = ref(false);

const currentPhasePosition = ref(0);
const currentSlice = ref(0);
const imageBase64 = ref("");
const maskBase64 = ref("");
const sliceLoading = ref(false);
const phaseThumbnails = ref<Record<string, string>>({});
const windowCenter = ref(0.5);
const windowWidth = ref(1);
const windowInitialized = ref(false);
const showMask = ref(true);
const maskOpacity = ref(initialPreferences.maskOpacityPercent / 100);
const zoom = ref(1);
const playing = ref(false);
const playbackFps = ref(3);

const fpsOptions = [1, 3, 5, 8, 10].map((value) => ({
  label: `${value} FPS`,
  value,
}));

const currentPhase = computed(() =>
  viewerInfo.value?.phases[currentPhasePosition.value],
);
const currentPhaseNumber = computed(() =>
  currentPhase.value ? getPhaseIndex(currentPhase.value) : 0,
);
const currentSliceCount = computed(() => currentPhase.value?.shape?.[0] || 0);
const currentDimensions = computed(() => {
  const shape = currentPhase.value?.shape;
  return shape && shape.length >= 3 ? `${shape[2]} × ${shape[1]}` : "—";
});
const hasAnyMask = computed(() =>
  viewerInfo.value?.phases.some((phase) => phase.has_masks) || false,
);
const spacingLabel = computed(() => {
  const spacing = viewerInfo.value?.study.pixel_spacing || [];
  return spacing.length >= 2
    ? `${Number(spacing[0]).toFixed(2)} × ${Number(spacing[1]).toFixed(2)} mm`
    : "—";
});
const displayWindowCenter = computed(() => formatWindow(windowCenter.value));
const displayWindowWidth = computed(() => formatWindow(windowWidth.value));

let playbackTimer: ReturnType<typeof setInterval> | null = null;
let loadTimer: ReturnType<typeof setTimeout> | null = null;
let requestSerial = 0;
let wheelLocked = false;

function chooseFile() {
  fileInputRef.value?.click();
}

function chooseReplacement() {
  replaceInputRef.value?.click();
}

function handleFileInput(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) void openFile(file);
}

function handleDrop(event: DragEvent) {
  isDragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) void openFile(file);
}

async function openFile(file: File) {
  openError.value = "";
  viewError.value = "";
  if (!file.name.toLowerCase().endsWith(".tici")) {
    openError.value = "文件格式不正确，请选择 .tici 文件。";
    return;
  }
  if (file.size > 2 * 1024 * 1024 * 1024) {
    openError.value = "文件超过 2 GB，当前查看器无法打开。";
    return;
  }

  opening.value = true;
  uploadProgress.value = 0;
  const previousViewerId = viewerInfo.value?.viewer_id;
  try {
    const info = await openTiciFile(file, (percent) => {
      uploadProgress.value = percent;
    });
    if (previousViewerId) {
      await closeTiciFile(previousViewerId).catch(() => undefined);
    }
    viewerInfo.value = info;
    filename.value = file.name;
    currentPhasePosition.value = 0;
    currentSlice.value = Math.floor((info.phases[0]?.shape?.[0] || 1) / 2);
    windowInitialized.value = false;
    phaseThumbnails.value = {};
    zoom.value = 1;
    await loadCurrentSlice(true);
    void loadPhaseThumbnails();
    await nextTick();
    pageRef.value?.focus();
    message.success(`已打开 ${info.phases.length} 个时相`);
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    openError.value = typeof detail === "string" ? detail : "无法打开该 TICI 文件。";
  } finally {
    opening.value = false;
  }
}

async function loadCurrentSlice(resetWindow = false) {
  const info = viewerInfo.value;
  if (!info || !currentPhase.value) return;
  const serial = ++requestSerial;
  sliceLoading.value = true;
  viewError.value = "";
  try {
    const data = await loadTiciSlice(
      info.viewer_id,
      currentPhaseNumber.value,
      currentSlice.value,
      resetWindow || !windowInitialized.value
        ? { includeMask: true }
        : {
            windowCenter: windowCenter.value,
            windowWidth: windowWidth.value,
            includeMask: true,
          },
    );
    if (serial !== requestSerial) return;
    imageBase64.value = data.image_base64;
    maskBase64.value = data.mask_base64 || "";
    if (resetWindow || !windowInitialized.value) {
      windowCenter.value = Number(data.window_center.toFixed(2));
      windowWidth.value = Number(data.window_width.toFixed(2));
      windowInitialized.value = true;
    }
  } catch (error: any) {
    if (serial !== requestSerial) return;
    imageBase64.value = "";
    maskBase64.value = "";
    viewError.value = error?.response?.data?.detail || "切片读取失败。";
  } finally {
    if (serial === requestSerial) sliceLoading.value = false;
  }
}

async function loadPhaseThumbnails() {
  const info = viewerInfo.value;
  if (!info) return;
  for (const phase of info.phases) {
    if (viewerInfo.value?.viewer_id !== info.viewer_id) return;
    const slice = Math.floor((phase.shape?.[0] || 1) / 2);
    try {
      const data = await loadTiciSlice(
        info.viewer_id,
        getPhaseIndex(phase),
        slice,
        { includeMask: false },
      );
      phaseThumbnails.value = {
        ...phaseThumbnails.value,
        [phase.phase]: data.image_base64,
      };
    } catch {
      // A missing thumbnail should not block diagnostic viewing.
    }
  }
}

function selectPhase(position: number) {
  const info = viewerInfo.value;
  if (!info) return;
  const next = Math.min(Math.max(Math.round(position), 0), info.phases.length - 1);
  currentPhasePosition.value = next;
  currentSlice.value = Math.min(
    currentSlice.value,
    Math.max(0, (info.phases[next]?.shape?.[0] || 1) - 1),
  );
  void loadCurrentSlice();
}

function stepPhase(delta: number) {
  const count = viewerInfo.value?.phases.length || 0;
  if (count <= 1) return;
  selectPhase((currentPhasePosition.value + delta + count) % count);
}

function stepSlice(delta: number) {
  const next = Math.min(
    Math.max(currentSlice.value + delta, 0),
    Math.max(0, currentSliceCount.value - 1),
  );
  if (next === currentSlice.value) return;
  currentSlice.value = next;
  void loadCurrentSlice();
}

function scheduleSliceLoad() {
  if (loadTimer) clearTimeout(loadTimer);
  loadTimer = setTimeout(() => void loadCurrentSlice(), 70);
}

function applyWindow() {
  if (windowWidth.value <= 0) {
    viewError.value = "窗宽必须大于 0。";
    return;
  }
  void loadCurrentSlice();
}

function resetWindow() {
  windowInitialized.value = false;
  void loadCurrentSlice(true);
}

function changeZoom(delta: number) {
  zoom.value = Math.min(4, Math.max(0.5, Number((zoom.value + delta).toFixed(2))));
}

function handleWheel(event: WheelEvent) {
  if (event.ctrlKey) {
    changeZoom(event.deltaY > 0 ? -0.1 : 0.1);
    return;
  }
  if (wheelLocked) return;
  wheelLocked = true;
  stepSlice(event.deltaY > 0 ? 1 : -1);
  window.setTimeout(() => { wheelLocked = false; }, 70);
}

function handleKeyboard(event: KeyboardEvent) {
  const target = event.target as HTMLElement;
  if (["INPUT", "TEXTAREA"].includes(target.tagName)) return;
  if (event.key === "ArrowUp") { event.preventDefault(); stepSlice(-1); }
  if (event.key === "ArrowDown") { event.preventDefault(); stepSlice(1); }
  if (event.key === "PageUp") { event.preventDefault(); stepPhase(-1); }
  if (event.key === "PageDown") { event.preventDefault(); stepPhase(1); }
  if (event.code === "Space") { event.preventDefault(); playing.value = !playing.value; }
}

async function closeViewer() {
  const viewerId = viewerInfo.value?.viewer_id;
  stopPlayback();
  viewerInfo.value = null;
  imageBase64.value = "";
  maskBase64.value = "";
  phaseThumbnails.value = {};
  if (viewerId) await closeTiciFile(viewerId).catch(() => undefined);
}

function startPlayback() {
  stopPlayback();
  playbackTimer = setInterval(() => stepPhase(1), 1000 / playbackFps.value);
}

function stopPlayback() {
  if (playbackTimer) {
    clearInterval(playbackTimer);
    playbackTimer = null;
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatWindow(value: number): string {
  if (Math.abs(value) >= 10) return value.toFixed(0);
  return value.toFixed(2);
}

watch(playing, (value) => value ? startPlayback() : stopPlayback());
watch(playbackFps, () => { if (playing.value) startPlayback(); });

onBeforeUnmount(() => {
  stopPlayback();
  if (loadTimer) clearTimeout(loadTimer);
  const viewerId = viewerInfo.value?.viewer_id;
  if (viewerId) void closeTiciFile(viewerId).catch(() => undefined);
});
</script>

<style scoped>
.tici-page {
  min-width: 0;
  color: var(--color-text);
  outline: none;
}

.page-intro,
.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.page-intro {
  max-width: 960px;
  margin: 0 auto var(--space-lg);
}

.page-intro h1,
.viewer-header h1 {
  margin: 0;
  color: var(--color-text);
  font-size: 20px;
  line-height: 1.3;
}

.page-intro p,
.viewer-header p {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.open-panel {
  display: flex;
  max-width: 960px;
  min-height: 390px;
  margin: 0 auto;
  padding: 56px 32px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px dashed #94a3b8;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  text-align: center;
  transition: border-color 180ms ease-out, background 180ms ease-out;
}

.open-panel.dragging {
  border-color: var(--color-primary);
  background: #eff6ff;
}

.open-icon {
  display: grid;
  width: 64px;
  height: 64px;
  margin-bottom: 20px;
  place-items: center;
  border-radius: 14px;
  background: #e8f2fc;
  color: var(--color-primary-dark);
}

.open-panel h2 {
  margin: 0;
  font-size: 18px;
}

.open-panel p {
  max-width: 55ch;
  margin: 8px 0 24px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.drop-hint {
  margin-top: 12px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.upload-progress {
  width: min(420px, 100%);
  margin-top: 24px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.upload-progress span {
  display: block;
  margin-top: 8px;
}

.open-error {
  max-width: 960px;
  margin: 16px auto 0;
}

.capability-row {
  display: flex;
  max-width: 960px;
  margin: 20px auto 0;
  justify-content: center;
  gap: 28px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.capability-row div {
  display: flex;
  align-items: center;
  gap: 6px;
}

.viewer-header {
  min-height: 56px;
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.file-identity,
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.file-identity > .n-icon {
  flex: 0 0 auto;
  color: var(--color-primary);
}

.file-identity h1 {
  max-width: 44vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewer-alert {
  margin-bottom: 12px;
}

.viewer-shell {
  display: grid;
  min-height: 640px;
  height: calc(100vh - 148px);
  grid-template-columns: 164px minmax(420px, 1fr) 288px;
  overflow: hidden;
  border: 1px solid #233044;
  border-radius: 10px;
  background: #0b1017;
}

.phase-panel {
  min-width: 0;
  overflow: hidden;
  border-right: 1px solid #263346;
  background: #101722;
  color: #dbe6f4;
}

.panel-heading {
  display: flex;
  min-height: 44px;
  padding: 0 14px;
  align-items: center;
  justify-content: space-between;
}

.panel-heading h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.phase-panel .panel-heading span {
  color: #8ca0b8;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.phase-list {
  height: calc(100% - 44px);
  padding: 0 8px 12px;
  overflow-y: auto;
}

.phase-item {
  display: grid;
  width: 100%;
  min-height: 68px;
  margin-bottom: 6px;
  padding: 7px;
  grid-template-columns: 56px minmax(0, 1fr) 8px;
  align-items: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: #dbe6f4;
  cursor: pointer;
  text-align: left;
  transition: background 160ms ease-out, border-color 160ms ease-out;
}

.phase-item:hover {
  background: #182232;
}

.phase-item:focus-visible {
  outline: 2px solid #60a5fa;
  outline-offset: 1px;
}

.phase-item.active {
  border-color: #3b82f6;
  background: #1a2b42;
}

.phase-thumb {
  display: block;
  width: 56px;
  height: 52px;
  overflow: hidden;
  border-radius: 4px;
  background: #03060a;
}

.phase-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.phase-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.phase-copy strong {
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.phase-copy small {
  color: #8ca0b8;
  font-size: 10px;
}

.mask-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #f87171;
}

.image-workspace {
  display: grid;
  min-width: 0;
  grid-template-rows: minmax(0, 1fr) 48px 52px;
  background: #05080d;
}

.viewport-wrap {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.viewport-label {
  position: absolute;
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: #d8e3ef;
  font-size: 11px;
  line-height: 1.35;
  text-shadow: 0 1px 2px #000;
  pointer-events: none;
  font-variant-numeric: tabular-nums;
}

.top-left { top: 12px; left: 14px; }
.top-right { top: 12px; right: 14px; text-align: right; }
.bottom-left { bottom: 12px; left: 14px; }
.bottom-right { bottom: 12px; right: 14px; text-align: right; }

.slice-toolbar,
.cine-toolbar {
  display: flex;
  padding: 0 12px;
  align-items: center;
  gap: 6px;
  border-top: 1px solid #263346;
  background: #101722;
  color: #dbe6f4;
}

.slice-toolbar :deep(.n-slider),
.cine-toolbar :deep(.n-slider) {
  flex: 1;
}

.toolbar-value {
  min-width: 32px;
  text-align: center;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.toolbar-value.muted {
  color: #8ca0b8;
}

.toolbar-divider {
  width: 1px;
  height: 22px;
  margin: 0 6px;
  background: #344258;
}

.zoom-reset {
  min-width: 52px;
  font-variant-numeric: tabular-nums;
}

.fps-select {
  width: 88px;
}

.inspector-panel {
  overflow-y: auto;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
}

.inspector-section {
  padding: 4px 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

.inspector-section .panel-heading {
  padding: 0;
}

.control-row,
.stacked-control > div {
  display: flex;
  min-height: 36px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.stacked-control {
  margin-top: 6px;
}

.stacked-control.disabled {
  opacity: 0.55;
}

.stacked-control span {
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.window-grid {
  display: grid;
  margin-top: 14px;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.window-grid label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.window-actions {
  display: flex;
  margin-top: 10px;
  gap: 6px;
}

.metadata-list {
  margin: 0;
}

.metadata-list > div {
  display: grid;
  min-height: 28px;
  grid-template-columns: 76px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  font-size: 12px;
}

.metadata-list dt {
  color: var(--color-text-secondary);
}

.metadata-list dd {
  margin: 0;
  overflow-wrap: anywhere;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.content-flags {
  display: flex;
  padding-bottom: 12px;
  flex-wrap: wrap;
  gap: 6px;
}

.provenance {
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.shortcut-help {
  display: flex;
  padding: 14px;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.shortcut-help strong {
  margin-bottom: 2px;
  color: var(--color-text);
  font-size: 12px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1200px) {
  .viewer-shell {
    height: auto;
    grid-template-columns: 140px minmax(400px, 1fr);
  }

  .image-workspace {
    min-height: 650px;
  }

  .inspector-panel {
    display: grid;
    grid-column: 1 / -1;
    grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }

  .shortcut-help {
    display: none;
  }
}

@media (max-width: 820px) {
  .page-intro,
  .viewer-header,
  .capability-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }

  .viewer-shell {
    display: flex;
    flex-direction: column;
  }

  .phase-panel {
    border-right: 0;
    border-bottom: 1px solid #263346;
  }

  .phase-list {
    display: flex;
    height: auto;
    padding-bottom: 8px;
    overflow-x: auto;
  }

  .phase-item {
    min-width: 142px;
  }

  .inspector-panel {
    display: block;
  }

  .image-workspace {
    min-height: 580px;
  }

  .capability-row {
    gap: 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .open-panel,
  .phase-item {
    transition: none;
  }
}
</style>
