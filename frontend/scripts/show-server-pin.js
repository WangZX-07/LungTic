const fs = require("node:fs");
const { publicKeyPin } = require("../electron/connection");

const certificatePath = process.argv[2];
if (!certificatePath) {
  process.stderr.write("Usage: node scripts/show-server-pin.js <server-certificate.pem>\n");
  process.exit(2);
}
try {
  const pem = fs.readFileSync(certificatePath, "utf8");
  process.stdout.write(publicKeyPin(pem) + "\n");
} catch (error) {
  process.stderr.write("Unable to read a PEM server certificate: " + error.message + "\n");
  process.exit(1);
}
