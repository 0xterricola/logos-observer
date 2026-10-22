{
  description = "Logos Observer - Basecamp integration module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    let
      pkgs = logos-module-builder.inputs.nixpkgs.legacyPackages.aarch64-darwin;

      python = pkgs.python3.withPackages (ps: [
        ps.pyinstaller
        ps.cryptography
      ]);

      portableRuntime = pkgs.stdenvNoCC.mkDerivation {
        pname = "logos-observer-portable";
        version = "0.1.4";

        src = ./runtime;
        nativeBuildInputs = [ python pkgs.darwin.system_cmds pkgs.cctools pkgs.darwin.sigtool ];

        dontConfigure = true;
        dontBuild = true;

        installPhase = ''
          runHook preInstall

          export HOME="$TMPDIR"
          export PYINSTALLER_CONFIG_DIR="$TMPDIR/pyinstaller-cache"

          mkdir -p "$out"

          pyinstaller \
            --noconfirm \
            --clean \
            --onedir \
            --name logos-observer \
            --target-arch arm64 \
            --paths "$PWD" \
            --distpath "$out" \
            --workpath "$TMPDIR/pyinstaller-work" \
            --specpath "$TMPDIR" \
            ./v2_server.py

          test -x "$out/logos-observer/logos-observer"

          # Repair Nix-derived OpenSSL paths after PyInstaller collection.
          internal="$out/logos-observer/_internal"
          rust="$internal/cryptography/hazmat/bindings/_rust.abi3.so"
          ssl="$(find "$internal/lib-dynload" -name '_ssl*.so' -print -quit)"
          hashlib="$(find "$internal/lib-dynload" -name '_hashlib*.so' -print -quit)"
          legacy="$internal/ossl-modules/legacy.dylib"

          for binary in "$rust" "$ssl" "$hashlib" "$legacy"; do
            test -f "$binary"
          done

          install_name_tool -change             "@loader_path/../../../../../../../../lib/libssl.3.dylib"             "@loader_path/../../../libssl.3.dylib" "$rust"

          install_name_tool -change             "@loader_path/../../../../../../../../lib/libcrypto.3.dylib"             "@loader_path/../../../libcrypto.3.dylib" "$rust"

          install_name_tool -change             "@loader_path/../../../../../../lib/libssl.3.dylib"             "@loader_path/../libssl.3.dylib" "$ssl"

          install_name_tool -change             "@loader_path/../../../../../../lib/libcrypto.3.dylib"             "@loader_path/../libcrypto.3.dylib" "$ssl"

          install_name_tool -change             "@loader_path/../../../../../../lib/libcrypto.3.dylib"             "@loader_path/../libcrypto.3.dylib" "$hashlib"

          install_name_tool -change             "@loader_path/../../../../../../lib/libcrypto.3.dylib"             "@loader_path/../libcrypto.3.dylib" "$legacy"

          install_name_tool -id "@rpath/libssl.3.dylib"             "$internal/libssl.3.dylib"

          install_name_tool -change             "@loader_path/../../../../../lib/libcrypto.3.dylib"             "@loader_path/libcrypto.3.dylib"             "$internal/libssl.3.dylib"

          install_name_tool -id "@rpath/libcrypto.3.dylib"             "$internal/libcrypto.3.dylib"

          for binary in "$rust" "$ssl" "$hashlib" "$legacy"             "$internal/libssl.3.dylib" "$internal/libcrypto.3.dylib"; do
            codesign --force --sign - "$binary"
          done

          runHook postInstall
        '';
      };
    in
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;

      postInstall = ''
        mkdir -p "$out/share/logos/observer-runtime"

        cp -v ${./runtime}/*.py \
          "$out/share/logos/observer-runtime/"

        cp -v ${./runtime}/requirements.txt \
          "$out/share/logos/observer-runtime/"

        cp -R ${portableRuntime}/logos-observer \
          "$out/share/logos/observer-runtime/portable-macos-arm64"
      '';
    };
}
