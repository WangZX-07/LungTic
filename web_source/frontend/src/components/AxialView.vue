<template>
  <div class="axial-view">
    <n-grid cols="4" x-gap="16">
      <n-grid-item span="3">
        <n-card size="small" title="CT 横断面视图" class="viewer-card">
          <template #header-extra>
            <n-space align="center">
              <n-tag v-if="currentSlice" size="small">层 {{ currentSliceIndex }} / {{ totalSlices }}</n-tag>
              <n-tag v-if="currentSlice" size="small" type="info">Z: {{ currentSlice?.z_position?.toFixed(1) || "-" }} mm</n-tag>
            </n-space>
          </template>
          <div class="canvas-area" ref="canvasAreaRef" @keydown="onKeydown" tabindex="0">
            <div v-if="!hasImage && !imageLoading" class="canvas-placeholder">
              <n-icon size="64" color="#CBD5E1"><ImageOutline /></n-icon>
              <p>选择时相和切片查看 CT 图像</p>
            </div>
            <n-spin v-if="imageLoading" class="loading-overlay" />
            <div ref="cornerstoneElementRef" class="cornerstone-element" :style="{ display: useCornerstone && hasImage ? 'block' : 'none' }" @contextmenu.prevent />
            <canvas v-if="!useCornerstone && hasImage" ref="fallbackCanvasRef" class="fallback-canvas" />
          </div>
          <Filmstrip v-if="hasImage && totalSlices > 1" :series-id="currentSeriesId" :current-slice="currentSliceIndex" :total-slices="totalSlices" @select="onFilmstripSelect" style="margin-top:8px" />
          <div v-if="hasImage" class="image-toolbar">
            <n-space :size="8" align="center">
              <n-button size="tiny" quaternary @click="zoomIn"><template #icon><n-icon><AddCircleOutline /></n-icon></template></n-button>
              <n-button size="tiny" quaternary @click="zoomOut"><template #icon><n-icon><RemoveCircleOutline /></n-icon></template></n-button>
              <n-button size="tiny" quaternary @click="fitToWindow"><template #icon><n-icon><ExpandOutline /></n-icon></template>适应</n-button>
              <n-divider vertical />
              <n-button size="tiny" quaternary @click="prevSlice" :disabled="currentSliceIndex <= 1"><template #icon><n-icon><ChevronUpOutline /></n-icon></template>上层</n-button>
              <n-button size="tiny" quaternary @click="nextSlice" :disabled="currentSliceIndex >= totalSlices"><template #icon><n-icon><ChevronDownOutline /></n-icon></template>下层</n-button>
              <n-divider vertical />
              <span class="toolbar-label">窗宽</span>
              <n-input-number v-model:value="windowWidth" size="tiny" :min="1" :max="4000" style="width:80px" @update:value="updateWindowing" />
              <span class="toolbar-label">窗位</span>
              <n-input-number v-model:value="windowCenter" size="tiny" :min="-1024" :max="3071" style="width:80px" @update:value="updateWindowing" />
              <n-button size="tiny" quaternary @click="resetWindowing">重置</n-button>
            </n-space>
          </div>
        </n-card>
      </n-grid-item>
      <n-grid-item span="1">
        <n-space vertical :size="16">
          <n-card size="small" title="时相">
            <n-slider v-model:value="currentPhase" :min="0" :max="phaseCount - 1" :step="1" :marks="phaseMarks" @update:value="onPhaseChange" />
          </n-card>
          <n-card size="small" title="层数">
            <n-slider v-model:value="currentSliceIndex" :min="1" :max="totalSlices || 1" :step="1" :disabled="!totalSlices" @update:value="onSliceChange" />
          </n-card>
          <n-card size="small" title="分割信息">
            <n-spin :show="segLoading" size="small">
              <div v-if="diceScore !== null" class="info-block">
                <div class="info-item"><span class="label">Dice</span><n-tag :type="diceScore > 0.85 ? 'success' : diceScore > 0.7 ? 'warning' : 'error'">{{ diceScore.toFixed(3) }}</n-tag></div>
                <div class="info-item"><span class="label">模型</span><span>{{ modelVersion || "内置" }}</span></div>
              </div>
              <p v-else class="text-muted">未执行分割</p>
            </n-spin>
          </n-card>
          <n-card size="small" title="显示选项">
            <n-space vertical :size="8">
              <n-checkbox v-model:checked="showMask">显示 Mask</n-checkbox>
              <div class="setting-row"><span>透明度</span><n-slider v-model:value="maskOpacity" :min="0.1" :max="1" :step="0.1" style="width:100px" /></div>
            </n-space>
          </n-card>
          <n-card size="small" title="窗宽窗位预设">
            <n-space vertical :size="4">
              <n-button size="tiny" quaternary block @click="setPreset('lung')">肺窗 (1500/-600)</n-button>
              <n-button size="tiny" quaternary block @click="setPreset('mediastinum')">纵隔窗 (350/50)</n-button>
              <n-button size="tiny" quaternary block @click="setPreset('bone')">骨窗 (2000/350)</n-button>
              <n-button size="tiny" quaternary block @click="setPreset('default')">默认 (400/40)</n-button>
            </n-space>
          </n-card>
        </n-space>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import {
  NGrid, NGridItem, NCard, NSpace, NButton, NIcon, NTag, NSlider, NSpin, NCheckbox, NSwitch,
  NDivider, NInputNumber, useMessage,
} from "naive-ui";
import {
  ImageOutline, AddCircleOutline, RemoveCircleOutline, ExpandOutline,
  ChevronUpOutline, ChevronDownOutline,
} from "@vicons/ionicons5";
import api from "@/api";
import Filmstrip from "@/components/Filmstrip.vue";
import { getWindowPreset, readClientPreferences } from "@/stores/preferences";

