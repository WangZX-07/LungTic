<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
<script setup lang="ts">
import { computed } from "vue";
import { darkTheme, NConfigProvider, NMessageProvider, NDialogProvider } from "naive-ui";
import type { GlobalThemeOverrides } from "naive-ui";
import { useThemeStore } from "@/stores/theme";
import { usePreferencesStore } from "@/stores/preferences";

const themeStore = useThemeStore();
usePreferencesStore();
const naiveTheme = computed(() => themeStore.theme === "dark" ? darkTheme : null);

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#1E88E5",
    primaryColorHover: "#42A5F5",
    primaryColorPressed: "#1565C0",
    primaryColorSuppl: "#1E88E5",
  },
};
</script>
