const fs = require("fs");
const path = require("path");

const base = process.env.API_BASE || "";
const file = path.join(__dirname, "..", "web", "config.js");
const body = "window.SCM_CONFIG = {\n  apiBase: " + JSON.stringify(base) + "\n};\n";
fs.writeFileSync(file, body);
