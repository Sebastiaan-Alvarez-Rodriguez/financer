{
  description = "financer";
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils, ... }: flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs {
        inherit system;
      };

      buildPythonPackages = pkgs.python311Packages;

      # Our build
      financer = buildPythonPackages.buildPythonApplication {
        pname = "financer";
        version = "0.0.1";

        meta = {
          homepage = "https://github.com/Sebastiaan-Alvarez-Rodriguez/financer";
          description = "Small project to help making, evaluating, projecting financial decisions.";
        };
        src = ./.;

        propagatedBuildInputs = with buildPythonPackages; [ numpy pandas scipy matplotlib];

        # By default tests are executed, but we don't want to.
        dontUseSetuptoolsCheck = true;
      };
    in rec {
      apps.default = flake-utils.lib.mkApp {
        drv = packages.default;
      };
      packages.default = financer;
      devShells.default = pkgs.mkShell rec {
        packages = with buildPythonPackages; [ numpy pandas scipy matplotlib];
      };
    }
  );
}

