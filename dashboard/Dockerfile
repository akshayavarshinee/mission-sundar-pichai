# ---- build stage ----
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so the
# backend + Phoenix URLs must be supplied as build args (see deploy workflow).
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_PHOENIX_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_PHOENIX_BASE=$NEXT_PUBLIC_PHOENIX_BASE
RUN npm run build

# ---- runtime stage ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
ENV PORT=3000
CMD ["npm", "run", "start"]
