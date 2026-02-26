console.log("✅ index.js is running...");

const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.json({ ok: true, message: "Backend is running" });
});

app.get("/api/vaults", (req, res) => {
  res.json([
    {
      id: "demo-vault-1",
      name: "Demo Vault",
      chainId: 8453,
      paused: false,
      token0: "ETH",
      token1: "USDC",
    },
  ]);
});

const PORT = process.env.PORT || 8080;

app.listen(PORT, () => {
  console.log(`✅ Backend listening on http://localhost:${PORT}`);
});

// keep-alive so you can *never* get a “clean exit” by accident
setInterval(() => {}, 1 << 30);