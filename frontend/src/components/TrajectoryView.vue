<template>
  <n-card size="small" title="肿瘤运动轨迹" class="trajectory-card">
    <template #header-extra>
      <n-space>
        <n-switch v-model:value="showPredicted">
          <template #checked>显示预测</template>
          <template #unchecked>仅真实</template>
        </n-switch>
        <n-button size="small" type="primary" @click="predict" :loading="predicting">
          预测轨迹
        </n-button>
      </n-space>
    </template>

    <n-spin :show="loading">
      <div class="chart-area">
        <div v-if="!hasData" class="chart-placeholder">
          <n-icon size="64" color="#CBD5E1"><AnalyticsOutline /></n-icon>
          <p>运动轨迹图表</p>
          <p class="hint">执行分割和轨迹预测后将在此显示 X/Y/Z 方向位移曲线</p>
        </div>
        <v-chart
          v-else
          class="chart-instance"
          :option="chartOption"
          autoresize
        />
      </div>
    </n-spin>
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { NCard, NSpace, NSwitch, NButton, NIcon, NSpin, useMessage } from "naive-ui";
import { AnalyticsOutline } from "@vicons/ionicons5";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from "echarts/components";
import type { ComposeOption } from "echarts/core";
import type { LineSeriesOption } from "echarts/charts";
import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
} from "echarts/components";
import api from "@/api";

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

type ECOption = ComposeOption<
  | LineSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
>;

const props = defineProps<{ studyId: number }>();
const message = useMessage();

const loading = ref(false);
const showPredicted = ref(true);
const predicting = ref(false);
const hasData = ref(false);
const trajectoryData = ref<any>(null);

interface TrajectoryPoint {
  phase: number;
  centroid_x: number | null;
  centroid_y: number | null;
  centroid_z: number | null;
  is_predicted: boolean;
}

const chartOption = computed<ECOption>(() => {
  if (!trajectoryData.value) return {};

  const points: TrajectoryPoint[] = trajectoryData.value;
  const observed = points.filter((p) => !p.is_predicted);
  const predicted = points.filter((p) => p.is_predicted);

  const series: LineSeriesOption[] = [
    {
      name: "X (观测)", type: "line",
      data: observed.map((p) => p.centroid_x),
      smooth: true, symbol: "circle", symbolSize: 6,
      lineStyle: { width: 2 }, itemStyle: { color: "#EF4444" },
    },
    {
      name: "Y (观测)", type: "line",
      data: observed.map((p) => p.centroid_y),
      smooth: true, symbol: "circle", symbolSize: 6,
      lineStyle: { width: 2 }, itemStyle: { color: "#22C55E" },
    },
    {
      name: "Z (观测)", type: "line",
      data: observed.map((p) => p.centroid_z),
      smooth: true, symbol: "circle", symbolSize: 6,
      lineStyle: { width: 2 }, itemStyle: { color: "#1E88E5" },
    },
  ];

  if (showPredicted.value && predicted.length > 0) {
    const last = observed[observed.length - 1];
    series.push(
      {
        name: "X (预测)", type: "line",
        data: last ? [last.centroid_x, ...predicted.map((p) => p.centroid_x)] : predicted.map((p) => p.centroid_x),
        smooth: true, symbol: "diamond", symbolSize: 8,
        lineStyle: { width: 2, type: "dashed" }, itemStyle: { color: "#EF4444" },
      },
      {
        name: "Y (预测)", type: "line",
        data: last ? [last.centroid_y, ...predicted.map((p) => p.centroid_y)] : predicted.map((p) => p.centroid_y),
        smooth: true, symbol: "diamond", symbolSize: 8,
        lineStyle: { width: 2, type: "dashed" }, itemStyle: { color: "#22C55E" },
      },
      {
        name: "Z (预测)", type: "line",
        data: last ? [last.centroid_z, ...predicted.map((p) => p.centroid_z)] : predicted.map((p) => p.centroid_z),
        smooth: true, symbol: "diamond", symbolSize: 8,
        lineStyle: { width: 2, type: "dashed" }, itemStyle: { color: "#1E88E5" },
      }
    );
  }

  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        let html = `<b>时相 ${params[0]?.axisValue ?? "?"}</b><br/>`;
        params.forEach((item: any) => {
          html += `${item.marker} ${item.seriesName}: ${item.value?.toFixed(2) ?? "-"} mm<br/>`;
        });
        return html;
      },
    },
    legend: { bottom: 0, textStyle: { fontSize: 11 }, itemWidth: 16, itemHeight: 2 },
    grid: { left: 48, right: 24, top: 24, bottom: 48 },
    xAxis: {
      type: "category",
      data: points.map((p) => `P${p.phase}`),
      name: "时相", nameLocation: "center", nameGap: 32,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: "value", name: "位移 (mm)",
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { color: "#E2E8F0", type: "dashed" } },
    },
    series,
  };
});

async function loadTrajectory() {
  loading.value = true;
  try {
    const res = await api.get(`/trajectory/${props.studyId}`);
    const data = res.data?.trajectories || res.data?.points;
    if (data?.length > 0) {
      trajectoryData.value = data;
      hasData.value = true;
    }
  } catch { hasData.value = false; }
  finally { loading.value = false; }
}

async function predict() {
  predicting.value = true;
  try {
    const res = await api.post("/trajectory/predict", { study_id: props.studyId });
    message.success(res.data.message || "预测完成");
    let retries = 0;
    while (retries < 15) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const result = await api.get(`/trajectory/${props.studyId}`);
        const data = result.data?.trajectories || result.data?.points;
        if (data?.length > 0) {
          trajectoryData.value = data;
          hasData.value = true;
          break;
        }
      } catch {}
      retries++;
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || "预测失败");
  } finally { predicting.value = false; }
}

onMounted(loadTrajectory);
</script>

<style scoped>
.trajectory-card { height: 100%; }
.chart-area {
  min-height: 400px;
  background: #FFFFFF;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #E2E8F0;
}
.chart-placeholder { text-align: center; color: #94A3B8; }
.chart-placeholder p { margin-top: 16px; }
.hint { font-size: 12px; color: #64748B; margin-top: 8px !important; }
.chart-instance { width: 100%; height: 420px; }
</style>