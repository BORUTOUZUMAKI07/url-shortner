FROM node:22-trixie

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY . .

ENV NODE_ENV=production
RUN npm run build -- --webpack 2>&1

EXPOSE 3000
CMD ["npm", "start"]