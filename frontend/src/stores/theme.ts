import { defineStore } from "pinia";
import { ref, watch } from "vue";

export type Theme = "light" | "dark";

export const useThemeStore = defineStore("theme", () => {
  const saved = (localStorage.getItem("lungtic_theme") as Theme) || "light";
  const theme = ref<Theme>(saved);

  function applyTheme(t: Theme) {
    document.documentElement.setAttribute("data-theme", t);
  }

  function toggle() {
    theme.value = theme.value === "light" ? "dark" : "light";
  }

  function setTheme(t: Theme) {
    theme.value = t;
  }

  watch(theme, (t) => {
    localStorage.setItem("lungtic_theme", t);
    applyTheme(t);
  }, { immediate: true });

  return { theme, toggle, setTheme };
});