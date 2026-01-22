# frontend/Dockerfile
FROM node:18.18.0-bullseye-slim AS build
WORKDIR /app

# Manifiestos primero (cache de deps)
COPY package.json package-lock.json ./

# Instalar dependencias (evita fallo por lock desincronizado)
RUN npm install --omit=dev

# Código (sin node_modules)
COPY . .

# Build más estable dentro de Docker
ENV NODE_OPTIONS="--max-old-space-size=2048"
ENV GENERATE_SOURCEMAP=false
ENV DISABLE_ESLINT_PLUGIN=true
ENV BROWSERSLIST_IGNORE_OLD_DATA=true
ENV CI=false

# Build estático
RUN npm run build

# --- Runtime Nginx ---
FROM nginx:alpine
WORKDIR /usr/share/nginx/html
# Serviremos en 80 y 8080 para no depender de qué puerto apunte el TG
EXPOSE 80 8080
# Estático generado
COPY --from=build /app/build /usr/share/nginx/html
# Conf con healthcheck, SPA fallback y proxy opcional a /api
COPY nginx.conf /etc/nginx/conf.d/default.conf
