import axios from "axios";
import { clientApiBaseUrl } from "./server";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  config.baseURL = clientApiBaseUrl();
  const token = localStorage.getItem("lungtic_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("lungtic_token");
      const currentPath = window.location.hash.replace("#", "") || "/dashboard";
      window.location.hash = `#/login?redirect=${encodeURIComponent(currentPath)}`;
    }
    return Promise.reject(err);
  }
);

export default api;
