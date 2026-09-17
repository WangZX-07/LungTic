import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_ADMIN_API_BASE_URL || "/api",
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem("lungtic_admin_token");
  if (token) config.headers.Authorization = "Bearer " + token;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem("lungtic_admin_token");
      if (!window.location.hash.startsWith("#/login")) window.location.hash = "#/login";
    }
    return Promise.reject(error);
  },
);

export default api;
