#!/usr/bin/env bash

set -e

function cleanup {
    echo "Stopping development services..."
    kill $APP_PID 2>/dev/null || true
    docker-compose -f services/data_ingestion/docker-compose.yml down
}
trap cleanup EXIT

function wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service to be ready..."
    while true; do
        if [[ "$(docker-compose -f services/data_ingestion/docker-compose.yml ps --format json $service)" =~ \"Health\"\:\"healthy\" ]]; then
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

echo "Starting data ingestion development services..."
docker-compose -f services/data_ingestion/docker-compose.yml up -d

for service in timescaledb redis; do
    wait_for_service $service
done

echo "All data ingestion development services are ready!"
echo "Starting data ingestion service..."
poetry run python -m data_ingestion.main --host 0.0.0.0 --port 8000 --reload --log-level debug &
APP_PID=$!
wait $APP_PID 