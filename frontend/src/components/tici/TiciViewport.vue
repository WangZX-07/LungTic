<template>
  <figure
    class="tici-viewport"
    :aria-busy="loading"
    aria-label="TICI 医学影像视口"
  >
    <div v-if="imageBase64" class="image-stage" :style="stageStyle">
      <img
        class="image-layer"
        :src="`data:image/png;base64,${imageBase64}`"
        alt="当前 TICI 切片"
        draggable="false"
      />
      <img
        v-if="maskBase64 && showMask"
        class="mask-layer"
        :src="`data:image/png;base64,${maskBase64}`"
        alt="当前切片分割掩膜"
        draggable="false"
        :style="{ opacity: maskOpacity }"
      />
    </div>

    <div v-else-if="!loading" class="viewport-empty">
      <n-icon :size="44"><ScanOutline /></n-icon>
      <span>选择一个时相和切片</span>
    </div>

    <div v-if="loading" class="loading-state" role="status" aria-live="polite">
      <n-spin size="medium" />
      <span>读取切片…</span>
    </div>
  </figure>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NIcon, NSpin } from "naive-ui";
import { ScanOutline } from "@vicons/ionicons5";

const props = defineProps<{
  imageBase64: string;
  maskBase64: string;
  showMask: boolean;
  maskOpacity: number;
  zoom: number;
  loading: boolean;
}>();

const stageStyle = computed(() => ({
  transform: `scale(${props.zoom})`,
}));
</script>

<style scoped>
.tici-viewport {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 420px;
  height: 100%;
  margin: 0;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #05080d;
  color: #8ca0b8;
}

.image-stage {
  position: relative;
  display: grid;
  width: calc(100% - 64px);
  height: calc(100% - 64px);
  place-items: center;
  transform-origin: center;
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.image-layer,
.mask-layer {
  grid-area: 1 / 1;
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
}

.mask-layer {
  mix-blend-mode: screen;
  transition: opacity 160ms ease-out;
}

.viewport-empty,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.loading-state {
  position: absolute;
  inset: 0;
  justify-content: center;
  background: rgb(5 8 13 / 72%);
}

@media (prefers-reduced-motion: reduce) {
  .image-stage,
  .mask-layer {
    transition: none;
  }
}
</style>
