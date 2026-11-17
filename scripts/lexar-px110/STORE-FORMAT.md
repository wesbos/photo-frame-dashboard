# The rescue store in `cache`: what `rescue.sh` reads

Our recovery (`recovery-rescue.img`) runs `/system/bin/rescue.sh` once at start. The script mounts the
`cache` partition (plain ext4, 110.5 MB) at a directory of its own, `/tmp/rescue_cache`, and looks in one
folder there, `rescue/`. It never mounts, unmounts or touches `/cache` itself, because the stock recovery
program mounts and unmounts `/cache` on its own. From Android the same files are seen under `/cache/`, which
is how the paths are written below. The script itself is `src/recovery/rescue.sh`; this file describes
what it expects to find.

## The script acts only on our own note

Before anything else the script reads the note in `para` (the bootloader message at offset 0) and compares it
byte for byte. It goes on only when the command is `boot-recovery` **and** the arguments are ours:

| arguments (768 bytes at offset 64, zero-padded) | what the script does |
|---|---|
| empty, or exactly `recovery\n` | the full work described below: the ladder, or an at-once restore (see "The escalation ladder") |
| exactly `recovery\n--just_exit\n` | no list, no stopping, no clearing: the stock program restarts the frame. See "With `--just_exit`" |
| anything else (`--wipe_data`, `--prompt_and_wipe_data`, `--update_package`, `--sideload`, ...) | **nothing** |

With any other command (`boot-fastboot`, none) it also does nothing. "Nothing" means: `cache` is not mounted, no
partition and no byte of `para` is written, the stock program is not stopped, no restart is asked for. The only
trace is a log and a marker in `/tmp`, which are gone after the restart. The reason: a factory reset from
Android puts `--wipe_data` in the note, and the stock program then formats `data` and `cache`; interfering
with that, or holding `cache` mounted while it is formatted, would do damage.

## Files

| path (as seen from Android) | what it is |
|---|---|
| `/cache/rescue/list` | the list: which partitions to check, the hash each should have, and its known-good copy |
| `/cache/rescue/<name>.gz` | a gzip'd known-good copy of one partition (any plain file name; the list names it) |
| `/cache/rescue/stay` | optional. Holds a number of seconds, 1 to 3600; empty or anything else means 600. The recovery stays up that long after its work, then clears the note and restarts as usual |
| `/cache/rescue/rung` | the ladder counter, one number, written by the script and removed by Android. See "The escalation ladder" |
| `/cache/rescue/safe` | the safe-start flag, written by the script at rung 2 with the single word `ladder` (and a newline) in it. Android's start-up looks for it. See "The escalation ladder" |
| `/cache/rescue/attempts` | written by the script: the retry counter, one number. See "A restore that is cut off" below |
| `/cache/rescue.log` | written by the script: what it found and did, one line per event, appended on every run (moved to `rescue.log.old` when over 256 KB) |
| `/cache/rescue.marker` | written by the script: a seven-line record of the latest run (time, the note it found, list accepted/refused/none, what was restored, what was wrong but not restored, how far it got). Rewritten at each stage, so it exists even if the run is cut off |

## The list

Plain text, Unix line ends, fields separated by spaces.

```
rescue-list 1
<name> <expected sha256> <copy file> <sha256 of the copy file> <sha256 of the unpacked copy>
...
end
```

- First line exactly `rescue-list 1`. Last line exactly `end`. A list with no `end` (cut short while being
  written) is refused whole.
- Blank lines and lines starting with `#` are ignored.
- `<name>` must be one of the five names below, each at most once. Any other name and the **whole list is
  refused**: nothing is written.
- Hashes are 64 lowercase hex digits.
- `<copy file>` is a plain file name inside `/cache/rescue/` (letters, digits, `.`, `-`, `_`; no `/`, no leading dot).
- Any malformed line and the whole list is refused.
- An optional line that is exactly `guarded`, once, between the first line and `end`, marks a list armed for a flash we are
  checking: see "The escalation ladder". It is not an entry.

### The five names (the allow-list, fixed inside the script)

| name | what is checked and, if needed, written | length in bytes |
|---|---|---|
| `product` | the `product` region of `super`: 4096-byte blocks 32512 to 59321 (byte offset 133,169,152) | 109,813,760 |
| `vbmeta_system` | the whole `vbmeta_system` partition | 4,194,304 |
| `vbmeta` | the whole `vbmeta` partition | 4,194,304 |
| `logo` | the whole `logo` partition | 8,388,608 |
| `boot` | the whole `boot` partition | 33,554,432 |

