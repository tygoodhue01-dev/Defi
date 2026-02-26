const express = require("express");
const cors = require("cors");

const app = express();

// Allow requests from anywhere (fine for now)
app.use(cors());
app.use(express.json());

// Health route
app.get("/", (req, res) => {
  res.json({ ok: true, message: "Backend is running" });
});

// Demo vault route
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

// ✅ IMPORTANT: use Render's dynamic port
const PORT = process.env.PORT || 8080;

app.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
});