const key = "lungtic_server_origin";

export const isPackagedClinicalClient =
  window.location.protocol === "app:" && import.meta.env.VITE_STANDALONE_VIEWER !== "true";

function normalizeServerOrigin(value: string): string {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("请输入完整的服务端地址，例如 https://clinical.example.org");
  }
  const loopback = (url.hostname === "127.0.0.1" || url.hostname === "localhost") && url.protocol === "http:";
  if ((url.protocol !== "https:" && !loopback) || url.username || url.password
    || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("服务端须使用 HTTPS；本机开发可使用 http://localhost。地址不要包含路径或账号密码。");
  }
  return url.origin;
}

export function getServerOrigin(): string {
  const stored = localStorage.getItem(key);
  if (!stored) return "";
  try { return normalizeServerOrigin(stored); }
  catch { localStorage.removeItem(key); return ""; }
}

export function saveServerOrigin(value: string): string {
  const origin = normalizeServerOrigin(value);
  localStorage.setItem(key, origin);
  return origin;
}

export function clientApiBaseUrl(): string {
  if (isPackagedClinicalClient) {
    const origin = getServerOrigin();
    if (!origin) throw new Error("请先设置服务端地址");
    return origin + "/api";
  }
  return import.meta.env.VITE_API_BASE_URL || "/api";
}
