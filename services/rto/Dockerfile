FROM golang:1.22-alpine AS build

WORKDIR /src
COPY go.mod ./
RUN go mod download || true

COPY . .
RUN go mod tidy && CGO_ENABLED=0 go build -o /out/rto ./cmd/server

FROM alpine:3.20
RUN adduser -D -u 10001 rto
USER rto
COPY --from=build /out/rto /usr/local/bin/rto
EXPOSE 8080
ENTRYPOINT ["rto"]
