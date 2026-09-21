FROM postgres:18.6-alpine3.24@sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873
# The entrypoint only needs gosu's user-switching interface. su-exec provides it
# without the unused Go networking stack bundled in the upstream gosu binary.
RUN apk add --no-cache su-exec=0.3-r0 \
    && rm /usr/local/bin/gosu \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/' /usr/local/bin/docker-entrypoint.sh \
    && test "$(su-exec postgres id -u)" = "$(id -u postgres)" \
    && ! grep -q 'exec gosu' /usr/local/bin/docker-entrypoint.sh
