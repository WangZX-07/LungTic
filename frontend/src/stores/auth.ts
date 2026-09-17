import { defineStore } from "pinia";
import { ref, computed } from "vue";
import api from "@/api";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<{ username: string; role: string; patient_code?: string; email?: string; phone?: string } | null>(null);
  const token = ref(localStorage.getItem("lungtic_token") || "");

  const isAdmin = computed(() => user.value?.role === "admin");
  const isDoctor = computed(() => user.value?.role === "doctor" || user.value?.role === "admin");
  const isPatient = computed(() => user.value?.role === "patient");

  async function login(username: string, password: string, role: string, captchaToken?: string, captchaCode?: string) {
    const res = await api.post("/auth/login", {
      username,
      password,
      role,
      captcha_token: captchaToken || "",
      captcha_code: captchaCode || 0,
    });
    if (res.data.role !== role || (role === "admin" && import.meta.env.VITE_STANDALONE_VIEWER !== "true")) {
      throw new Error("此客户端不允许该角色登录");
    }
    token.value = res.data.access_token;
    user.value = { username: res.data.username, role: res.data.role };
    localStorage.setItem("lungtic_token", token.value);
    return res.data;
  }

  async function fetchMe() {
    const res = await api.get("/auth/me");
    if (res.data.role !== "doctor" && res.data.role !== "patient"
      && !(import.meta.env.VITE_STANDALONE_VIEWER === "true" && res.data.role === "admin")) {
      logout();
      throw new Error("此客户端不允许该角色登录");
    }
    user.value = {
      username: res.data.username,
      role: res.data.role,
      patient_code: res.data.patient_code,
    };
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("lungtic_token");
  }

  return { user, token, isAdmin, isDoctor, isPatient, login, fetchMe, logout };
});