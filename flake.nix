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

        python = pkgs.python311;
        poetry = pkgs.poetry.override { python3 = python; };
        nodejs = pkgs.nodejs_20;  # Latest LTS version

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            poetry
            pkgs.docker
            pkgs.docker-compose

            # Node.js environment
            nodejs
            pkgs.nodePackages.npm
          ];

          shellHook = ''
            export POETRY_PYTHON=${python}/bin/python
            poetry config virtualenvs.in-project true
            
            # Set up Node.js environment
            export NODE_PATH=$PWD/node_modules
            export PATH=$PWD/node_modules/.bin:$PATH
          '';
        };
      }
    );
}
