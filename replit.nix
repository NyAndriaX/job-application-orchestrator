{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.udev
    pkgs.glib
    pkgs.dbus
    pkgs.expat
    pkgs.xorg.libxcb
    pkgs.xorg.libXrandr
    pkgs.xorg.libXfixes
    pkgs.xorg.libXext
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.xorg.libX11
    pkgs.cairo
    pkgs.pango
    pkgs.mesa
    pkgs.libxkbcommon
    pkgs.libdrm
    pkgs.cups
    pkgs.at-spi2-core
    pkgs.alsa-lib
    pkgs.nss
    pkgs.nspr
  ];
}
