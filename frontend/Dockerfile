# Build from repo root: `docker compose build web` (context `.`, dockerfile frontend/Dockerfile).
# Needs `docs/` for MarketingLandingPage raw HTML import.
FROM node:20-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

COPY frontend ./frontend
COPY docs ./docs

WORKDIR /app/frontend
# Clerk + Vite: must exist at build time to enable Clerk UI in the static bundle (`import.meta.env`).
ARG VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
