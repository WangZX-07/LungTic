const { createHash, timingSafeEqual, X509Certificate } = require("node:crypto");

const DEFAULT_CONNECTION = Object.freeze({
  origin: "https://clinical.respulse.top",
  pin: "b6f5a401faf49c8b187e95f12ce6b3339fd80e9e5cd911140e92896a1d9d4085",
});
const LEGACY_DEFAULT_PINS = new Set([
  "a67a2f77197a453e13962cd577ed35ecee64cb87cbda48fa1c50cba539de5eee",
]);

function normalizeConnection(input) {
  if (!input || typeof input.origin !== "string" || typeof input.pin !== "string") {
    throw new Error("请输入医院服务端地址和公钥指纹");
  }
  let url;
  try { url = new URL(input.origin.trim()); }
  catch { throw new Error("请输入完整的 HTTPS 服务端地址"); }
  if (url.protocol !== "https:" || !url.hostname || url.username || url.password
      || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("安装版仅允许 HTTPS 根地址，不能包含路径或账号密码");
  }
  const pin = input.pin.replace(/[:\s]/g, "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(pin)) {
    throw new Error("公钥 SHA-256 指纹须为 64 位十六进制字符");
  }
  return { origin: url.origin, pin };
}

function bundledConnection() {
  return { ...DEFAULT_CONNECTION };
}

function normalizeStoredConnection(input) {
  const normalized = normalizeConnection(input);
  if (normalized.origin === DEFAULT_CONNECTION.origin
      && LEGACY_DEFAULT_PINS.has(normalized.pin)) {
    return bundledConnection();
  }
  return normalized;
}

function publicKeyPin(pem) {
  const certificate = new X509Certificate(pem);
  const publicKey = certificate.publicKey.export({ type: "spki", format: "der" });
  return createHash("sha256").update(publicKey).digest("hex");
}

function isTrustedServer(request, connection) {
  const verificationSucceeded = request.verificationResult === "OK"
    || request.verificationResult === "net::OK";
  if (!connection || !verificationSucceeded || request.errorCode !== 0) return false;
  if (request.hostname.toLowerCase() !== new URL(connection.origin).hostname) return false;
  try {
    const actual = Buffer.from(publicKeyPin(request.certificate.data), "hex");
    const expected = Buffer.from(connection.pin, "hex");
    return actual.length === expected.length && timingSafeEqual(actual, expected);
  } catch { return false; }
}

module.exports = {
  DEFAULT_CONNECTION,
  bundledConnection,
  normalizeConnection,
  normalizeStoredConnection,
  publicKeyPin,
  isTrustedServer,
};
