import { defineStore } from "pinia";
import { ref, watch } from "vue";

export type WindowPreset = "lung" | "mediastinum" | "bone" | "default";

export interface ClientPreferences {
  sidebarCollapsed: boolean;
  animationsEnabled: boolean;
  inferenceTimeoutSeconds: number;
  defaultPreset: WindowPreset;
  maskOpacityPercent: number;
}

export const SETTINGS_STORAGE_KEY = "lungtic_settings";

export const DEFAULT_CLIENT_PREFERENCES: ClientPreferences = {
  sidebarCollapsed: false,
  animationsEnabled: true,
  inferenceTimeoutSeconds: 120,
  defaultPreset: "lung",
  maskOpacityPercent: 50,
};

const WINDOW_PRESETS: Record<WindowPreset, { width: number; center: number }> = {
  lung: { width: 1500, center: -600 },
  mediastinum: { width: 350, center: 50 },
  bone: { width: 2000, center: 350 },
  default: { width: 400, center: 40 },
};

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

export function readClientPreferences(): ClientPreferences {
  try {
    const stored = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) || "{}");
    const preset = stored.defaultPreset in WINDOW_PRESETS
      ? stored.defaultPreset as WindowPreset
      : DEFAULT_CLIENT_PREFERENCES.defaultPreset;
    return {
      sidebarCollapsed: typeof stored.sidebarCollapsed === "boolean"
        ? stored.sidebarCollapsed
        : DEFAULT_CLIENT_PREFERENCES.sidebarCollapsed,
      animationsEnabled: typeof stored.animationsEnabled === "boolean"
        ? stored.animationsEnabled
        : DEFAULT_CLIENT_PREFERENCES.animationsEnabled,
      inferenceTimeoutSeconds: clampNumber(
        stored.inferenceTimeoutSeconds,
        DEFAULT_CLIENT_PREFERENCES.inferenceTimeoutSeconds,
        30,
        600,
      ),
      defaultPreset: preset,
      maskOpacityPercent: clampNumber(
        stored.maskOpacityPercent,
        DEFAULT_CLIENT_PREFERENCES.maskOpacityPercent,
        10,
        100,
      ),
    };
  } catch {
    return { ...DEFAULT_CLIENT_PREFERENCES };
  }
}

export function getInferenceTimeoutMs(): number {
  return readClientPreferences().inferenceTimeoutSeconds * 1000;
}

export function getWindowPreset(preset?: WindowPreset): { width: number; center: number } {
  return WINDOW_PRESETS[preset || readClientPreferences().defaultPreset];
}

function applyAnimations(enabled: boolean) {
  document.documentElement.dataset.animations = enabled ? "on" : "off";
}

export const usePreferencesStore = defineStore("preferences", () => {
  const initial = readClientPreferences();
  const sidebarCollapsed = ref(initial.sidebarCollapsed);
  const animationsEnabled = ref(initial.animationsEnabled);
  const inferenceTimeoutSeconds = ref(initial.inferenceTimeoutSeconds);
  const defaultPreset = ref<WindowPreset>(initial.defaultPreset);
  const maskOpacityPercent = ref(initial.maskOpacityPercent);

  watch(
    [sidebarCollapsed, animationsEnabled, inferenceTimeoutSeconds, defaultPreset, maskOpacityPercent],
    () => {
      const preferences: ClientPreferences = {
        sidebarCollapsed: sidebarCollapsed.value,
        animationsEnabled: animationsEnabled.value,
        inferenceTimeoutSeconds: clampNumber(inferenceTimeoutSeconds.value, 120, 30, 600),
        defaultPreset: defaultPreset.value,
        maskOpacityPercent: clampNumber(maskOpacityPercent.value, 50, 10, 100),
      };
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(preferences));
      applyAnimations(preferences.animationsEnabled);
    },
    { immediate: true },
  );

  function reset() {
    sidebarCollapsed.value = DEFAULT_CLIENT_PREFERENCES.sidebarCollapsed;
    animationsEnabled.value = DEFAULT_CLIENT_PREFERENCES.animationsEnabled;
    inferenceTimeoutSeconds.value = DEFAULT_CLIENT_PREFERENCES.inferenceTimeoutSeconds;
    defaultPreset.value = DEFAULT_CLIENT_PREFERENCES.defaultPreset;
    maskOpacityPercent.value = DEFAULT_CLIENT_PREFERENCES.maskOpacityPercent;
  }

  return {
    sidebarCollapsed,
    animationsEnabled,
    inferenceTimeoutSeconds,
    defaultPreset,
    maskOpacityPercent,
    reset,
  };
});
