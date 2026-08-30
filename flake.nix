{
  description = "habla - Voice-to-text daemon powered by Parakeet";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [
      "x86_64-linux"
      "aarch64-linux"
      "aarch64-darwin"
    ] (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
        py = python.pkgs;

        wheel = wheels.${system} or (throw "habla does not support ${system}");

        wheels = {
          x86_64-linux = {
            sherpaUrl = "https://files.pythonhosted.org/packages/75/8c/3a4bcdc71f9ea22b9ce77e2e562324a010be96b855a4cd4a73f83dc6b646/sherpa_onnx-1.13.6-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl";
            sherpaHash = "sha256-AtC6OyV+HHSzDHl17EZsrI4B4bRZnQZX6kr6B2/EnTc=";
            coreUrl = "https://files.pythonhosted.org/packages/fa/0a/6f64568ebb230b200c30c465eb002113944705fa36c734838ea46f2e1802/sherpa_onnx_core-1.13.6-py3-none-manylinux2014_x86_64.whl";
            coreHash = "sha256-nBJgrhUOvU9liFT9jYyoR3gor6W+v2bBsvYTLx9wSiE=";
          };
          aarch64-linux = {
            sherpaUrl = "https://files.pythonhosted.org/packages/da/71/9fe597931cfcff8c42e4631156bf5a4efb90d6c635f8dd09f1d815f221eb/sherpa_onnx-1.13.6-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl";
            sherpaHash = "sha256-0zuQZlF2Dzb1nNI5ns6M1hm+jEFBBzMlPHti0kK330o=";
            coreUrl = "https://files.pythonhosted.org/packages/58/ab/ab279cf4eb6d4aa4b5f703d4e8233365c3acee304b963a09d4cb71601324/sherpa_onnx_core-1.13.6-py3-none-manylinux2014_aarch64.whl";
            coreHash = "sha256-4keyA8pkq3CVhk0+8aIRWXh+AqmFp98TdlJgQ3fHgz4=";
          };
          aarch64-darwin = {
            sherpaUrl = "https://files.pythonhosted.org/packages/d2/e9/8df794db2be1c4f50091399f8e5793c3c51454ee3a201e55f5e83e09bda6/sherpa_onnx-1.13.6-cp312-cp312-macosx_11_0_arm64.whl";
            sherpaHash = "sha256-1v8ahK1o/uGF98XettUOR9Xi6NlkwqWplONJVWffW/0=";
            coreUrl = "https://files.pythonhosted.org/packages/06/ee/dbbc6718e263e4961106e057c187875e00485ca8030a6bca0d9682807d30/sherpa_onnx_core-1.13.6-py3-none-macosx_11_0_arm64.whl";
            coreHash = "sha256-KkExId0O4uU8Rd7z6k6PDpaKasdPjP0oi+064syBXDM=";
          };
        };

        sherpa-onnx-core = py.buildPythonPackage {
          pname = "sherpa-onnx-core";
          version = "1.13.6";
          format = "wheel";
          src = pkgs.fetchurl {
            url = wheel.coreUrl;
            hash = wheel.coreHash;
          };
          nativeBuildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [ pkgs.autoPatchelfHook ];
          buildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [ pkgs.stdenv.cc.cc.lib ];
          dontStrip = true;
        };

        sherpa-onnx = py.buildPythonPackage {
          pname = "sherpa-onnx";
          version = "1.13.6";
          format = "wheel";
          src = pkgs.fetchurl {
            url = wheel.sherpaUrl;
            hash = wheel.sherpaHash;
          };
          dependencies = [ sherpa-onnx-core ];
          nativeBuildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [ pkgs.autoPatchelfHook ];
          buildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
            pkgs.alsa-lib
            pkgs.stdenv.cc.cc.lib
          ];
          autoPatchelfIgnoreMissingDeps = [ "libonnxruntime.so" ];
          postFixup = pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
            patchelf --add-rpath \
              ${sherpa-onnx-core}/${python.sitePackages}/sherpa_onnx/lib \
              $out/${python.sitePackages}/sherpa_onnx/lib/_sherpa_onnx*.so
          '';
          dontStrip = true;
          pythonImportsCheck = [ "sherpa_onnx" ];
        };

        habla = py.buildPythonApplication {
          pname = "habla";
          version = "0.2.0";
          format = "other";
          src = self;
          dontBuild = true;

          dependencies = [
            py.numpy
            sherpa-onnx
            py.sounddevice
          ];

          installPhase = ''
            runHook preInstall
            mkdir -p $out/${python.sitePackages} $out/bin
            cp -r src/habla $out/${python.sitePackages}/
            cat > $out/bin/habla <<EOF
            #!${python.interpreter}
            from habla.habla import main
            main()
            EOF
            chmod +x $out/bin/habla
            runHook postInstall
          '';

          # The packaged sherpa-onnx wheel is the portable CPU build.
          makeWrapperArgs = [ "--set-default HABLA_ONNX_PROVIDER cpu" ];
          pythonImportsCheck = [ "habla" ];

          meta = {
            description = "Voice-to-text daemon powered by Parakeet";
            homepage = "https://github.com/baitinq/habla";
            mainProgram = "habla";
          };
        };
      in
      {
        packages = {
          default = habla;
          inherit habla;
        };

        apps.default = {
          type = "app";
          program = pkgs.lib.getExe habla;
          meta = habla.meta;
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python312
            uv
            portaudio
          ];
        };
      });
}
