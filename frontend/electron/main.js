const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

let mainWindow;
let backendProcess;
let isQuitting = false;
const backendPort = 18765;

function waitForBackend(timeoutMs = 20000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const retry = () => {
      if (Date.now() - startedAt >= timeoutMs) {
        reject(new Error("本地查看服务启动超时"));
        return;
      }
      setTimeout(check, 250);
    };
    const check = () => {
      const request = http.get(
        `http://127.0.0.1:${backendPort}/api/health`,
        (response) => {
          response.resume();
          if (response.statusCode === 200) resolve();
          else retry();
        },
      );
      request.on("error", retry);
      request.setTimeout(1000, () => request.destroy());
    };
    check();
  });
}

async function startBackend() {
  if (!app.isPackaged) return;

  const executable = path.join(
    process.resourcesPath,
    "backend",
    "lungtic-viewer-backend.exe",
  );
  if (!fs.existsSync(executable)) {
    throw new Error(`未找到内置查看服务：${executable}`);
  }

  const dataDir = path.join(app.getPath("userData"), "backend-data");
  fs.mkdirSync(dataDir, { recursive: true });
  const databasePath = path.join(dataDir, "lungtic-viewer.db").replace(/\\/g, "/");

  backendProcess = spawn(executable, [], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      LUNGTIC_DATA_DIR: dataDir,
      LUNGTIC_DB_URL: `sqlite:///${databasePath}`,
      LUNGTIC_PORT: String(backendPort),
      LUNGTIC_BOOTSTRAP_USERNAME: "admin",
      LUNGTIC_BOOTSTRAP_PASSWORD: "admin123",
    },
  });

  backendProcess.once("exit", (code) => {
    backendProcess = undefined;
    if (!isQuitting && code !== 0) {
      dialog.showErrorBox("LungTic 查看服务已停止", "请重新启动应用。");
    }
  });

  await waitForBackend();
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) backendProcess.kill();
  backendProcess = undefined;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 960,
    minHeight: 680,
    title: "LungTic TICI Viewer",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!app.isPackaged) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || "http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    try {
      await startBackend();
      createWindow();
    } catch (error) {
      dialog.showErrorBox("LungTic 启动失败", error.message || String(error));
      app.quit();
    }
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});
app.on("window-all-closed", () => app.quit());
