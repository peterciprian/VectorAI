FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run export
EXPOSE 3000
CMD ["npm", "run", "serve"]
