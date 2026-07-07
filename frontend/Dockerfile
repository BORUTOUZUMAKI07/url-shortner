FROM node:22-bookworm

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund && node -e "const{execSync}=require('child_process');['lightningcss','@tailwindcss/oxide','unrs-resolver'].map(p=>{try{const pkg=require('./node_modules/'+p+'/package.json');return[Object.keys(pkg.optionalDependencies||{}).find(n=>n.includes('linux-x64-gnu')),pkg.version]}catch(e){return[null,null]}}).filter(([n])=>n).forEach(([n,v])=>execSync('npm install --no-save '+n+'@'+v,{stdio:'inherit'}))"
COPY . .

ENV NODE_ENV=production
RUN npm run build -- --webpack

EXPOSE 3000
CMD ["npm", "start"]
