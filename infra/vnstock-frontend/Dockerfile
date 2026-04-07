# ═══════════════════════════════════════════════════════════
# VVS Frontend — Multi-stage Docker build
# ═══════════════════════════════════════════════════════════
# Stage 1: Build React app (node:20-alpine)
# Stage 2: Serve static via nginx:1.25-alpine
# RAM optimization: limit Node heap during build, nginx worker_processes 1
# ═══════════════════════════════════════════════════════════

# ─── Build stage ───────────────────────────────────────────
FROM node:18-alpine AS build
WORKDIR /app

# Cache dependencies layer (chỉ rebuild khi package.json thay đổi)
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps --no-audit --no-fund 2>/dev/null && \
    npm install ajv@8.17.1 --no-audit --no-fund 2>/dev/null

# Copy source & build
COPY . .
# Limit Node.js heap to 512MB (máy 32GB cần chia sẻ với 40+ containers)
ENV NODE_OPTIONS="--max-old-space-size=512"
ENV GENERATE_SOURCEMAP=false
RUN npm run build

# ─── Production stage ─────────────────────────────────────
FROM nginx:1.25-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy built assets + custom nginx config
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

# Non-root: nginx alpine runs master process as root, worker as nginx user
# Ensure cache/temp dirs are writable
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx && \
    touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid

EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
