FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN corepack enable && corepack prepare pnpm@10.18.0 --activate && pnpm install
COPY . .
RUN pnpm build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
