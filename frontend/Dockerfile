# =============================================================
#  Frontend Dockerfile  –  Node / Vite / React
# =============================================================

FROM node:20-slim

WORKDIR /app

# ── Install dependencies (cached layer) ───────────────────────
COPY package.json package-lock.json ./
RUN npm ci

# ── Copy source ───────────────────────────────────────────────
COPY . .

# ── Expose Vite dev-server port ───────────────────────────────
EXPOSE 5173

# ── Start Vite dev server, bound to 0.0.0.0 so Docker port-maps work
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
