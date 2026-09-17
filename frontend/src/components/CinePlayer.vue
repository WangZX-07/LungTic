<template>
  <div class="cine-player">
    <div class="cine-controls">
      <n-space align="center" :size="8">
        <!-- Play/Pause -->
        <n-button
          quaternary
          circle
          size="small"
          @click="togglePlay"
        >
          <template #icon>
            <n-icon>
              <PlayOutline v-if="!playing" />
              <PauseOutline v-else />
            </n-icon>
          </template>
        </n-button>

        <!-- Phase indicator -->
        <div class="phase-display">
          <span class="phase-current">Phase {{ currentPhase }}</span>
          <span class="phase-sep">/</span>
          <span class="phase-total">{{ totalPhases - 1 }}</span>
        </div>

        <!-- Progress bar with phase markers -->
        <div class="cine-track" ref="trackRef" @mousedown="onTrackClick">
          <div
            class="cine-track-fill"
            :style="{ width: trackPercent + '%' }"
          />
          <div
            v-for="p in totalPhases"
            :key="p"
            class="cine-tick"
            :class="{ active: p - 1 === currentPhase }"
            :style="{ left: ((p - 1) / (totalPhases - 1)) * 100 + '%' }"
          />
        </div>

        <!-- Speed control -->
        <n-select
          v-model:value="speed"
          :options="speedOptions"
          size="tiny"
          style="width:80px"
        />

        <!-- Frame navigation -->
        <n-button-group size="tiny">
          <n-button quaternary @click="prevPhase" :disabled="currentPhase <= 0">
            <template #icon><n-icon><PlayBackOutline /></n-icon></template>
          </n-button>
          <n-button quaternary @click="nextPhase" :disabled="currentPhase >= totalPhases - 1">
            <template #icon><n-icon><PlayForwardOutline /></n-icon></template>
          </n-button>
        </n-button-group>

        <!-- Loop toggle -->
        <n-button
          quaternary
          circle
          size="tiny"
          :type="loop ? 'primary' : 'default'"
          @click="loop = !loop"
        >
          <template #icon><n-icon><RepeatOutline /></n-icon></template>
        </n-button>
      </n-space>
    </div>

    <!-- Cine viewport: shows current phase image sequence -->
    <div class="cine-viewport" ref="viewportRef">
      <div v-if="!hasPhases" class="cine-placeholder">
        <n-icon size="48" color="#CBD5E1"><FilmOutline /></n-icon>
        <p>4D Cine 播放器</p>
        <p class="hint">加载 DICOM 序列后可播放呼吸周期影像</p>
      </div>
      <div v-else class="cine-frames">
        <img
          v-for="(img, idx) in phaseFrames"
          :key="idx"
          :src="img ? 'data:image/png;base64,' + img : ''"
          class="cine-frame"
          :class="{
            active: idx === currentPhase,
            prev: idx === currentPhase - 1,
            next: idx === currentPhase + 1,
          }"
          :style="{ opacity: idx === currentPhase ? 1 : 0 }"
        />
      </div>
      <!-- Overlay: phase label -->
      <div v-if="hasPhases" class="cine-overlay">
        <span class="cine-overlay-label">
          Phase {{ currentPhase }} · {{ speed }} FPS
          <template v-if="loop"> · 循环</template>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import {
  NSpace, NButton, NIcon, NSelect, NButtonGroup,
} from "naive-ui";
import {
  PlayOutline, PauseOutline, PlayBackOutline, PlayForwardOutline,
  RepeatOutline, FilmOutline,
} from "@vicons/ionicons5";

const props = defineProps<{
  phases: any[];
  currentPhaseIndex: number;
}>();

const emit = defineEmits<{
  "update:currentPhaseIndex": [value: number];
}>();

const playing = ref(false);
const loop = ref(true);
const speed = ref(5); // frames per second
const phaseFrames = ref<string[]>([]);
const hasPhases = ref(false);
const totalPhases = ref(10);

