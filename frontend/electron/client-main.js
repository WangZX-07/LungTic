const { app, BrowserWindow, ipcMain, net, protocol, safeStorage, session } = require("electron");
const fs = require("node:fs");
const { normalizeConnection, isTrustedServer } = require("./connection");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

protocol.registerSchemesAsPrivileged([{
  scheme: "app",
  privileges: { standard: true, secure: true, supportFetchAPI: true },
}]);

const appOrigin = "app://lungtic";
let mainWindow;
let connection = null;

function connectionFile() {
  return path.join(app.getPath("userData"), "connection.bin");
}

function loadConnection() {
  const file = connectionFile();
  if (!fs.existsSync(file)) return null;
  if (!safeStorage.isEncryptionAvailable()) throw new Error("系统安全存储不可用");
  try {
    return normalizeConnection(JSON.parse(safeStorage.decryptString(fs.readFileSync(file))));
  } catch {
    throw new Error("医院连接配置无法解密，请重新配置客户端");
  }
}

function saveConnection(value) {
  if (!safeStorage.isEncryptionAvailable()) throw new Error("系统安全存储不可用");
  const normalized = normalizeConnection(value);
  const encrypted = safeStorage.encryptString(JSON.stringify(normalized));
  fs.mkdirSync(path.dirname(connectionFile()), { recursive: true });
  fs.writeFileSync(connectionFile(), encrypted, { mode: 0o600 });
  connection = normalized;
  return normalized;
}

function requireClientFrame(event) {
  if (!app.isPackaged || !event.senderFrame?.url?.startsWith(appOrigin + "/")) {
    throw new Error("Invalid client origin");
  }
}

function registerAssets() {
  const root = path.resolve(__dirname, "../dist");
  protocol.handle("app", async (request) => {
    const url = new URL(request.url);
    if (url.host !== "lungtic") return new Response("Not found", { status: 404 });
    let pathname;
    try { pathname = decodeURIComponent(url.pathname); }
    catch { return new Response("Invalid asset path", { status: 400 }); }
    const requested = pathname === "/" ? "/index.html" : pathname;
    const target = path.resolve(root, "." + requested);
    const relative = path.relative(root, target);
    if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
      return new Response("Invalid asset path", { status: 400 });
    }
    return net.fetch(pathToFileURL(target).toString());
  });
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    if (!details.url.startsWith(appOrigin + "/")) { callback({}); return; }
    callback({ responseHeaders: {
      ...details.responseHeaders,
      "Content-Security-Policy": [
        "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; " +
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' " + (connection?.origin || "") + "; " +
        "worker-src 'self' blob:; object-src 'none'; frame-src 'none'; base-uri 'self'",
      ],
    } });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 960, minHeight: 680,
    title: "LungTic 临床客户端",
    autoHideMenuBar: true,
    webPreferences: {
      preload: app.isPackaged ? path.join(__dirname, "client-preload.js") : undefined,
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const allowed = app.isPackaged ? url.startsWith(appOrigin + "/") : url.startsWith("http://localhost:5173/");
    if (!allowed) event.preventDefault();
  });
  if (app.isPackaged) mainWindow.loadURL(appOrigin + "/index.html");
  else mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || "http://localhost:5173/");
}

const lock = app.requestSingleInstanceLock();
if (!lock) app.quit();
else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
    if (app.isPackaged) {
      try { connection = loadConnection(); }
      catch { connection = null; }
      session.defaultSession.setCertificateVerifyProc((request, callback) => {
        callback(isTrustedServer(request, connection) ? 0 : -2);
      });
      ipcMain.handle("connection:load", (event) => {
        requireClientFrame(event);
        return connection;
      });
      ipcMain.handle("connection:save", async (event, value) => {
        requireClientFrame(event);
        const saved = saveConnection(value);
        await session.defaultSession.closeAllConnections();
        setTimeout(() => {
          if (mainWindow && !mainWindow.isDestroyed()) mainWindow.reload();
        }, 50);
        return saved;
      });
      registerAssets();
    }
    createWindow();
  });
}
app.on("window-all-closed", () => app.quit());
