# ── Base ──
FROM node:24-alpine AS base
WORKDIR /app

# ── Dépendances ──
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# ── Développement ──
FROM deps AS dev
COPY . .
EXPOSE 5173

# ── Build ──
FROM deps AS build
COPY . .
RUN npm run build

# ── Production ──
FROM nginx:1.27-alpine AS prod
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
