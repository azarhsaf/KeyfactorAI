FROM node:20-alpine
WORKDIR /app
COPY package.json tsconfig.json index.html ./
COPY src ./src
RUN npm install && npm run build
CMD ["npm", "run", "dev"]
