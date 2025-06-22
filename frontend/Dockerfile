# build env
FROM node:18-alpine

WORKDIR /app

COPY package*.json .

RUN npm install --no-audit --prefer-offline

COPY . .

RUN npm run build
 