FROM node:22-alpine AS build

WORKDIR /app

# Copy the frontend dependencies first
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci

# Copy the rest of the frontend source
WORKDIR /app
COPY frontend/ ./frontend/

# Copy the generated experiment data
COPY experiments/baseline_v1/generated/baseline_evaluation.json ./frontend/public/data/baseline_evaluation.json

# Build the frontend
WORKDIR /app/frontend
# Ensure we don't try to copy data again in the prebuild script since we already copied it here
# so we run vite build directly or disable the sync script
RUN npm pkg delete scripts.prebuild && npm run build

# Nginx stage
FROM nginx:alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
