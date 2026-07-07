FROM node:22-bookworm

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .

ENV NODE_ENV=production
RUN npm run build 2>&1; echo "BUILD_EXIT_CODE=$?"

EXPOSE 3000
CMD ["npm", "start"]