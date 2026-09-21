FROM node:24.14.0-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,id=pf-cobraflow-npm,target=/root/.npm npm ci

FROM dependencies AS build
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_INTERNAL_URL=http://api:8101
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
COPY . .
RUN npm run build

FROM node:24.14.0-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3101
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3101
CMD ["node", "server.js"]

FROM dependencies AS checks
ENV NEXT_TELEMETRY_DISABLED=1
COPY . .
CMD ["sh", "-c", "npm run lint && npm run typecheck"]
