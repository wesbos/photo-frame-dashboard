# VESWWE DP100 that reports DP101 (Android 10, `ceres` platform)

A record of **one unit**, set up on 2026-10-13. Its About screen says `VESWWE DP100`, like the
frame in [veswwe-10.1.md](veswwe-10.1.md), but ADB shows a different board and Android version.
Nothing from the RK3326 docs or `scripts/` applies to it. Check `ro.product.model` and
`ro.board.platform` before following either page.

End result: Home HQ is the Home app and boots into the dashboard, touch works, Frameo is disabled
and the Adups updater is removed for user 0. No root, WebView swap, backup image, boot patch or
flash was needed. Everything below is reversible over ADB.

**Tested on:** one unit, bought from [Amazon.ca B0H2FC19YB](https://www.amazon.ca/dp/B0H2FC19YB),
from a Mac (Apple silicon, macOS 26) with Google's platform-tools 37.0.1 over USB.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| About screen | `VESWWE DP100`, Frameo `v1.32.12 (78070)` |
| `ro.product.model` | `DP101` |
| `ro.board.platform` | `ceres` |
| Android | 10 |
| `ro.build.display.id` | `DP101_Frameo_V02_26061607` |
| `ro.product.cpu.abi` | `armeabi-v7a` |
| Display | `wm size` 800x1280 (shown landscape), 68 Hz, density **190** (188 × 189 dpi) |
| WebView | `com.android.webview` 113.0.5672.136 (version code 567263600), the only WebView package |
| Home app (stock) | `net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` |
| Vendor packages | `net.frameo.frame`, `com.adups.fota` |
| Screen defaults | `screen_off_timeout` 2147483647, `stay_on_while_plugged_in` 0, brightness 178 (manual) |

Not recorded: SoC (see Guesses), kernel, RAM, USB IDs, the cable used, and the result of
`su -c id` (the command printed nothing before the session was interrupted). Root was not needed.

## Setup that worked

1. **ADB:** Frameo Settings → About → **Enable Beta Program**, then **ADB access**. `adb devices`
   showed the frame as `device` after accepting the prompt.
2. **Install and set as Home** (from [the kiosk README](../dashboard/kiosk/README.md)):

   ```sh
   adb install -r homehq.apk
   adb shell am start -n com.wesbos.homehq/.MainActivity --es url https://your-dashboard/
   adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
   adb shell cmd package set-home-activity com.wesbos.homehq/.Home
   adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
   ```

   `cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME`
   then returned `com.wesbos.homehq/.Home`. The Home HQ navigation service was listed in
   `enabled_accessibility_services` before and after a reboot.
3. **Density:** at the stock density of 190 the bottom of a 1280×800 dashboard was cut off. This
   fixed it (owner confirmed the dashboard fits):

   ```sh
   adb shell wm density 160      # undo: adb shell wm density reset
   ```

   `wm density` showed `Override density: 160` after a reboot. A dark band along two edges of the
   screen is the bezel: `dumpsys display` reports an app area of the full 800×1280.
4. **Wi-Fi check before disabling Frameo:** `dumpsys wifi | grep -m1 mWifiInfo` showed the network
   connected (`Supplicant state: COMPLETED`), so Wi-Fi is stored in Android, not only in Frameo.
   It reconnected after the reboot with Frameo disabled.
5. **Frameo and Adups:**

   ```sh
   adb shell pm list packages -s -e > frame-packages-backup.txt
   adb shell pm disable-user --user 0 net.frameo.frame
   adb shell pm disable-user --user 0 com.adups.fota
   ```

   After a reboot both were listed as disabled, but `com.adups.fota` was still running, with a new
   PID on each check (5544, then 5995). Removing it for user 0 stopped it; no `frameo` or `fota`
   process was running afterwards:

   ```sh
   adb shell pm uninstall -k --user 0 com.adups.fota
   ```

6. **Reboot:** the Frameo boot logo appears, then Home HQ's "Connect to Wi-Fi?" screen for about a
   minute while Wi-Fi connects, then the dashboard. Touch works.

USB ADB still connected after the reboot with Frameo disabled. Checked by hand on the panel: a
two-finger hold opened the Home HQ controls, **Android settings** opened Settings, Apps listed Frameo
as disabled, and the floating **Dashboard** button returned to the kiosk (README rule 9).

## Undo

```sh
adb shell cmd package install-existing com.adups.fota
adb shell pm enable com.adups.fota
adb shell pm enable net.frameo.frame
adb shell cmd package set-home-activity net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted
adb shell wm density reset
```

To undo the kiosk as Home, see the [kiosk README](../dashboard/kiosk/README.md#start-at-boot).

## Second unit: USB ID, root shell and WebView 113 CSS limits

A second unit with the same build string, bought from a different listing:
[Amazon.nl B0H6NQVZGW](https://www.amazon.nl/dp/B0H6NQVZGW), titled "Frameo Digital Photo Frame WiFi
10.1 inch VESWWE Electronic Photo Frame 1280 x 800 IPS Touch Screen 32GB Storage" (white). It was set
up on 2026-10-17 from a Hackintosh (Intel PC running macOS 15.4, x86_64) with Google's
platform-tools 37.0.1 (Homebrew cask) over USB. Home HQ was set as the default Home app using the
steps above; Frameo and Adups were left enabled.

**Host and cable.** The frame connected to the Hackintosh with a USB-C to USB-C cable and a USB-C
to USB-A adapter on the host end, plugged into a USB-A port. On a Mac mini M4 (Apple silicon) the
same USB-C to USB-C cable plugged straight in did nothing. What then worked on the Mac mini: frame
USB-C, the USB-C to USB-C cable, a USB-A plug adapter, a USB-A female coupler and a USB-C adapter into
the Mac mini. With that chain the frame started, and `adb` on the Mac mini (platform-tools 37.0.1
from Homebrew, `/opt/homebrew/bin/adb`) listed it as `device` with no authorization prompt;
`getprop ro.product.model` returned `DP101`, `ro.board.platform` returned `ceres` and `id` returned
`uid=0(root)`. The cause of the first failure was not determined: the chain was tried once after it,
and it is not known which part of it mattered, or whether power, the cable or the port was the
difference. In this setup `system_profiler SPUSBDataType` showed no matching entry for
`1f3a`, `DP101`, `Allwinner` or `Android`, even though `adb` detected the device, so it was not a
reliable way to verify this connection. Other reports in this repo use Apple-silicon Macs over USB.

On every boot Home HQ showed "The frame isn't on Wi-Fi" for a few seconds, then the dashboard
loaded. It is the same offline screen as in step 6 above, which lasted about a minute on the first
unit; the owner's reading is that the frame's network stack is slow to come up.

| Field | Value seen on the second unit |
| --- | --- |
| USB ID | `1f3a:1007` (`1f3a` is Allwinner's USB vendor ID), product name `DP101` |
| `ro.build.display.id` | `DP101_Frameo_V02_26061607` (same as above) |
| `ro.board.platform` | `ceres` |
| `ro.product.cpu.abilist` | `armeabi-v7a,armeabi` (32-bit only) |
| Android | 10 (SDK 29) |
| `adb shell` user | `uid=0` straight away, no `su` needed |
| WebView | `com.android.webview` 113.0.5672.136, a system app in `/product/app/webview/webview.apk` |
| Google services | no package matching `vending` or `gms` |

`set-home-activity` printed `Failed to set default home` when it ran right after
`am start -n com.wesbos.homehq/.MainActivity --ez home true`. Running it again a moment later printed
`Success`, and `resolve-activity` then returned `com.wesbos.homehq/.Home`.

### CSS compatibility issues in this WebView

A dashboard built with Next.js 16 and Tailwind 4 (a separate project, not this repo's `dashboard/`)
looked wrong on this frame while it looked right in desktop Chrome: a blur toggle did nothing, text
inputs were white and table header buttons were light grey. The kiosk was opened with debugging on
and the page was inspected over the Chrome DevTools protocol:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez debug true
adb shell "cat /proc/net/unix | grep devtools_remote"        # shows webview_devtools_remote_<pid>
adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>
curl -s localhost:9222/json                                  # page list with webSocketDebuggerUrl
```

Measured on the frame with `Runtime.evaluate` (nothing was clicked or changed):

| Declaration | Result |
| --- | --- |
| `background-color: #0000`, `#00000000` or `#f008` | rejected, `CSS.supports('background-color', '#0000')` is `false` |
| `background-color: transparent`, `rgba(0,0,0,0)`, `#f00` | works |
| `filter: blur(12px)` | works |
| `--tw-blur: blur(12px); filter: var(--tw-blur)` | works |
| `--tw-blur: blur(12px); filter: var(--tw-blur,)` | computed `filter` is `none` |
| `--qq: blur(12px); filter: var(--qq,)` (not registered with `@property`) | works |

Tailwind 4 registers its `--tw-*` variables with `@property` and writes utilities such as
`blur-md` as `filter: var(--tw-blur,)var(--tw-brightness,)…`, so those utilities did nothing here.
Its minifier also turned `transparent` into `#0000`, which the WebView rejected: that is why
`bg-transparent` and the `button, input` reset fell back to the browser's white and grey. The
same stylesheet had 91 hex colours with an alpha channel, including shadow and border colours such
as `#0000001a`.

What fixed it, in that project:

- `"browserslist": ["chrome >= 61"]` in `package.json`. The minifier then writes `rgba()` and
  `transparent`; the built CSS had 0 hex colours with alpha afterwards (it grew about 11%). On the
  frame, inputs and header buttons were transparent again and the shadows showed. This is the same
  approach as `cssTarget: 'chrome61'` in `dashboard/vite.config.js`. The workaround was verified on
  one device running Android 10 with WebView 113.
- For the blur, a literal value without variables, such as Tailwind's `[filter:blur(12px)]`, worked
  before the browserslist change.
- `color-mix(in oklab, …)` gradients, which Tailwind 4 also emits, rendered correctly on this
  WebView.

## Guesses

- `ceres` is probably an Allwinner Android 10 platform name. The second unit's USB vendor ID `1f3a`
  points to Allwinner, but the SoC model was not read from `/proc/cpuinfo` on either unit.
- Why `var(--x,)` fails only for `@property`-registered variables: probably a WebView 113 bug with an
  empty fallback on a registered property. Not investigated; the table above is only what was
  measured.
- Why `set-home-activity` failed the first time: probably the `.Home` alias had not been enabled yet
  when the command ran. Not checked.
- Why density 190 clipped the page: the WebView lays out in CSS pixels of 160/190 device pixels,
  so a 1280×800 screen becomes about 1078×674 CSS pixels, and a page built for 1280×800 does not
  fit. Not measured on the device.
- The Frameo boot logo is in the firmware's boot image; changing it was not attempted.