const currentPhase = computed({
  get: () => props.currentPhaseIndex,
  set: (val) => emit("update:currentPhaseIndex", val),
});

const trackPercent = computed(() =>
  totalPhases.value > 1
    ? (currentPhase.value / (totalPhases.value - 1)) * 100
    : 0
);

const speedOptions = [
  { label: "1 FPS", value: 1 },
  { label: "3 FPS", value: 3 },
  { label: "5 FPS", value: 5 },
  { label: "10 FPS", value: 10 },
  { label: "15 FPS", value: 15 },
];

let timerId: ReturnType<typeof setInterval> | null = null;

function togglePlay() {
  playing.value = !playing.value;
}

function startPlayback() {
  stopPlayback();
  timerId = setInterval(() => {
    if (currentPhase.value >= totalPhases.value - 1) {
      if (loop.value) {
        currentPhase.value = 0;
      } else {
        playing.value = false;
        return;
      }
    } else {
      currentPhase.value++;
    }
  }, 1000 / speed.value);
}

function stopPlayback() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
}

function prevPhase() {
  if (currentPhase.value > 0) currentPhase.value--;
}

function nextPhase() {
  if (currentPhase.value < totalPhases.value - 1) currentPhase.value++;
}

function onTrackClick(e: MouseEvent) {
  const track = e.currentTarget as HTMLElement;
  const rect = track.getBoundingClientRect();
  const ratio = (e.clientX - rect.left) / rect.width;
  currentPhase.value = Math.round(ratio * (totalPhases.value - 1));
}

watch(playing, (val) => {
  if (val) startPlayback();
  else stopPlayback();
});

watch(speed, () => {
  if (playing.value) startPlayback();
});

function updatePhaseData(phases: any[]) {
  totalPhases.value = phases.length || 10;
  hasPhases.value = phases.length > 0;
}

watch(() => props.phases, updatePhaseData, { immediate: true });

onBeforeUnmount(stopPlayback);
</script>

<style scoped>
.cine-player {
  background: #0F172A;
  border-radius: 8px;
  overflow: hidden;
  user-select: none;
}

.cine-controls {
  padding: 10px 16px;
  background: #1E293B;
  border-bottom: 1px solid #334155;
}

.phase-display {
  display: flex;
  align-items: baseline;
  gap: 2px;
  min-width: 72px;
}

.phase-current {
  font-size: 14px;
  font-weight: 600;
  color: #E2E8F0;
  font-variant-numeric: tabular-nums;
}

.phase-sep {
  font-size: 12px;
  color: #64748B;
  margin: 0 2px;
}

.phase-total {
  font-size: 12px;
  color: #64748B;
  font-variant-numeric: tabular-nums;
}

.cine-track {
  flex: 1;
  height: 6px;
  background: #334155;
  border-radius: 3px;
  position: relative;
  cursor: pointer;
  min-width: 80px;
}

.cine-track-fill {
  height: 100%;
  background: linear-gradient(90deg, #1E88E5, #42A5F5);
  border-radius: 3px;
  transition: width 0.1s linear;
}

.cine-tick {
  position: absolute;
  top: -3px;
  width: 4px;
  height: 12px;
  background: #475569;
  border-radius: 1px;
  transform: translateX(-50%);
  transition: background 0.15s;
}
.cine-tick.active {
  background: #42A5F5;
  box-shadow: 0 0 4px rgba(66, 165, 245, 0.5);
}

.cine-viewport {
  position: relative;
  min-height: 200px;
  max-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  overflow: hidden;
}

.cine-placeholder {
  text-align: center;
  color: #64748B;
}
.cine-placeholder p {
  margin-top: 12px;
  font-size: 13px;
}
.hint {
  font-size: 11px !important;
  color: #475569 !important;
}

.cine-frames {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cine-frame {
  position: absolute;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: opacity 0.08s ease;
}

.cine-overlay {
  position: absolute;
  bottom: 8px;
  right: 12px;
}

.cine-overlay-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(0, 0, 0, 0.5);
  padding: 3px 8px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}
</style>