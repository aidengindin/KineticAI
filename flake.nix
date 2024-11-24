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

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            poetry
            pkgs.docker
            pkgs.docker-compose
          ];

          shellHook = ''
            export POETRY_PYTHON=${python}/bin/python
            poetry config virtualenvs.in-project true
          '';
        };
      }
    );
}
