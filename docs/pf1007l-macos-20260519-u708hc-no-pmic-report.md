# PF1007L / `20260519` on macOS: a board revision with no PMIC (`U708HC`)

One Portrait-branded PF1007L (`FL-AIMOR-OS.0.20260519`, the larger eMMC) went through Route U's read-only backup on macOS, then booted mainline Linux from microSD. The main finding: **this unit's board has no AXP PMIC at all**. Its vendor config names the board `U708HC`. The Linux and U-Boot device trees that assume an AXP223 on RSB fail on it. It likely explains the "AXP PMIC programming in the SPL failed with `-EIO`" result on [UK unit 1](pf1007l-macos-uk-20260519-20260529-report.md#unit-1-the-spl-hang-was-dram-byte-lane-1).

One unit, one session (2026-11-10 to 2026-11-16). Observations are marked [observed]; inferences are marked [inference].

## Report

```text
About model / firmware:   PF1007L; YHK.F-null-A33-1001-D1024-PF1007L-FL-AIMOR-OS.0.20260519
AiMOR version:            6.0.78
Ports (DC jack, or USB-C only): USB-C only, TF slot (rear label: Portrait PF1007, FCC ID 2AW9M-PORTRAIT)
Cable and port that gave USB data: the first A-to-C cable gave no USB device at all; a second
                          A-to-C data cable on a USB-C-to-A adapter directly on an M3 Max MacBook Pro worked
T3 USB IDs seen / adb devices output: 1f3a:1000 "Android"; adb devices empty
T3b network ADB result (port 5555): skipped (frame kept off Wi-Fi)
T4 sunxi-fel version output: AWUSBFEX soc=00001667(A33) 00000001 ver=0001 44 08 scratchpad=00007e00 00000000 00000000
T5 check-dump stage / chunks: skipped
eMMC size in sectors:     30,777,344
Boot partition start sector: 172032 (partitions start at 73728, 139264, 172032, 237568, 2334720, 2400256, ...)
Boot image SHA-256 (sector 172032, 31,028 sectors): 9a6e2456... (matches the 20260519 row)
Route used and result:    Route U read-only backup: complete and verified (15 segments, two reads each, gzip verified).
                          No boot patch written (not needed for this owner's goal).
Host OS:                  macOS 27 (Apple silicon)
First failed step and its exact output: emmc-macos.py backup-resume:
                          "STOP: [Errno 6] Device not configured during segment 0 (backup)", at a different
                          point each run, until U-Boot's console input was nulled (below)
```

## 1. No PMIC on this board

**Symptom** [observed]. Mainline Linux (7.2.10, Arch Linux ARM `linux-armv7`) with a device tree that has the AXP223 on R_RSB:

```text
sunxi-rsb 1f03400.rsb: RSB running at 3000000 Hz
sunxi-rsb 1f03400.rsb: /soc/rsb@1f03400/pmic@3a3: set runtime address failed: -22
axp20x-rsb sunxi-rsb-3a3: AXP20x variant AXP223 found
axp20x-rsb sunxi-rsb-3a3: Failed to set masks in 0x40: -5
axp20x-rsb sunxi-rsb-3a3: probe with driver axp20x-rsb failed with error -5
```

(`AXP223 found` comes from the device-tree compatible, not from a register read.) Every regulator the device tree takes from the PMIC never appears, so anything that depends on them, the SD card included, never probes.

**What was ruled out** [observed]:

| Test | Result |
| --- | --- |
| RSB at 400 kHz instead of 3 MHz | Same failure |
| Device tree without the AXP interrupt (the driver then skips the IRQ chip) | The regulator driver fails on its first write; every register reads `XX` through regmap debugfs |
| Boot stock Android, then press RESET (SoC reset, power kept), then boot Linux from the card | Same failure |
| Raw RSB transfers from userspace (`/dev/mem`), the vendor U-Boot's exact sequence: `CCR = 0x103`, `DMCR = 0x807c3e00`, PL0/PL1 drive level 2 | Set-runtime-address (`0xE8`, hardware address `0x3a3`) gets no ACK (`INTS = 0x10003`); `RD8` of register `0x03` gets a data error at **all 255 runtime addresses** |
| I2C scans | Nothing at `0x34` on R_I2C (PL0/PL1), I2C0 (touch at `0x40`) or I2C1 (accelerometer at `0x19`) |

Gotcha for anyone repeating the raw test: Linux gates the RSB clock while idle, so writes to the RSB registers are ignored unless bit 3 of `0x01f01428` is set first.

**The vendor's view** [observed]:

- The vendor U-Boot (2011.09, built May 19 2026, in the boot package at `0x12a6000` of the eMMC) uses the same RSB setup as mainline: same pins and `CCR`, device-mode word `0x807c3e00`, hardware address `0x3a3` (passed from its AXP22x probe), runtime address `0x2d`. Its "PMU: AXP22x found" path is generic code that fails quietly.
- The kernel `script.bin` (at `0x139a000` of the eMMC; entries are `name[32]`, value offset, words, type) has **75 sections and no `pmu1_para`, `power_sply` or `pmu1_regu`**. `[product] machine = U708HC`. Every supply entry is `"none"` (`sdc_regulator`, `audio_hp_ldo`), and `[lcd0_para]` has no power rail, only `lcd_bl_en = PH6`, `lcd_gpio_0 = PH7` and PWM on PH0.
- Wi-Fi differs from the board the [Omarchy port](https://github.com/pangoleen/ormarch-picture-frame) was built on: `[rf_para] chip_en = PL5` (that port uses PL2), `wl_reg_on = PL6`, `wl_host_wake = PL7`.

**Conclusion** [inference, strongly supported]: this board revision powers its rails from fixed regulators and has no PMIC. Stock Android works because nothing in it needs one.

**What this means for this repo** [inference]:

- Route U itself was unaffected: the read-only backup used the 12 MHz low-power build (`CONFIG_SUNXI_NO_PMIC=y`). A build that programs the PMIC would get `power_failed = -5`, as UK unit 1 did, and the CPU would stay at the SPL's default clock.
- If a `20260519` unit fails PMIC programming, suspect this board revision before suspecting the bus. Quick check from a backup: look for `pmu1_para` in the `script.bin` sections, or `[product] machine`.

**Working mainline device tree** [observed]: the Omarchy port's board tree with `&r_rsb` disabled, every AXP-supplied consumer (`mmc0`/`mmc1` supplies, DSI `vcc-dsi`, panel `vccio`/`vdd`, backlight `power-supply`, touch `avdd`/`vddio`) moved to one always-on fixed 3.3 V regulator, USB VBUS left to the PHY's fallback, and Wi-Fi chip-enable on PL5. With it, the DSI panel, the Silead touch, the AIC8800 on SDIO (`C8A1:C08D`), cpufreq (120–1008 MHz) and `lima` all work.

## 2. UMS drops at random points: nulled console input fixed it

[observed] With the 12 MHz low-power + START STOP build, the read-only UMS disk disappeared two runs in a row (about 7 minutes in each, at different byte offsets: 64% and 90% into segment 1's second pass). Adding `CONFIG_SYS_DEVICE_NULLDEV=y` and a boot script that runs `setenv stdin nulldev` before `ums`, as in the [May macOS report's recipe](pf1007l-macos-20260529-report.md#reproduce-the-ram-only-build), fixed it: the next run read the whole 15.8 GB eMMC twice (about 2 hours at 4.7–4.8 MB/s) with no drop. Build: v2025.10 + `pf1007l-uboot.patch` + START STOP + 12 MHz low-power + `SYS_DEVICE_NULLDEV`. The SPL ended at `0x3f26` (warm-up `0x3f36`), the same as the 12 MHz build without it. DRAM trained on the first cold load; the warm-up SPL was not needed.

[inference] This matches the floating console RX pin explanation (noise read as Ctrl+C ends `ums`).

## 3. Touch firmware and the boot ramdisk

[observed] `gslX680new.ko` is in the boot ramdisk (with `disp.ko`, `lcd.ko`, `nand.ko`, `sunxi-keyboard.ko`, `sw-device.ko`). The `gsl_m86_hd` entry it selects (`ctp_name = gsl_m86_hd`) is byte-identical to the January units' (`gsl_m86_hd.fw` SHA-256 `e11ffa8a...`). The only panel driver in `lcd.ko` is `yhk_zr789_sq9365_101`.

## 4. Smaller notes

- [observed] macOS 27: `system_profiler SPUSBDataType` returns nothing at all; `system_profiler SPUSBHostDataType` and `ioreg -p IOUSB -w 0` work. A FEL check that greps `SPUSBDataType` silently finds nothing.
- [observed] A 128 GB SDXC card (factory MBR, exFAT starting at sector 32768) worked as the FEL stub card with `fel-card-macos.py`, unchanged. A card that isn't fully seated boots Android without warning.
- [observed] Under mainline Linux, the touchscreen's axes are swapped relative to the portrait panel (its own coordinate space is the fex's 1024×600 landscape). Measured libinput calibration for this unit: `0 0.979 0.008 0.991 0 0.009`.
