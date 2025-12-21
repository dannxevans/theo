# =============================
# Build stage
# =============================
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

# Build frontend
RUN npm run build


# =============================
# Runtime stage (nginx)
# =============================
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx template (envsubst-enabled)
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]