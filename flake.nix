{
  description = "Python-Based Endurance Platform";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          # Web framework and API
          fastapi
          uvicorn
          pydantic-settings
          
          # Data processing
          pandas
          numpy
          scipy
          scikit-learn
          
          # Database
          sqlalchemy
          psycopg2
          redis
          
          # Utils
          python-jose  # JWT
          passlib      # password hashing
          requests     # HTTP client
          aiohttp      # async HTTP client
          backoff      # retrying
          hvac         # HashiCorp Vault
          
          # Testing
          pytest
          pytest-cov
          
          # Dev tools
          black
          isort
          mypy
          flake8
          setuptools
          
          # ML/NLP
          transformers
          torch
          
          # Monitoring
          prometheus-client
          
          # Task queue
          celery
        ]);

        # Development tools
        devTools = with pkgs; [
          postgresql_15
          redis
          # kafka
          docker
          docker-compose
          kubectl
          terraform
          
          # CLI tools
          git
          vim
          tmux
          jq
          direnv
          
          # Python tools
          poetry
        ];

        externalDataGatewayScript = pkgs.writeScript "external-data-gateway" ''
          set -e
    
          function cleanup {
            echo "Stopping development services and application..."
            kill $APP_PID 2>/dev/null || true
            ${pkgs.docker-compose}/bin/docker-compose -f docker-compose.dev.yml down
          }
          
          trap cleanup EXIT
          
          echo "Starting development services..."
          ${pkgs.docker-compose}/bin/docker-compose -f docker-compose.dev.yml up -d
          
          # Wait for Redis to be healthy
          echo "Waiting for Redis to be ready..."
          until ${pkgs.docker-compose}/bin/docker-compose -f docker-compose.dev.yml exec -T redis redis-cli ping; do
            echo "Redis is unavailable - sleeping"
            sleep 1
          done
          
          # Wait for Vault to be healthy
          echo "Waiting for Vault to be ready..."
          until ${pkgs.docker-compose}/bin/docker-compose -f docker-compose.dev.yml exec -T vault vault status; do
            echo "Vault is unavailable - sleeping"
            sleep 1
          done
          
          # Set up Vault dev token
          export VAULT_ADDR="http://localhost:8200"
          export VAULT_TOKEN="dev-token"
          
          echo "Development services are ready!"
          echo "Redis is running on localhost:6379"
          echo "Vault is running on localhost:8200"
          
          # Start the FastAPI application
          echo "Starting the application..."
          ${pythonEnv}/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
          APP_PID=$!
          
          # Wait for the application to exit
          wait $APP_PID
        '';
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
          ] ++ devTools;

          shellHook = ''
            echo "🏃‍♂️ Endurance Platform Development Environment"
            
            # Set up environment variables
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
            export DEVELOPMENT_ENV="local"
            
            # Create local configuration if it doesn't exist
            if [ ! -f .env ]; then
              cp .env.example .env
            fi

            # Create virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi
            
            # Activate virtual environment
            source .venv/bin/activate
            
            # Install pre-commit hooks
            if [ -f .pre-commit-config.yaml ]; then
              pre-commit install
            fi

            # Verify Python installation
            python --version
            which python
          '';
        };

        # Example package definition for a service
        packages.default = pkgs.python311Packages.buildPythonApplication {
          pname = "kinetic-ai";
          version = "0.1.0";
          src = ./.;
          
          propagatedBuildInputs = [
            pythonEnv
          ];

          checkInputs = [
            pkgs.python311Packages.pytest
            pkgs.python311Packages.pytest-cov
          ];

          checkPhase = ''
            pytest tests/
          '';
        };

        apps = {
          devExternalGateway = {
            type = "service";
            script = externalDataGatewayScript;
          };
        };
      }
    );
}