The list cannot give a device, an offset or a length; those are fixed in the script. The preloader, `lk`, `lk2`,
`seccfg`, `tee1`, `tee2`, `md_udc`, `frp`, `recovery`, `para` and everything else can never be written by it.

The `product` offset is where `product` sits in `super` today (one extent). If the layout of `super` is ever
changed, the script and this table must be changed with it.

## What the script does with each line

1. Reads the region and takes its SHA-256. If it cannot read all of it, it leaves the partition alone.
2. If the hash equals `<expected sha256>`: nothing to do.
3. If not, and the hash already equals `<sha256 of the unpacked copy>`: nothing to write.
4. Otherwise it checks the copy three ways: the hash of the `.gz` file, the hash of the unpacked data, and the
   unpacked length (must be exactly the length in the table). Any of the three wrong, or the file missing: the
   partition is **not written**, and that is logged.
5. Only then it writes the unpacked copy to the region, reads the region back and compares it with
   `<sha256 of the unpacked copy>`. If the read-back is wrong it tries once more, then logs a failure.

Two ways to use the expected hash:

- **"Put it back unless it is already good":** expected hash = the known-good hash. Whatever else is on the
  partition is replaced by the copy.
- **"Check that the flash landed":** expected hash = the hash of the new image just flashed. If the partition
  holds exactly the new image it is left alone; if the write was cut short or went wrong, the known-good copy goes back.

## After the list

- With `/cache/rescue/stay`: the script stops the stock recovery program (so that it cannot restart the frame),
  waits the number of seconds in the file, and then carries on with the next point. A stay always ends.
- The script clears the note, then restarts. Clearing means zeroing the first 2048 bytes of `para` (the
  bootloader message) while the note is still ours; nothing else in `para` is written. It then waits two
  seconds and looks again, up to five times, because the stock recovery program writes the note back once when
  it starts. If the note is still there after that, the script does not restart, so the frame cannot loop.
- A refused list or no list (in a restore that is allowed to run, see the ladder): nothing is restored; the note
  is cleared and the frame restarts as above.
- `cache` not mountable (five tries, a second apart) or not writable, with our plain note and no way to count: see
  "The escalation ladder": the script stays.

## The stock recovery program runs beside the script

The stock `recovery` program is unchanged and starts as it always did. Without `--just_exit` it waits for a key
the frame does not have, and restarts the frame after about two minutes if USB is unplugged. So as soon as the
script has accepted a list (or found a `stay` file) it stops that program (`stop recovery`), does its work,
clears the note itself and restarts. As seen on the frame, the stock program clears the note
about a second after it starts, before the script's work begins. The script judges whose note it was from a
copy init takes before the stock program starts (`rescue.sh snapshot`, kept in `/tmp/rescue.note`).

## A restore that is cut off is taken up again, at most three times

Because the stock program has already cleared the note, a restore cut off by a power loss would otherwise not
be resumed: the next power-on would start Android with a half-written partition. So, once per run and
**immediately before its first partition write**, the script:

1. reads the counter file `/cache/rescue/attempts` (one number; missing, empty or not a number counts as 0;
   3 or more, or anything longer than two digits, means "give up");
2. if the counter is below 3, raises it by one and syncs;
3. puts our own plain note back into `para`: the first 2048 bytes become `boot-recovery` and zeros. Nothing
   else in `para` is written. It then reads the note back.

Only if all of that worked does it write a partition. If the counter is already 3 or more, cannot be written,
the note in `para` is somebody else's, or the note does not read back as ours, **no partition is written in
that run**; the partitions that are wrong are logged and named in the marker as "wrong but not restored", and
the script then stays in recovery with the note armed (it does not restart while a listed partition is wrong; see the ladder section).

If the run is cut off after that, `para` still holds our note, so the next power-on starts recovery and the
list is worked through again. At the end of a run in which nothing is left wrong, the counter file is removed.
A run that needs no write never touches the counter (it sets our note at the start, as the ladder section says, and clears it at the end).

**When making a new store, do not copy an old `attempts` file into it, and remove one that is there:** a
counter left at 3 from an earlier failure blocks every restore until it is removed.

## The escalation ladder (Android arms the note at every start)

Android's start-up arms our plain note in `para` at every start and clears it once Android has been healthy. So
recovery is entered with our plain note only when a start did not get that far. When the script finds our plain
note (not `--just_exit`, which is handled as described further down) it first decides which of three modes it is in:

