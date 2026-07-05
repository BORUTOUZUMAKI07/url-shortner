FROM node:22-bookworm

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .

# Check node and next versions before building
RUN node --version && npm --version && npx next --version

ENV NODE_ENV=production
RUN npm run build 2>&1

EXPOSE 3000
CMD ["npm", "start"]