const props = defineProps<{ studyId: number }>();
const initialPreferences = readClientPreferences();
const initialWindow = getWindowPreset(initialPreferences.defaultPreset);

const canvasAreaRef = ref<HTMLDivElement>();
const cornerstoneElementRef = ref<HTMLDivElement>();
const fallbackCanvasRef = ref<HTMLCanvasElement>();
const useCornerstone = ref(false);

let cornerstoneRenderingEngine: any = null;
let cornerstoneViewport: any = null;
let cornerstoneInitAttempted = false;

const phases = ref<any[]>([]);
const phaseCount = ref(10);
const currentPhase = ref(0);
const slices = ref<any[]>([]);
const totalSlices = ref(0);
const currentSliceIndex = ref(1);
const currentSlice = ref<any>(null);
const currentSeriesId = ref<number | null>(null);
const hasImage = ref(false);
const imageLoading = ref(false);
const imageBase64 = ref("");

const windowWidth = ref(initialWindow.width);
const windowCenter = ref(initialWindow.center);
const showMask = ref(false);
const maskOpacity = ref(initialPreferences.maskOpacityPercent / 100);
const diceScore = ref<number | null>(null);
const modelVersion = ref("");
const segLoading = ref(false);

const phaseMarks = computed(() => {
  const marks: Record<number, string> = {};
  for (let i = 0; i < phaseCount.value; i++) marks[i] = `P${i}`;
  return marks;
});

