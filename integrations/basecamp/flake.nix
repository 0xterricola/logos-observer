{
  description = "Logos Observer - Basecamp integration module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
      postInstall = ''
        mkdir -p "$out/share/logos/observer-runtime"
        cp -v ${./runtime}/*.py "$out/share/logos/observer-runtime/"
        cp -v ${./runtime}/requirements.txt "$out/share/logos/observer-runtime/"
      '';

    };
}
