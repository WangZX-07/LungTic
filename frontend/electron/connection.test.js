const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
  DEFAULT_CONNECTION, bundledConnection, normalizeConnection, normalizeStoredConnection,
  publicKeyPin, isTrustedServer,
} = require("./connection");

const pem = fs.readFileSync(path.join(__dirname, "test-fixtures/synthetic-server.crt"), "utf8");
const pin = publicKeyPin(pem);

test("accepts only an HTTPS origin and a SHA-256 pin", () => {
  assert.deepEqual(normalizeConnection({
    origin: "https://clinical.example.org",
    pin: pin.toUpperCase().match(/.{2}/g).join(":"),
  }), { origin: "https://clinical.example.org", pin });
  for (const origin of ["http://clinical.example.org", "https://user:pass@clinical.example.org",
    "https://clinical.example.org/api", "https://clinical.example.org/?q=1"]) {
    assert.throws(() => normalizeConnection({ origin, pin }));
  }
  assert.throws(() => normalizeConnection({ origin: "https://clinical.example.org", pin: "short" }));
});

test("requires system trust, matching host, and matching public key", () => {
  const request = { hostname: "clinical.example.org", certificate: { data: pem },
    verificationResult: "OK", errorCode: 0 };
  const connection = { origin: "https://clinical.example.org", pin };
  assert.equal(isTrustedServer(request, connection), true);
  assert.equal(isTrustedServer({ ...request, verificationResult: "net::OK" }, connection), true);
  assert.equal(isTrustedServer({ ...request, hostname: "other.example.org" }, connection), false);
  assert.equal(isTrustedServer({ ...request, verificationResult: "CERT_AUTHORITY_INVALID" }, connection), false);
  assert.equal(isTrustedServer(request, { ...connection, pin: "0".repeat(64) }), false);
  assert.equal(isTrustedServer({ ...request, certificate: { data: "invalid" } }, connection), false);
});

test("provides the bundled production connection and migrates the previous pin", () => {
  assert.deepEqual(bundledConnection(), DEFAULT_CONNECTION);
  assert.notEqual(bundledConnection(), DEFAULT_CONNECTION);
  assert.deepEqual(normalizeStoredConnection({
    origin: "https://clinical.respulse.top",
    pin: "a67a2f77197a453e13962cd577ed35ecee64cb87cbda48fa1c50cba539de5eee",
  }), DEFAULT_CONNECTION);
  const custom = { origin: "https://clinical.example.org", pin };
  assert.deepEqual(normalizeStoredConnection(custom), custom);
});
