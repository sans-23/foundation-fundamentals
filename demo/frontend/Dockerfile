FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# The built static files will be copied into the NGINX container via docker-compose
# We use a lightweight serve image just to hold the build artifacts
FROM alpine:3.19
COPY --from=build /app/dist /app/dist
CMD ["echo", "Frontend build complete. Static files are in /app/dist."]