| mode | when | what happens |
|---|---|---|
| manual | `/cache/rescue/stay` exists, **or** the list holds a line `guarded` | the old behaviour: the list is checked and restored at once, the optional stay is waited, the note is cleared, restart. `rung` is neither read nor written |
| resume | `attempts` holds 1 or 2 and a list exists | a restore was cut off: it is finished at once. `rung` is neither read nor written. It ends with the note cleared and a restart (or, if something listed is still wrong, a stay with the note armed), and if it wrote nothing in its run (whatever the reason, a refused list included) it removes `attempts`, so the next entry is a rung |
| ladder | everything else | first the list is checked and anything wrong is put back (the restore described above, with all its protections), then the counter `rung` decides |

**The note is set again at the start.** For every mode of our plain note (after the foreign-note and `recovery/command`
checks) the script waits for the stock program to clear the note (up to 10 s), then sets our plain note again
(`attempts` is not touched). So a power cut while mounting, hashing the 110 MB of `product` or restoring comes back to
recovery. Every normal end clears it again; the stays below say what they do. If another program's note appears in
`para` in the meantime, the run is not ours any more: nothing is done.

**Never restart while a listed partition is still wrong** (bad copy, restores given up at `attempts` 3, a write that did
not read back). A restart with the note cleared and a bad verified partition would be Red State for ever. In that case
whatever the mode, the script stays in recovery with our plain note **armed**: the frame is reachable over adb, and a
power cycle comes back to recovery.

The ladder counter is the file `/cache/rescue/rung`: one number, one line. Missing, empty or not a number counts
as 0; `3` or more (or anything longer than two digits) counts as 3. On entry the script raises it by one (below 3),
syncs and reads it back **before it does anything else**, so a power cut cannot reset the count. Then it does the
restore step, then acts on the new value:

| new value | what the script does after the restore step |
|---|---|
| 1 | restart, **note cleared** (if a listed partition is still wrong: stay, note armed) |
| 2 | writes `/cache/rescue/safe` containing `ladder`, then restart, **note cleared** (if a listed partition is still wrong: stay, note armed, no `safe`) |
| 3 or more | **stays**: stops the stock recovery program, no restart, nothing more written; logged in `rescue.log` and the marker. The recovery's own adbd (root, in the recovery domain) is up for adb. If nothing listed is wrong the note is **cleared**, so a power cycle starts Android; if something is still wrong it stays **armed**. The counter is left at 3 |

**Every restart from the ladder is unarmed.** LK goes to recovery whenever our note is in `para`, so an armed
restart would send the frame straight back here and Android would never get its next try or safe mode. Android arms
the note itself at its next start and clears it when healthy. A run that restored something still counts as a rung.
A failure that is a verified image is handled by the restore step at the first entry; the rungs are for Android that
fails with all partitions good, or keeps failing after a restore.

Which paths clear the note and which leave it armed:

| path | at the end |
|---|---|
| ladder rungs 1 and 2, nothing listed wrong | restart, note **cleared** |
| ladder rung 3 and above, nothing listed wrong | stay, note **cleared** |
| resume, nothing listed wrong | restart, note **cleared**. Any resume that wrote nothing in its run (list refused or damaged, a bad copy, nothing left to write) removes `attempts`, so the next entry is a rung of the ladder; resume can never repeat for ever |
| manual (`stay` file or `guarded` list), nothing listed wrong | note **cleared**, restart (a flash armed on purpose; the restore is verified first) |
| any of the above with a listed partition still wrong | stay, note **armed**, no restart |
| manual (`guarded` list) with a refused list | stay, note **armed**, no restart (the list cannot vouch for the flash in progress) |
| cache cannot be mounted | stay, note **armed** (set at the start): a power cycle comes back here |
| the counter cannot be written (cache full or read-only) | the restore step still runs; nothing listed wrong: stay with the note **cleared**, so a power cycle starts Android, which can free space; something still wrong: stay, note **armed** |
| `--just_exit` after its 120 s | note cleared, restart |
| foreign notes, or a non-empty `recovery/command` | nothing |

If the store's counter already holds 3 or more the script does the restore step and stays, without writing the
counter. If `cache` cannot be mounted, or the counter cannot be written and read back (read-only or full), the
ladder cannot count and the script stays (a loop of restarts that never escalates would be worse); what it does
with the note is in the table above. It never
restarts without having cleared the note.

**A pending command in `cache`.** With our plain note the stock program also reads `/cache/recovery/command` (an OTA
package, a wipe, ...). In every mode of a plain note (not `--just_exit`), if that file exists and is not empty the
script treats the run as not ours: nothing written, no counter changed, no restart, the stock program left running.
An empty file does not count.

