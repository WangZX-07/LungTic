<template>
  <n-badge :value="unreadCount" :max="99" :show-zero="false">
    <n-button text circle aria-label="打开消息中心" title="消息中心" @click="openInbox">
      <template #icon><n-icon size="20"><NotificationsOutline /></n-icon></template>
    </n-button>
  </n-badge>

  <n-drawer v-model:show="show" :width="420" placement="right">
    <n-drawer-content title="消息中心" closable>
      <div class="inbox-actions">
        <n-button text size="small" :disabled="unreadCount === 0" @click="markAllRead">
          全部已读
        </n-button>
      </div>

      <n-spin :show="loading">
        <n-empty v-if="!loading && notifications.length === 0" description="暂无系统消息" />
        <div v-else class="notification-list">
          <button
            v-for="item in notifications"
            :key="item.id"
            type="button"
            class="notification-item"
            :class="{ unread: !item.is_read }"
            @click="openNotification(item)"
          >
            <span class="notification-dot" aria-hidden="true" />
            <span class="notification-content">
              <strong>{{ item.title }}</strong>
              <span>{{ item.message }}</span>
              <time>{{ formatTime(item.created_at) }}</time>
            </span>
          </button>
        </div>
      </n-spin>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NBadge, NButton, NDrawer, NDrawerContent, NEmpty, NIcon, NSpin, useMessage,
} from "naive-ui";
import { NotificationsOutline } from "@vicons/ionicons5";
import api from "@/api";

interface InboxNotification {
  id: number;
  kind: string;
  title: string;
  message: string;
  target_path?: string | null;
  is_read: boolean;
  created_at: string;
}

const router = useRouter();
const message = useMessage();
const show = ref(false);
const loading = ref(false);
const unreadCount = ref(0);
const notifications = ref<InboxNotification[]>([]);
let refreshTimer: number | null = null;

async function refreshUnreadCount() {
  try {
    const response = await api.get("/notifications/unread-count");
    unreadCount.value = Number(response.data?.count || 0);
  } catch {
    // A badge refresh must not interrupt the clinical workspace.
  }
}

async function loadNotifications() {
  loading.value = true;
  try {
    const response = await api.get("/notifications", { params: { limit: 50 } });
    notifications.value = response.data || [];
    unreadCount.value = notifications.value.filter((item) => !item.is_read).length;
  } catch {
    message.error("消息加载失败");
  } finally {
    loading.value = false;
  }
}

function openInbox() {
  show.value = true;
  void loadNotifications();
}

async function openNotification(item: InboxNotification) {
  if (!item.is_read) {
    try {
      await api.put(`/notifications/${item.id}/read`);
      item.is_read = true;
      unreadCount.value = Math.max(0, unreadCount.value - 1);
    } catch {
      message.error("消息状态更新失败");
      return;
    }
  }
  if (item.target_path?.startsWith("/dashboard/")) {
    show.value = false;
    await router.push(item.target_path);
  }
}

async function markAllRead() {
  try {
    await api.put("/notifications/read-all");
    notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }));
    unreadCount.value = 0;
  } catch {
    message.error("全部已读操作失败");
  }
}

function formatTime(value: string): string {
  if (!value) return "";
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

onMounted(() => {
  void refreshUnreadCount();
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === "visible") void refreshUnreadCount();
  }, 60_000);
});

onBeforeUnmount(() => {
  if (refreshTimer !== null) window.clearInterval(refreshTimer);
});
</script>

<style scoped>
.notification-list { display: flex; flex-direction: column; gap: 8px; }
.inbox-actions { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.notification-item {
  width: 100%; display: flex; gap: 10px; padding: 12px; text-align: left;
  color: var(--color-text); background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: 8px; cursor: pointer;
}
.notification-item:hover { border-color: var(--color-primary); }
.notification-item.unread { background: color-mix(in srgb, var(--color-primary) 8%, var(--color-surface)); }
.notification-dot { width: 8px; height: 8px; margin-top: 5px; border-radius: 50%; background: transparent; flex: 0 0 auto; }
.notification-item.unread .notification-dot { background: var(--color-primary); }
.notification-content { display: flex; min-width: 0; flex-direction: column; gap: 5px; }
.notification-content strong { font-size: 14px; }
.notification-content span { color: var(--color-text-secondary); font-size: 13px; line-height: 1.5; }
.notification-content time { color: var(--color-text-muted); font-size: 12px; }
</style>
