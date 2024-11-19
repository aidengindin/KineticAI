{
  description = "Python-Based Endurance Platform";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          substituters = [
            "https://cache.nixos.org"
            "https://nix-community.cachix.org"
          ];
          trustedPublicKeys = [
            "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
            "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
          ];
        };

        python = pkgs.python311;

        globalPythonDeps = with pkgs.python311Packages; [
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
          pytest-asyncio
          pytest-mock
          
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

          # Types
          types-redis
        ];

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

        mkPythonServiceTest = name:
          let
            servicePythonEnv = python.withPackages(ps:
              globalPythonDeps
            );
          in
          pkgs.stdenv.mkDerivation {
            pname = "test-${name}";
            version = "0.1.0";
            src = ./services/${name};

            buildInputs = [ servicePythonEnv ];

            dontBuild = true;
            doCheck = true;

            checkPhase = ''
              export PYTHONPATH=$PWD:$PYTHONPATH
              pytest tests/
            '';

            installPhase = "touch $out";
          };

        mkPythonService = name:
          let
            servicePythonEnv = python.withPackages(ps:
              globalPythonDeps
            );
          in
          pkgs.stdenv.mkDerivation {
            pname = name;
            version = "0.1.0";
            src = ./services/${name};

            buildInputs = [ servicePythonEnv ];

            checkPhase = ''
              export PYTHONPATH=$PWD:$PYTHONPATH
              pytest tests/
            '';

            doCheck = true;

            buildPhase = ''
              mkdir -p $out/bin $out/lib
              cp -r $PWD/* $out/lib/

              cat > $out/bin/${name} <<EOF
                #!${pkgs.bash}/bin/bash
                export PYTHONPATH=$out/lib:\$PYTHONPATH
                exec ${servicePythonEnv}/bin/python -m src.main
              EOF

              chmod +x $out/bin/${name}
            '';

            installPhase = "true";
          };

          pythonFormatCheck =
            let
              pythonEnv = python.withPackages(ps:
                globalPythonDeps
              );
            in pkgs.stdenv.mkDerivation {
              name = "python-format-check";
              src = ./.;

              buildInputs = [
                pythonEnv
                pkgs.black
                pkgs.ruff
                pkgs.python311Packages.mypy
              ];

              dontBuild = true;
              doCheck = true;

              checkPhase = ''
                black --check services/
                isort --profile black --check services/
                mypy services/
              '';

              installPhase = "touch $out";
            };

          mkPythonDevApp = name: 
          let
            servicePythonEnv = python.withPackages(ps:
              globalPythonDeps
            );
            service = mkPythonService name;
          in pkgs.writeShellApplication {
            name = "dev-${name}";
            runtimeInputs = [
              servicePythonEnv
              pkgs.docker-compose
              service
            ];

            text = ''
              set -e
              cd services/${name}

              function cleanup {
                echo "Stopping development services..."
                kill $APP_PID 2>/dev/null || true
                docker-compose -f docker-compose.yml down
              }
              trap cleanup EXIT

              echo "Starting development services..."
              docker-compose -f docker-compose.yml up -d

              sleep 5

              echo "Starting the application..."
              ${service}/bin/${name} --host 0.0.0.0 --port 8000 --reload --log-level debug &
              APP_PID=$!
              wait $APP_PID
            '';
          };

          pythonServices = [
            "external_data_gateway"
          ];

          devPythonEnv = python.withPackages(ps:
            globalPythonDeps
          );
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            devPythonEnv
            pkgs.just
          ];

          shellHook = ''
            echo "🏃‍♂️ KineticAI Development Environment"

            # Verify Python installation
            python --version
            which python
          '';
        };

        packages = builtins.listToAttrs (map (name: {
          inherit name;
          value = mkPythonService name;
        }) pythonServices);

        checks = {
          inherit pythonFormatCheck;
        } // builtins.listToAttrs (map (name: {
          name = "test-${name}";
          value = mkPythonServiceTest name;
        }) pythonServices);

        apps = builtins.listToAttrs (map (name: {
          name = "dev-${name}";
          value = {
            type = "app";
            program = "${mkPythonDevApp name}/bin/dev-${name}";
          };
        }) pythonServices);
      }
    );
}
