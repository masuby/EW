# syntax=docker/dockerfile:1

## Build stage
FROM node:24-alpine AS build
WORKDIR /app

COPY ew-app/package*.json ./
RUN npm ci

COPY ew-app .
RUN npm run build -- --configuration production

## Runtime stage
FROM nginx:1.27-alpine
COPY --from=build /app/dist/ew-app/browser /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
