FROM node:22-bookworm

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund && npm install lightningcss-linux-x64-gnu@1.32.0 @tailwindcss/oxide-linux-x64-gnu@4.3.0 @unrs/resolver-binding-linux-x64-gnu@1.12.2
COPY . .

ENV NODE_ENV=production
RUN npm run build -- --webpack

EXPOSE 3000
CMD ["npm", "start"]
