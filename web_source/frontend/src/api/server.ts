export const isPackagedClinicalClient =
  window.location.protocol === "app:" && import.meta.env.VITE_STANDALONE_VIEWER !== "true";

let packagedToken = "";
if (isPackagedClinicalClient) {
  // Remove plaintext settings left by older builds.
  localStorage.removeItem("lungtic_server_origin");
  localStorage.removeItem("lungtic_token");
}

export function getClientToken(): string {
  return isPackagedClinicalClient ? packagedToken : localStorage.getItem("lungtic_token") || "";
}

export function setClientToken(token: string): void {
  if (isPackagedClinicalClient) packagedToken = token;
  else if (token) localStorage.setItem("lungtic_token", token);
  else localStorage.removeItem("lungtic_token");
}

export async function getServerConnection(): Promise<LungTicConnection | null> {
  if (!isPackagedClinicalClient) return null;
  if (!window.lungticConnection) throw new Error("客户端安全连接模块不可用");
  return window.lungticConnection.load();
}

export async function saveServerConnection(origin: string, pin: string): Promise<LungTicConnection> {
  if (!isPackagedClinicalClient || !window.lungticConnection) {
    throw new Error("仅安装版客户端可保存医院连接");
  }
  const connection = await window.lungticConnection.save({ origin, pin });
  setClientToken("");
  return connection;
}

export async function clientApiBaseUrl(): Promise<string> {
  if (isPackagedClinicalClient) {
    const connection = await getServerConnection();
    if (!connection) throw new Error("请先设置医院服务端地址和公钥指纹");
    return connection.origin + "/api";
  }
  return import.meta.env.VITE_API_BASE_URL || "/api";
}
