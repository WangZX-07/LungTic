import { defineStore } from "pinia";
import { ref } from "vue";
import api from "./api";

export const useAdminStore = defineStore("admin", () => {
  const token = ref(sessionStorage.getItem("lungtic_admin_token") || "");
  const username = ref("");

  async function login(name: string, password: string, captchaToken: string, captchaCode: string) {
    const { data } = await api.post("/auth/login", {
      username: name, password, role: "admin",
      captcha_token: captchaToken, captcha_code: captchaCode,
    });
    if (data.role !== "admin") throw new Error("仅管理员账号可登录此后台");
    token.value = data.access_token;
    username.value = data.username;
    sessionStorage.setItem("lungtic_admin_token", token.value);
  }

  async function verify() {
    if (!token.value) return false;
    try {
      const { data } = await api.get("/auth/me");
      if (data.role !== "admin") throw new Error("管理员权限已失效");
      username.value = data.username;
      return true;
    } catch {
      logout();
      return false;
    }
  }

  function logout() {
    token.value = "";
    username.value = "";
    sessionStorage.removeItem("lungtic_admin_token");
  }

  return { token, username, login, verify, logout };
});
