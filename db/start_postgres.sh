#!/bin/bash

# Variables
CONTAINER_NAME="rag-postgres"
PG_VERSION="16"
DB_NAME="ragdb"
DB_USER="myuser"
DB_PASSWORD="mypassword"
NETWORK_NAME="opsloom-network"

# Check if the Docker network exists; create it if it doesn't
if ! sudo docker network ls --format '{{.Name}}' | grep -wq "$NETWORK_NAME"; then
  echo "Creating Docker network: $NETWORK_NAME"
  sudo docker network create "$NETWORK_NAME"
else
  echo "Docker network $NETWORK_NAME already exists."
fi

# Check if the container exists
if sudo docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
  echo "Container $CONTAINER_NAME already exists. Starting it."
  sudo docker start "$CONTAINER_NAME"
else
  echo "Creating and starting container: $CONTAINER_NAME"
  sudo docker run -d --name "$CONTAINER_NAME" \
    --network "$NETWORK_NAME" \
    -e POSTGRES_DB="$DB_NAME" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -p 5432:5432 \
pgvector/pgvector:pg16
fi

echo "Waiting for Postgres to be ready..."
until sudo docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."
