FROM node:22-alpine AS builder

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY internal ./internal
COPY packages ./packages
COPY apps/bidpivot-frontend ./apps/bidpivot-frontend

# The app was added after the lockfile was generated; regenerate importer
# metadata instead of failing a frozen install.
RUN pnpm install --no-frozen-lockfile

RUN pnpm --filter @bidpivot/frontend build

FROM nginx:1.27-alpine

COPY apps/bidpivot-frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/bidpivot-frontend/dist /usr/share/nginx/html

EXPOSE 80
