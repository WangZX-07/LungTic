const { createHash, timingSafeEqual, X509Certificate } = require("node:crypto");

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

module.exports = { normalizeConnection, publicKeyPin, isTrustedServer };