// Cornerstone initialization
async function initCornerstone() {
  if (cornerstoneInitAttempted) return;
  cornerstoneInitAttempted = true;

  try {
    const cornerstone = await import("@cornerstonejs/core");
    const dicomImageLoader = await import("@cornerstonejs/dicom-image-loader");
    const cornerstoneTools = await import("@cornerstonejs/tools");

    await cornerstone.init();
    // Configure DICOM image loader
    dicomImageLoader.init({
      maxWebWorkers: 2,
      strict: false,
    });

    const { RenderingEngine, Enums } = cornerstone;
    const { ToolGroupManager, WindowLevelTool, ZoomTool, PanTool, StackScrollTool } = cornerstoneTools;
    const { MouseBindings, KeyboardBindings } = cornerstoneTools.Enums;
    const { ViewportType } = Enums;

    const renderingEngineId = "myRenderingEngine";
    const renderingEngine = new RenderingEngine(renderingEngineId);

    const viewportId = "stackViewport";
    const viewportInput = {
      viewportId,
      type: ViewportType.STACK,
      element: cornerstoneElementRef.value as HTMLDivElement,
    };

    renderingEngine.enableElement(viewportInput);
    const viewport = renderingEngine.getViewport(viewportId) as any;

    const toolGroupId = "myToolGroup";
    const toolGroup = ToolGroupManager.createToolGroup(toolGroupId);
    if (!toolGroup) throw new Error("Unable to create Cornerstone tool group");
    toolGroup.addTool(WindowLevelTool.toolName);
    toolGroup.addTool(ZoomTool.toolName);
    toolGroup.addTool(PanTool.toolName);
    toolGroup.addTool(StackScrollTool.toolName);
    toolGroup.setToolActive(WindowLevelTool.toolName);
    toolGroup.setToolActive(ZoomTool.toolName, { bindings: [{ mouseButton: MouseBindings.Secondary }] });
    toolGroup.setToolActive(PanTool.toolName, { bindings: [{ mouseButton: MouseBindings.Secondary, modifierKey: KeyboardBindings.Shift }] });
    toolGroup.setToolActive(StackScrollTool.toolName, { bindings: [{ mouseButton: MouseBindings.Wheel }] });
    toolGroup.addViewport(viewportId, renderingEngineId);

    cornerstoneRenderingEngine = renderingEngine;
    cornerstoneViewport = viewport;
    useCornerstone.value = true;
  } catch (err) {
    console.warn("Cornerstone.js initialization failed, falling back to base64 PNG:", err);
    useCornerstone.value = false;
  }
}

async function loadCornerstoneImage() {
  const slc = slices.value[currentSliceIndex.value - 1];
  if (!slc || !cornerstoneViewport) return;

  try {
    const imageId = `wadouri:/api/dicom/slice/${slc.id}/dicom`;
    // Load via cornerstone's image loader
    const imageIdObj = { imageId } as any;
    // Use the import to get cornerstone utilities
    const csCore = await import("@cornerstonejs/core");
    if (cornerstoneViewport) {
      const stack = [imageId];
      await cornerstoneViewport.setStack(stack);
      updateWindowing();
    }
  } catch {
    // Fallback to base64
    useCornerstone.value = false;
    loadImage();
  }
}

function renderFallbackImage() {
  if (!fallbackCanvasRef.value || !imageBase64.value) return;
  const canvas = fallbackCanvasRef.value;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const img = new Image();
  img.onload = () => {
    canvas.width = img.width;
    canvas.height = img.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.filter = `brightness(${110}%) contrast(${100}%)`;
    ctx.drawImage(img, 0, 0);
    applyFallbackWindowing();
  };
  img.src = "data:image/png;base64," + imageBase64.value;
}

function applyFallbackWindowing() {
  const canvas = fallbackCanvasRef.value;
  if (!canvas) return;
  canvas.style.filter = `brightness(${110}%) contrast(${100}%)`;
}

function updateWindowing() {
  if (useCornerstone.value && cornerstoneViewport) {
    try {
      cornerstoneViewport.setProperties({
        voiRange: { lower: windowCenter.value - windowWidth.value / 2, upper: windowCenter.value + windowWidth.value / 2 },
      });
      cornerstoneViewport.render();
    } catch {}
  } else {
    applyFallbackWindowing();
  }
}

function setPreset(type: string) {
  switch (type) {
    case "lung": windowWidth.value = 1500; windowCenter.value = -600; break;
    case "mediastinum": windowWidth.value = 350; windowCenter.value = 50; break;
    case "bone": windowWidth.value = 2000; windowCenter.value = 350; break;
    default: windowWidth.value = 400; windowCenter.value = 40;
  }
  updateWindowing();
}

function resetWindowing() { setPreset(readClientPreferences().defaultPreset); }

function zoomIn() { if (useCornerstone.value && cornerstoneViewport) { try { const zoom = cornerstoneViewport.getZoom() || 1; cornerstoneViewport.setZoom(zoom * 1.25); cornerstoneViewport.render(); } catch {} } }
function zoomOut() { if (useCornerstone.value && cornerstoneViewport) { try { const zoom = cornerstoneViewport.getZoom() || 1; cornerstoneViewport.setZoom(zoom * 0.8); cornerstoneViewport.render(); } catch {} } }
function fitToWindow() { if (useCornerstone.value && cornerstoneViewport) { try { cornerstoneViewport.resetCamera(); cornerstoneViewport.render(); } catch {} } }

