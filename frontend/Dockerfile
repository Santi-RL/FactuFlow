ARG IMAGE_REGISTRY=docker.io/library

# Build stage
FROM ${IMAGE_REGISTRY}/node:24.15.0-alpine AS build

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --global npm@11.12.1 && npm ci

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM ${IMAGE_REGISTRY}/nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
