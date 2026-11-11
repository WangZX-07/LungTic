import axios from "axios";

function cookie(name: string) {
  const prefix = encodeURIComponent(name) + "=";
  const value = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : "";
}

const api = axios.create({
  baseURL: import.meta.env.VITE_PROJECT_API_BASE_URL || "/api/project",
  timeout: 30000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const csrf = cookie("lungtic_project_csrf");
  if (csrf && config.method && !["get", "head", "options"].includes(config.method.toLowerCase())) {
    config.headers["X-Project-CSRF"] = csrf;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.hash.startsWith("#/login")) {
      window.location.hash = "#/login";
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error: any, fallback = "请求失败") {
  return error?.response?.data?.detail || error?.message || fallback;
}

export default api;