Still unchanged: the script acts only on our own plain note; any other note (`--wipe_data`,
`--prompt_and_wipe_data`, `--update_package`, `--sideload`, `boot-fastboot`, ...) means nothing at all, whatever is
in the store; only the five allow-listed regions; no copy is written unless its hashes are right.

### What Android must do (the boot script in `/data` and the `boot` wrapper match this exactly)

- **At every start, arm the note:** write `boot-recovery` (13 bytes, then zeros) over the first 2048 bytes of `para`,
  only if `para` holds nothing else (all zero, or already our plain note).
- **When Android has been healthy** (kiosk accepted, stayed up the agreed time), the "all clear" is, in this order:
  1. remove `/cache/rescue/rung` (and `/cache/rescue/attempts`, a leftover count of restore tries);
  2. zero the first 2048 bytes of `para`.

  In that order, because a cut-off between the two then leaves a note and no counter (harmless: the next entry is
  rung 1) and not the reverse. Android does **not** remove `safe` in the all clear.
- **`/cache/rescue/safe`:** if it exists at start-up, Android starts in safe mode: adb over USB plus the private tailnet, the
  firewall, and no kiosk. The start-up animation's bind mount lives in the product image's own init, so it still
  happens in safe mode (harmless). Recovery only checks that the file exists and never removes it.
  - **Contents rule:** the ladder writes the single word `ladder`. Android treats `ladder` as "may end safe mode by
    itself after 30 minutes and reboot once". Anything else (for example `manual`, written by `frame-doctor.sh safe on`)
    stays until it is removed by hand.
  - A safe-mode start must not do the all clear above, or the ladder could never climb past a start that is broken
    only in the part safe mode skips.
- A guarded flash from Android's side: write the list with the `guarded` line, then arm the note.

## With `--just_exit`

Started with the note `boot-recovery` and the arguments `recovery\n--just_exit\n`, the stock program clears
the note and restarts the frame by itself within seconds, whether or not the script got anywhere. That is the
safe way to start our recovery the first time.

The script **refuses to use a list** in this case, and says so in its log and marker. The order of events shows
why: the stock program reads the note, clears it and asks for the restart within a few seconds of starting,
while the script would at that moment be somewhere between "list accepted" and its first write. Stopping the
stock program then comes too late (the restart is already under way), the script would be killed while reading
or, worse, in the middle of a write, and because the note is already cleared there would be no second run to
finish the job. So with `--just_exit` the script only mounts its directory, writes its log and marker, and
waits. Only if the frame is still up after 120 seconds (the stock program did not do its part) does the script
clear the note and restart the frame itself.

The script syncs after every log line and every write, and its log is on `cache` from the moment `cache` is mounted.

## Making a store by hand (`frame-doctor.sh store` does this for you)

```
gzip -6 -n -c vbmeta.img > vbmeta.gz
shasum -a 256 vbmeta.img vbmeta.gz
```

Then a list line is: `vbmeta <expected> vbmeta.gz <hash of vbmeta.gz> <hash of vbmeta.img>`.
For `product`, the image is the 109,813,760-byte `product.img` (`BUILD_DIR/work/stock/product.img` is the stock one).
Copying the store onto the frame is a write to the frame and needs the owner's yes like any other.

## Does a full known-good set fit in `cache`?

Measured with gzip level 6 (level 9 saves under 0.2%):

| known-good copy | raw bytes | gzip'd bytes |
|---|---|---|
| `product`, stock | 109,813,760 | 63,185,101 |
| `product`, ours (`BUILD_DIR/out`, with our kiosk; yours will differ a little) | 109,813,760 | 63,199,949 |
| `boot`, stock | 33,554,432 | 8,332,401 |
| `logo`, stock | 8,388,608 | 1,427,360 |
| `vbmeta`, stock | 4,194,304 | 7,216 |
| `vbmeta_system`, stock | 4,194,304 | 5,603 |

One full set (one `product` + `boot` + `logo` + both vbmeta) is **72,957,681 bytes, about 73.0 MB**. In the
backup `cache` had 26,322 free 4096-byte blocks, **107.8 MB** free. So one full set fits with about
**34.9 MB (32%) to spare**. Two `product` versions at once (about 136 MB with the rest) do **not** fit: the
store can hold one known-good `product`, not a choice of two. Free space on the frame must be re-read before a
store is written, because Android also uses `cache`.
