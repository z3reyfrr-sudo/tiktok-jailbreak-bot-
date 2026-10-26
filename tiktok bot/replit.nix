{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.chromium
    pkgs.nss
    pkgs.nspr
    pkgs.atk
    pkgs.at-spi2-atk
    pkgs.cups
    pkgs.libdrm
    pkgs.libxkbcommon
    pkgs.alsa-lib
    pkgs.dbus
    pkgs.expat
    pkgs.libgbm
    pkgs.pango
    pkgs.cairo
    pkgs.glib
  ];
}