function prevSlice() { if (currentSliceIndex.value > 1) { currentSliceIndex.value--; onSliceChange(); } }
function nextSlice() { if (currentSliceIndex.value < totalSlices.value) { currentSliceIndex.value++; onSliceChange(); } }

function onKeydown(e: KeyboardEvent) {
  if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); prevSlice(); }
  if (e.key === "ArrowDown" || e.key === "ArrowRight") { e.preventDefault(); nextSlice(); }
  if (e.key === "PageUp") { e.preventDefault(); currentPhase.value = Math.max(0, currentPhase.value - 1); onPhaseChange(); }
  if (e.key === "PageDown") { e.preventDefault(); currentPhase.value = Math.min(phaseCount.value - 1, currentPhase.value + 1); onPhaseChange(); }
}

async function loadPhases() {
  try {
    const r = await api.get(`/dicom/studies/${props.studyId}/phases`);
    phases.value = r.data;
    phaseCount.value = r.data.length || 10;
    if (phases.value.length > 0) await loadSlices();
  } catch {}
}

async function loadSlices() {
  const phase = phases.value[currentPhase.value];
  if (!phase) return;
  currentSeriesId.value = phase?.id || null;
  try {
    const r = await api.get(`/dicom/series/${phase.id}/slices`);
    slices.value = r.data;
    totalSlices.value = r.data.length;
    if (r.data.length > 0) { currentSliceIndex.value = 1; await loadImage(); }
  } catch { totalSlices.value = 0; hasImage.value = false; }
}

async function loadImage() {
  const slc = slices.value[currentSliceIndex.value - 1];
  if (!slc) return;
  currentSlice.value = slc;
  imageLoading.value = true;

  try {
    if (useCornerstone.value) {
      await loadCornerstoneImage();
    } else {
      const r = await api.get(`/dicom/slice/${slc.id}/image`);
      imageBase64.value = r.data?.image_base64 || r.data;
      hasImage.value = !!imageBase64.value;
      await nextTick();
      renderFallbackImage();
    }
    hasImage.value = true;
  } catch { hasImage.value = false; } finally { imageLoading.value = false; }
}

function onFilmstripSelect(index: number) { currentSliceIndex.value = index; onSliceChange(); }
function onPhaseChange() { loadSlices(); }
function onSliceChange() { loadImage(); }

async function loadSegResult() {
  segLoading.value = true;
  try {
    const r = await api.get(`/segmentation/${props.studyId}/result`);
    if (r.data) { diceScore.value = r.data.mean_dice ?? null; modelVersion.value = r.data.model_version || ""; }
  } catch {} finally { segLoading.value = false; }
}

onMounted(async () => {
  await initCornerstone();
  loadPhases();
  loadSegResult();
});

onBeforeUnmount(() => {
  if (cornerstoneRenderingEngine) {
    try { cornerstoneRenderingEngine.destroy(); } catch {}
  }
});
</script>
<style scoped>
.axial-view { width: 100%; }
.viewer-card { height: 100%; }
.canvas-area { position: relative; min-height: 400px; background: #0F172A; border-radius: 8px; display: flex; align-items: center; justify-content: center; overflow: hidden; outline: none; cursor: crosshair; }
.canvas-placeholder { text-align: center; color: #64748B; z-index: 1; }
.canvas-placeholder p { margin-top: 16px; }
.loading-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; z-index: 2; }
.cornerstone-element { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
.fallback-canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain; }
.image-toolbar { margin-top: 12px; padding: 8px 12px; background: #F8FAFC; border-radius: 8px; border: 1px solid #E2E8F0; overflow-x: auto; }
.toolbar-label { font-size: 11px; color: #64748B; white-space: nowrap; }
.info-block { font-size: 12px; }
.info-item { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
.label { color: #64748B; }
.text-muted { color: #94A3B8; font-size: 12px; }
.setting-row { display: flex; align-items: center; justify-content: space-between; font-size: 12px; }
</style>
