<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    preset="card"
    title="键盘快捷键"
    style="width: min(480px, calc(100vw - 24px)); max-height: calc(100dvh - 24px)"
    :mask-closable="true"
  >
    <n-space vertical :size="16">
      <div>
        <h4 class="section-title">影像浏览</h4>
        <div class="shortcut-list">
          <div class="shortcut-row">
            <kbd>←</kbd><kbd>→</kbd> / <kbd>↑</kbd><kbd>↓</kbd>
            <span class="desc">切换切片层数</span>
          </div>
          <div class="shortcut-row">
            <kbd>Page Up</kbd><kbd>Page Down</kbd>
            <span class="desc">切换时相</span>
          </div>
          <div class="shortcut-row">
            <span class="keys-group"><kbd>鼠标拖拽</kbd></span>
            <span class="desc">旋转 3D 视图</span>
          </div>
          <div class="shortcut-row">
            <span class="keys-group"><kbd>鼠标滚轮</kbd></span>
            <span class="desc">缩放 3D / CT 视图</span>
          </div>
        </div>
      </div>

      <div>
        <h4 class="section-title">通用操作</h4>
        <div class="shortcut-list">
          <div class="shortcut-row">
            <kbd>Enter</kbd>
            <span class="desc">登录确认</span>
          </div>
          <div class="shortcut-row">
            <kbd>Esc</kbd>
            <span class="desc">关闭弹窗 / 退出聚焦</span>
          </div>
          <div class="shortcut-row">
            <kbd>?</kbd>
            <span class="desc">显示此帮助面板</span>
          </div>
        </div>
      </div>

      <div>
        <h4 class="section-title">窗宽窗位预设</h4>
        <div class="shortcut-list">
          <div class="shortcut-row">
            <span class="preset-tag lung">肺窗</span>
            <span class="desc">WW 1500 / WL -600</span>
          </div>
          <div class="shortcut-row">
            <span class="preset-tag mediastinum">纵膈窗</span>
            <span class="desc">WW 350 / WL 50</span>
          </div>
          <div class="shortcut-row">
            <span class="preset-tag bone">骨窗</span>
            <span class="desc">WW 2000 / WL 350</span>
          </div>
        </div>
      </div>
    </n-space>
  </n-modal>
</template>

<script setup lang="ts">
import { NModal, NSpace } from "naive-ui";

defineProps<{ show: boolean }>();
defineEmits<{ "update:show": [value: boolean] }>();
</script>

<style scoped>
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  background: #F1F5F9;
  border: 1px solid #CBD5E1;
  border-radius: 4px;
  font-size: 11px;
  font-family: inherit;
  color: #334155;
  line-height: 1;
}

.keys-group {
  display: flex;
  gap: 4px;
}

.desc {
  color: #64748B;
  margin-left: 4px;
}

.preset-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  min-width: 48px;
  text-align: center;
}
.preset-tag.lung { background: #E3F2FD; color: #1565C0; }
.preset-tag.mediastinum { background: #E8F5E9; color: #2E7D32; }
.preset-tag.bone { background: #FFF3E0; color: #E65100; }
</style>
