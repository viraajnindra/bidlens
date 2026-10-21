FROM node:22-alpine
WORKDIR /app
RUN npm install -g pnpm@10.28.2
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG API_BASE_URL=http://api:8000
ENV API_BASE_URL=$API_BASE_URL NEXT_TELEMETRY_DISABLED=1
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "exec", "next", "start", "--hostname", "0.0.0.0"]
