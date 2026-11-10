<template>
  <div class="filmstrip" ref="stripRef">
    <div
      v-for="(item, idx) in thumbnails"
      :key="idx"
      class="thumbnail"
      :class="{ active: idx + 1 === currentSlice, loaded: item.loaded }"
      @click="$emit('select', idx + 1)"
      :title="'层 ' + (idx + 1) + ' · Z: ' + (item.z_pos?.toFixed(1) || '-') + ' mm'"
    >
      <div v-if="!item.loaded" class="thumb-placeholder">
        <span>{{ idx + 1 }}</span>
      </div>
      <img
        v-else
        :src="'data:image/png;base64,' + item.base64"
        class="thumb-img"
      />
      <span class="thumb-label">{{ idx + 1 }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from "vue";
import api from "@/api";

const props = defineProps<{
  seriesId: number | null;
  currentSlice: number;
  totalSlices: number;
}>();

defineEmits<{ select: [index: number] }>();

interface Thumbnail {
  base64: string;
  z_pos: number | null;
  loaded: boolean;
}

const thumbnails = ref<Thumbnail[]>([]);
const stripRef = ref<HTMLDivElement>();

async function loadThumbnails() {
  if (!props.seriesId) return;

  thumbnails.value = Array.from({ length: props.totalSlices }, () => ({
    base64: "",
    z_pos: null,
    loaded: false,
  }));

  try {
    const res = await api.get(`/dicom/series/${props.seriesId}/slices`);
    const slices = res.data || [];

    for (let i = 0; i < slices.length; i += 4) {
      const batch = slices.slice(i, i + 4);
      await Promise.all(
        batch.map(async (slc: any, bi: number) => {
          const idx = i + bi;
          try {
            const imgRes = await api.get(`/dicom/slice/${slc.id}/image`);
            thumbnails.value[idx] = {
              base64: imgRes.data?.image_base64 || imgRes.data,
              z_pos: slc.z_position || null,
              loaded: true,
            };
          } catch {
            thumbnails.value[idx] = { base64: "", z_pos: null, loaded: false };
          }
        })
      );
    }
  } catch {}
}

watch(
  () => props.currentSlice,
  () => {
    nextTick(() => {
      const active = stripRef.value?.querySelector(".thumbnail.active") as HTMLElement;
      active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    });
  }
);

watch(
  () => props.seriesId,
  (id) => {
    if (id) loadThumbnails();
  }
);

onMounted(() => {
  if (props.seriesId) loadThumbnails();
});
</script>

<style scoped>
.filmstrip {
  display: flex;
  gap: 4px;
  padding: 8px 4px;
  overflow-x: auto;
  overflow-y: hidden;
  background: #0F172A;
  border-radius: 8px;
  scroll-behavior: smooth;
  min-height: 80px;
  align-items: center;
}

.filmstrip::-webkit-scrollbar { height: 4px; }
.filmstrip::-webkit-scrollbar-track { background: #1E293B; }
.filmstrip::-webkit-scrollbar-thumb { background: #475569; border-radius: 2px; }

.thumbnail {
  position: relative;
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border: 2px solid transparent;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, opacity 0.15s;
  opacity: 0.6;
  background: #1E293B;
}

.thumbnail:hover { opacity: 0.85; border-color: #475569; }

.thumbnail.active {
  opacity: 1;
  border-color: #1E88E5;
  box-shadow: 0 0 8px rgba(30, 136, 229, 0.4);
}

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
}

.thumb-img { width: 100%; height: 100%; object-fit: cover; }

.thumb-label {
  position: absolute;
  bottom: 2px;
  right: 3px;
  font-size: 9px;
  color: #FFFFFF;
  background: rgba(0, 0, 0, 0.6);
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>