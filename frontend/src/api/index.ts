import axios from "axios";
import { clientApiBaseUrl, getClientToken, setClientToken } from "./server";
import { getInferenceTimeoutMs } from "@/stores/preferences";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 60000,
});

api.interceptors.request.use(async (config) => {
  config.baseURL = await clientApiBaseUrl();
  if (/\/(segmentation\/run|trajectory\/predict|igtv\/reconstruct)(?:\?|$)/.test(config.url || "")) {
    config.timeout = getInferenceTimeoutMs();
  }
  const token = getClientToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      setClientToken("");
      const currentPath = window.location.hash.replace("#", "") || "/dashboard";
      window.location.hash = `#/login?redirect=${encodeURIComponent(currentPath)}`;
    }
    return Promise.reject(err);
  }
);

export default api;
