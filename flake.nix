# flake.nix
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
          pydantic
          
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
          passlib     # password hashing
          requests
          httpx
          
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
      }
    );
}
