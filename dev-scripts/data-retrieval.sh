#!/usr/bin/env bash

set -e

function cleanup {
    echo "Stopping development services..."
    kill $APP_PID 2>/dev/null || true
    docker-compose -f services/data_retrieval/docker-compose.yml down
}
trap cleanup EXIT

function wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service to be ready..."
    while true; do
        if [[ "$(docker-compose -f services/data_retrieval/docker-compose.yml ps --format json $service)" =~ \"Health\"\:\"healthy\" ]]; then
            break
        fi
        if [ $attempt -eq $max_attempts ]; then
            echo "Service $service failed to start after $max_attempts attempts"
            exit 1
        fi
        echo "Attempt $attempt: $service not yet ready..."
        sleep 1
        ((attempt++))
    done
    echo "$service is ready!"
}

echo "Starting data retrieval development services..."
docker-compose -f services/data_retrieval/docker-compose.yml up -d

for service in timescaledb; do
    wait_for_service $service
done

echo "Initializing database schema..."
if ! docker-compose -f services/data_retrieval/docker-compose.yml exec -T timescaledb psql -U dev_user -d dev_db < database/schema.sql; then
    echo "Failed to initialize database schema"
    exit 1
fi

echo "All data retrieval development services are ready!"
echo "Starting data retrieval service..."
poetry run python -m data_retrieval.main --host 0.0.0.0 --port 8001 --reload --log-level debug &
APP_PID=$!
wait $APP_PID 