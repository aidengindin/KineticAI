#!/usr/bin/env bash

set -e

cd services/external_data_gateway

function cleanup {
    echo "Stopping development services..."
    kill $APP_PID 2>/dev/null || true
    docker-compose -f docker-compose.yml down
}
trap cleanup EXIT

function wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service to be ready..."
    while true; do
        if [[ "$(docker-compose ps --format json $service)" =~ \"Health\"\:\"healthy\" ]]; then
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

function wait_for_vault_init() {
    local max_attempts=30
    local attempt=1

    echo "Waiting for vault initialization..."
    while ! docker compose logs vault-init | grep -q "Success! Enabled the kv secrets engine at: kv/"; do
        if [ $attempt -eq $max_attempts ]; then
            echo "Vault initialization failed after $max_attempts attempts"
            exit 1
        fi
        if docker compose ps vault-init | grep -q "Exit"; then
            exit_code=$(docker compose ps -q vault-init | xargs docker inspect -f '{{.State.ExitCode}}')
            if [ "$exit_code" = "0" ]; then
                echo "Vault initialization completed successfully"
                return
            else
                echo "Vault initialization failed with exit code $exit_code"
                exit 1
            fi
        fi
        echo "Attempt $attempt: Waiting for vault initialization..."
        sleep 1
        ((attempt++))
    done
    echo "Vault initialization completed!"
}

echo "Starting external_data_gateway development services..."
docker-compose -f docker-compose.yml up -d

for service in redis vault; do
    wait_for_service $service
done

wait_for_vault_init

echo "All external_data_gateway development services are ready!"
echo "Starting external_data_gateway service..."
poetry run python -m src.main --host 0.0.0.0 --port 8000 --reload --log-level debug
APP_PID=$!
wait $APP_PID
