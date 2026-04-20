#!/usr/bin/env bash

# Collect all Nix library paths for Playwright Chromium dependencies
NIX_LIBS=""
for pkg in nspr nss alsa-lib dbus at-spi2-core cups libdrm libxkbcommon mesa pango cairo expat xorg.libX11 xorg.libXcomposite xorg.libXdamage xorg.libXext xorg.libXfixes xorg.libXrandr xorg.libxcb glib; do
  path=$(nix-build '<nixpkgs>' -A "$pkg" --no-out-link 2>/dev/null)
  if [ -n "$path" ] && [ -d "$path/lib" ]; then
    NIX_LIBS="$path/lib:$NIX_LIBS"
  fi
done

export LD_LIBRARY_PATH="$NIX_LIBS$LD_LIBRARY_PATH"
exec python run.py
