# Static Wi-Fi diagnostic tool

Built locally for Linux ARM64, including Android recovery, without Android shared-library dependencies. No device access was performed during the build.

- Binary: `diagnostics/tools/iw-build/iw-static/iw`
- SHA256: `4bd645310c7316f170d378228bdbfc87cbc6194b9c301ecfc6a17480f8cfbdc8`
- Size: 2,683,608 bytes
- Verified format: ELF64 little-endian AArch64 executable, no `PT_INTERP` and no `PT_DYNAMIC`. The iw command-registration section is present.
- Runtime validation: pending parent operator's device test. Static linking and architecture checks do not guarantee kernel/driver support.

## Sources and compiler

| Input | Provenance | SHA256 or revision |
| --- | --- | --- |
| iw 6.9 | [kernel.org source archive](https://www.kernel.org/pub/software/network/iw/iw-6.9.tar.xz) | SHA256 `3f2db22ad41c675242b98ae3942dbf3112548c60a42ff739210f2de4e98e4894` |
| libnl-tiny | [OpenWrt source](https://github.com/openwrt/libnl-tiny/tree/40493a655d8caa2ccf5206dde1e733abe2920432) | Git `40493a655d8caa2ccf5206dde1e733abe2920432` |
| Zig 0.14.1 macOS ARM64 | [official compiler archive](https://ziglang.org/download/0.14.1/zig-aarch64-macos-0.14.1.tar.xz) | Published SHA256 `39f3dc5e79c22088ce878edc821dedb4ca5a1cd9f5ef915e9b3cc3053e8faefa` |

The Zig archive hash was checked against the [official download index](https://ziglang.org/download/index.json) before extraction. The iw source hash is the locally recorded archive hash; no separate release-signature verification is claimed. No third-party prebuilt Android utility was used.

Downloaded archives, extracted compiler and sources, objects, libraries, binary, and manifest are under the ignored `diagnostics/tools/iw-build/` directory. Rebuild from these inputs using:

```sh
python3 scripts/build-static-iw.py
```

The script invokes Zig's C compiler with `-target aarch64-linux-musl -O2`, builds libnl-tiny as a static archive, and links iw with `-static -Wl,--no-gc-sections`. The linker flag retains iw's section-based command registration. The upstream generated command-name table is produced with equivalent Python logic because the upstream Makefile assumes GNU sed. No handwritten changes were made to iw's diagnostic or netlink behavior.

## Suggested parent-controlled checks

After an explicitly chosen transfer to a temporary device path, first verify `iw --version`, then list interfaces with `iw dev`. Read capabilities with `iw phy` and current link state with `iw dev wlan0 link`, substituting the actual interface name. A root/CAP_NET_ADMIN shell can request a scan with `iw dev wlan0 scan`; unsupported nl80211 operations or firmware failures may still prevent it.

The build script never opens USB, resets the device, modifies firmware, or starts a scan. Host-side ELF validation was completed; live-device tests are a separate step.
