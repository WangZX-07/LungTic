const { app, BrowserWindow, net, protocol, session } = require("electron");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

protocol.registerSchemesAsPrivileged([{
  scheme: "app",
  privileges: { standard: true, secure: true, supportFetchAPI: true },
}]);

const appOrigin = "app://lungtic";
let mainWindow;

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
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' https: http://localhost:* http://127.0.0.1:* wss:; " +
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
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
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
    if (app.isPackaged) registerAssets();
    createWindow();
  });
}
app.on("window-all-closed", () => app.quit());
