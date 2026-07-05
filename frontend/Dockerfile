FROM node:22-slim

WORKDIR /app
RUN node --version && npm --version
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV NODE_ENV=production
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]