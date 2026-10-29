#!/bin/sh

while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    echo "Aguardando inicializacao do PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)..."
    sleep 2
done

echo "PostgreSQL esta aceitando conexoes ($POSTGRES_HOST:$POSTGRES_PORT)"