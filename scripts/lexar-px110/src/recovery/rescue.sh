#!/system/bin/sh
# rescue.sh: automatic restore, run once by init when our recovery starts.
#
# What it does, in order:
#   1. Reads the note in `para`. It goes on ONLY when the note is ours: command "boot-recovery" with
#      no arguments, "recovery\n", or "recovery\n--just_exit\n", compared byte for byte. Any other
#      note (a factory reset's --wipe_data, an update, sideload, boot-fastboot, no note at all) belongs
#      to the stock recovery program: the script then mounts nothing, stops nothing, writes nothing
#      to any partition and does not restart. It only leaves a log and marker in /tmp.
#   2. Mounts the cache partition at its own directory, /tmp/rescue_cache, never at /cache (the
#      stock program mounts and unmounts /cache itself). Store, log and marker live there
#      (format: patch/out-recovery/STORE-FORMAT.md).
#   3. With --just_exit: touches no list. The stock program clears the note and restarts the frame
#      within seconds. Only if the frame is still up after two minutes does the script clear the
#      note and restart it itself.
#   4. Otherwise one of three modes, by what the store (cache/rescue/) says:
#        manual  a `stay` file, or a line `guarded` in the list: a flash armed on purpose. Restore at once.
#        resume  a restore was cut off earlier (`attempts` is 1 or 2) and a list is there: finish it at once.
#        ladder  our plain note and nothing saying otherwise (the always-armed note of every start). First
#                the list is checked and anything wrong put back (the restore below). Then the counter `rung`,
#                raised by one on each entry (Android removes it once it has been healthy): rung 1 restart,
#                rung 2 write `safe` and restart, rung 3 and above stay (no restart). Every restart from the
#                ladder CLEARS the note: Android arms it again itself at its next start, and an armed note would
#                send LK straight back here. If the counter cannot be read and written (cache not mountable or
#                not writable): stay. Before the first write of any mode our plain note is set again (a power cut
#                during the hashing must come back here), and the script never restarts while a listed partition
#                is still wrong: it stays in recovery with the note armed.
#      The restore: checks every line of the list first (one bad line refuses the whole list), stops the
#      stock program so it cannot restart the frame in mid-restore, and just before its first partition
#      write puts our own note back into `para` so that a restore cut off by a power loss is taken up
#      again at the next start; a counter (`attempts`) stops that after three tries.
#   5. For each listed partition: reads it and compares its SHA-256 with the expected one. On a
#      mismatch it checks the known-good copy three ways (hash of the .gz file, hash of the unpacked
#      data, unpacked length) and only then writes it, reads it back and compares again.
#   6. If the store has a file `stay` (manual mode): stops the stock program and waits the number of
#      seconds in that file (1 to 3600; anything else means 600). Then goes on to 7.
#   7. Clears the note (the 2048-byte bootloader message at offset 0 of `para`, nothing else) and
#      restarts. If the note cannot be cleared it does not restart, so the frame cannot loop.
#
# It may be cut off at any moment, so every log line and every write is followed by sync, and the
# marker file is rewritten at each stage so a run can be proven afterwards.
#
# Rules it keeps:
#   - It writes only the five regions in target() below, at fixed places and fixed lengths. The list
#     can choose among them but cannot name a device, an offset or a length.
#   - When anything is unclear it writes nothing.
#   - It uses only programs that are in the recovery ramdisk (test 14 checks this).
#
# Every path can be replaced through the environment so the tests can run this very file on the
# Mac against stand-in files. On the frame none of these variables is set.

BYNAME=${RESCUE_BYNAME:-/dev/block/platform/soc/11120000.mmc/by-name}
CACHE_DEV=${RESCUE_CACHE_DEV:-$BYNAME/cache}
MNT=${RESCUE_MNT:-/tmp/rescue_cache}
STORE=${RESCUE_STORE:-$MNT/rescue}
PARA=${RESCUE_PARA:-$BYNAME/para}
ZERO=${RESCUE_ZERO:-/dev/zero}
REBOOT=${RESCUE_REBOOT:-reboot}
DO_MOUNT=${RESCUE_MOUNT:-1}
WAIT=${RESCUE_WAIT:-30}
TMPLOG=${RESCUE_TMPLOG:-/tmp/rescue.log}
TMPMARK=${RESCUE_TMPMARK:-/tmp/rescue.marker}
STEP=${RESCUE_STAY_STEP:-10}
JUST_EXIT_WAIT=${RESCUE_JUST_EXIT_WAIT:-120}

LOGFILE=$TMPLOG
MARKFILE=$TMPMARK
# SHA-256 of the note's fields when the note is ours (fields are zero-padded to their full length).
CMD_RECOVERY=a55ab01c3d57d5baa0448714682e84b69f7f605fb4f89cfb0cf7124cab3b5a3c
CMD_NONE=66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925
ARGS_EMPTY=ef115a0e0c15cdc41958ca46b5b14b456115f4baec5e3ca68599d2a8f435e3b8
ARGS_PLAIN=a5a38f0379f624904d3b16f8454afe96ad503a0b31f3ababa19035d9ccb39fc4
ARGS_JUST_EXIT=8f588da41115667267254d29afdbeaf88636608035f85d279c4e5391140e5d98
MAX_ENTRIES=8
EMPTY_SHA=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

KMSG=${RESCUE_KMSG:-/dev/kmsg}
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOGFILE"
    # Also into the kernel log: Android keeps the last start's kernel log (/sys/fs/pstore/console-ramoops),
    # so a run can be read afterwards even when nothing could be written to cache.
    [ -c "$KMSG" ] && echo "rescue.sh: $*" > "$KMSG"
    sync
}

# Rewrite the marker file: a short record of this run, readable later from Android.
NOTE_AT_START=unknown
LIST_STATE=none
RESTORED=
NOT_RESTORED=
marker() {
    {
        echo "rescue.sh run"
        echo "time: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "note at start: $NOTE_AT_START"
        echo "list: $LIST_STATE"
        echo "restored:${RESTORED:- none}"
        echo "wrong but not restored:${NOT_RESTORED:- none}"
        echo "state: $1"
    } > "$MARKFILE"
    sync
}

# The allow-list. Sets DEV, SKIP and COUNT (both in 4096-byte blocks) for a name, or fails.
#   product        the product region inside super: 109,813,760 bytes at byte 133,169,152
#   vbmeta_system  whole partition, 4 MiB
#   vbmeta         whole partition, 4 MiB
#   logo           whole partition, 8 MiB
#   boot           whole partition, 32 MiB
# Never here: preloader, lk, lk2, seccfg, tee1, tee2, md_udc, frp, recovery, para, or anything else.
target() {
    case "$1" in
        product)       DEV=$BYNAME/super;         SKIP=32512; COUNT=26810 ;;
        vbmeta_system) DEV=$BYNAME/vbmeta_system; SKIP=0;     COUNT=1024 ;;
        vbmeta)        DEV=$BYNAME/vbmeta;        SKIP=0;     COUNT=1024 ;;
        logo)          DEV=$BYNAME/logo;          SKIP=0;     COUNT=2048 ;;
        boot)          DEV=$BYNAME/boot;          SKIP=0;     COUNT=8192 ;;
        *)             return 1 ;;
    esac
    return 0
}

# True when $1 is exactly 64 lowercase hex digits.
is_sha() {
    case "$1" in
        *[!0-9a-f]*) return 1 ;;
    esac
    [ ${#1} -eq 64 ]
}

# True when $1 is a plain file name: letters, digits, dot, dash, underscore; no path, no leading dot.
is_plain_name() {
    case "$1" in
        ""|.*|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
    return 0
}

# First word of a sha256sum output line.
first_word() {
    echo "$1"
}

sha_of_file() {
    first_word $(sha256sum < "$1")
}

sha_of_region() {
    first_word $(dd if="$DEV" bs=4096 skip="$SKIP" count="$COUNT" 2>/dev/null | sha256sum)
}

bytes_of_region() {
    echo $(($(dd if="$DEV" bs=4096 skip="$SKIP" count="$COUNT" 2>/dev/null | wc -c)))
}

# Pass 1: the whole list must be well formed, or nothing in it is used.
#   line 1:   rescue-list 1
#   entries:  <name> <expected sha256> <copy file> <sha256 of copy file> <sha256 of unpacked copy>
#   last:     end
check_list() {
    state=head
    count=0
    seen=" "
    seen_guarded=no
    while read -r f1 f2 f3 f4 f5 f6 || [ -n "$f1" ]; do
        case "$f1" in
            ""|"#"*) continue ;;
        esac
        if [ "$state" = head ]; then
            if [ "$f1" != rescue-list ] || [ "$f2" != 1 ] || [ -n "$f3" ]; then
                log "list refused: first line is not 'rescue-list 1'"
                return 1
            fi
            state=body
            continue
        fi
        if [ "$state" = done ]; then
            log "list refused: text after 'end'"
            return 1
        fi
        if [ "$f1" = end ] && [ -z "$f2" ]; then
            state=done
            continue
        fi
        if [ "$f1" = guarded ]; then
            if [ -n "$f2" ] || [ "$seen_guarded" = yes ]; then
                log "list refused: 'guarded' must stand alone on its line, once"
                return 1
            fi
            seen_guarded=yes
            continue
        fi
        if ! target "$f1"; then
            log "list refused: '$f1' is not on the allow-list"
            return 1
        fi
        case "$seen" in
            *" $f1 "*) log "list refused: '$f1' is listed twice"; return 1 ;;
        esac
        seen="$seen$f1 "
        if [ -n "$f6" ] || ! is_sha "$f2" || ! is_plain_name "$f3" || ! is_sha "$f4" || ! is_sha "$f5"; then
            log "list refused: malformed line for '$f1'"
            return 1
        fi
        count=$((count + 1))
        if [ "$count" -gt "$MAX_ENTRIES" ]; then
            log "list refused: too many entries"
            return 1
        fi
    done < "$STORE/list"
    if [ "$state" != done ]; then
        log "list refused: no 'end' line (cut short?)"
        return 1
    fi
    return 0
}

# Check one partition and restore it if, and only if, everything about the copy is right.
do_entry() {
    name=$1; want=$2; file=$3; gzsha=$4; goodsha=$5
    target "$name" || return 0
    size=$((COUNT * 4096))
    if [ ! -e "$DEV" ]; then
        log "$name: device $DEV is missing; not touched"
        return 0
    fi
    got=$(bytes_of_region)
    if [ "$got" -ne "$size" ]; then
        log "$name: could read only $got of $size bytes; not touched"
        return 0
    fi
    cur=$(sha_of_region)
    if ! is_sha "$cur" || [ "$cur" = "$EMPTY_SHA" ]; then
        log "$name: could not hash the partition; not touched"
        return 0
    fi
    if [ "$cur" = "$want" ]; then
        log "$name: matches the expected hash; nothing to do"
        return 0
    fi
    log "$name: MISMATCH, has $cur, expected $want"
    if [ "$cur" = "$goodsha" ]; then
        log "$name: already equal to the known-good copy; nothing to write"
        return 0
    fi
    NOT_RESTORED="$NOT_RESTORED $name"
    copy=$STORE/$file
    if [ ! -f "$copy" ]; then
        log "$name: known-good copy $file is missing; NOT restored"
        return 0
    fi
    if [ "$(sha_of_file "$copy")" != "$gzsha" ]; then
        log "$name: known-good copy $file is corrupt (file hash differs); NOT restored"
        return 0
    fi
    if [ "$(first_word $(gunzip -c "$copy" 2>/dev/null | sha256sum))" != "$goodsha" ]; then
        log "$name: known-good copy $file is corrupt (unpacked hash differs); NOT restored"
        return 0
    fi
    if [ "$(($(gunzip -c "$copy" 2>/dev/null | wc -c)))" -ne "$size" ]; then
        log "$name: known-good copy $file has the wrong length; NOT restored"
        return 0
    fi
    if ! arm_note; then
        log "$name: NOT restored (no partition is written in this run)"
        return 0
    fi
    try=1
    while [ "$try" -le 2 ]; do
        log "$name: writing known-good copy $file ($size bytes), try $try"
        gunzip -c "$copy" | dd of="$DEV" bs=4096 seek="$SKIP" conv=notrunc 2>/dev/null
        sync
        now=$(sha_of_region)
        if [ "$now" = "$goodsha" ]; then
            log "$name: RESTORED, read back and matches the known-good hash"
            RESTORED="$RESTORED $name"
            NOT_RESTORED=${NOT_RESTORED% $name}
            return 0
        fi
        log "$name: read-back after writing is $now, not the known-good hash"
        try=$((try + 1))
    done
    log "$name: RESTORE FAILED after 2 tries"
    return 0
}

# Pass 2: act on a list that passed check_list.
do_list() {
    while read -r f1 f2 f3 f4 f5 f6 || [ -n "$f1" ]; do
        case "$f1" in
            ""|"#"*|rescue-list|end) continue ;;
        esac
        do_entry "$f1" "$f2" "$f3" "$f4" "$f5"
    done < "$STORE/list"
}

# The note is the bootloader message at offset 0 of `para`: command (32 bytes), status (32),
# recovery arguments (768, at offset 64), stage (32), the rest of the first 2048 bytes reserved;
# all zero when idle. The ENV_v1 data sits at 0x20000..0x23FFF of `para`, far from them.
#
# note_kind prints one word:
#   plain      command boot-recovery, arguments empty or exactly "recovery\n"            (ours)
#   just_exit  command boot-recovery, arguments exactly "recovery\n--just_exit\n"       (ours)
#   none       command field all zero
#   foreign    anything else, or `para` unreadable: not ours, hands off
note_kind() {
    src=${1:-$PARA}
    if [ ! -e "$src" ]; then
        echo foreign
        return 0
    fi
    cmd=$(first_word $(dd if="$src" bs=32 count=1 2>/dev/null | sha256sum))
    args=$(first_word $(dd if="$src" bs=64 skip=1 count=12 2>/dev/null | sha256sum))
    if [ "$cmd" = "$CMD_NONE" ]; then
        echo none
    elif [ "$cmd" != "$CMD_RECOVERY" ]; then
        echo foreign
    elif [ "$args" = "$ARGS_EMPTY" ] || [ "$args" = "$ARGS_PLAIN" ]; then
        echo plain
    elif [ "$args" = "$ARGS_JUST_EXIT" ]; then
        echo just_exit
    else
        echo foreign
    fi
}

# Clearing means zeroing exactly the first 2048 bytes of `para`. It is done only while the note is
# still ours. The stock recovery program writes the note back once when it starts, so after
# clearing the script waits, looks again, and clears again if needed.
clear_note() {
    tries=0
    while [ "$tries" -lt 5 ]; do
        case "$(note_kind)" in
            none) log "start-recovery note cleared"; return 0 ;;
            plain|just_exit) ;;
            *) log "the note in para is no longer ours; not clearing it"; return 1 ;;
        esac
        dd if="$ZERO" of="$PARA" bs=2048 count=1 conv=notrunc 2>/dev/null
        sync
        sleep 2
        tries=$((tries + 1))
    done
    if [ "$(note_kind)" = none ]; then
        log "start-recovery note cleared"
        return 0
    fi
    log "the note is still in para after clearing 5 times"
    return 1
}

# The retry counter: one number in the store, file `attempts`. It counts the runs that started
# writing. Missing, empty or not a number counts as 0; 3 or more (or anything longer) means give up.
read_attempts() {
    c=
    rest=
    [ -f "$STORE/attempts" ] && read -r c rest < "$STORE/attempts"
    [ -n "$rest" ] && c=
    case "$c" in
        ""|*[!0-9]*) ATTEMPTS=0 ;;
        0|00)        ATTEMPTS=0 ;;
        1|01)        ATTEMPTS=1 ;;
        2|02)        ATTEMPTS=2 ;;
        *)           ATTEMPTS=3 ;;
    esac
}

# Called once per run, just before the first partition write. The stock program cleared the note
# when it started, so a restore cut off by a power loss would not be taken up again. This puts our
# own plain note back first: the first 2048 bytes of `para` become "boot-recovery" and zeros,
# nothing else in `para` is written. It succeeds only if the counter allows another try, the
# counter could be raised, the note in `para` is ours or empty now, and the note reads back as
# ours. Otherwise no partition is written in this run.
ARMED=
ATTEMPTS=0
arm_note() {
    [ "$ARMED" = yes ] && return 0
    [ "$ARMED" = no ] && return 1
    ARMED=no
    if [ "$ATTEMPTS" -ge 3 ]; then
        log "gave up after 3 tries: not setting the note again"
        return 1
    fi
    case "$(note_kind)" in
        none|plain) ;;
        *) log "the note in para is not ours and not empty: not setting ours over it"; return 1 ;;
    esac
    echo "$((ATTEMPTS + 1))" > "$STORE/attempts"
    sync
    was=$ATTEMPTS
    read_attempts
    if [ "$ATTEMPTS" -ne "$((was + 1))" ]; then
        log "could not record the try in the store: not setting the note"
        return 1
    fi
    dd if="$ZERO" of="$PARA" bs=2048 count=1 conv=notrunc 2>/dev/null
    printf boot-recovery | dd of="$PARA" bs=13 count=1 conv=notrunc 2>/dev/null
    sync
    if [ "$(note_kind)" != plain ]; then
        log "the note did not read back as ours after setting it"
        return 1
    fi
    ARMED=yes
    log "note set again in para (try $ATTEMPTS of 3) so that a cut-off restore is taken up at the next start"
    return 0
}

# True when the list has a line that is exactly `guarded`: the list says "this note was armed for a
# flash we are checking": restore at once, no ladder. (check_list judges the list as a whole later.)
list_guarded() {
    [ -f "$STORE/list" ] || return 1
    while read -r g1 g2 || [ -n "$g1" ]; do
        [ "$g1" = guarded ] && [ -z "$g2" ] && return 0
    done < "$STORE/list"
    return 1
}

# The ladder counter: one number in the store, file `rung`. It says how many times in a row recovery
# was entered by our plain note without Android having cleared it as healthy. Missing, empty or not
# a number counts as 0; 3 or more (or anything longer than two digits) counts as 3.
RUNG=0
read_rung() {
    c=
    rest=
    [ -f "$STORE/rung" ] && read -r c rest < "$STORE/rung"
    [ -n "$rest" ] && c=
    case "$c" in
        ""|*[!0-9]*) RUNG=0 ;;
        0|00)        RUNG=0 ;;
        1|01)        RUNG=1 ;;
        2|02)        RUNG=2 ;;
        *)           RUNG=3 ;;
    esac
}

# Record rung $1 and read it back. Fails if the store cannot be written.
write_rung() {
    mkdir -p "$STORE" 2>/dev/null
    echo "$1" > "$STORE/rung" 2>/dev/null
    sync
    read_rung
    [ "$RUNG" -eq "$1" ]
}

# Rung 3 and above: stay. The stock program is stopped so that it cannot restart the frame; nothing
# restarts it; the note is left as it is. adb (the ramdisk's own adbd, started by init) stays up.
stay_here() {
    log "$1: staying in recovery; no restart"
    stop recovery
    marker "staying in recovery (rung 3 or cannot count), no restart"
    exit 0
}

wait_for() {
    n=0
    while [ ! -e "$1" ] && [ "$n" -lt "$WAIT" ]; do
        sleep 1
        n=$((n + 1))
    done
    [ -e "$1" ]
}

# Sleep $1 seconds in steps of $STEP.
wait_seconds() {
    left=$1
    case "$STEP" in
        ""|0*|*[!0-9]*) STEP=10 ;;
    esac
    while [ "$left" -gt 0 ]; do
        s=$STEP
        [ "$left" -lt "$s" ] && s=$left
        sleep "$s"
        left=$((left - s))
    done
}

# Clear the note and restart. Without a cleared note there is no restart, so the frame cannot loop.
go_home() {
    if ! clear_note; then
        log "not restarting, so the frame cannot loop"
        marker "finished; note could not be cleared, no restart"
        exit 1
    fi
    log "restarting"
    marker "finished; restarting"
    if [ "$mounted" = 1 ]; then
        umount "$MNT"
    fi
    $REBOOT
    exit 0
}

# Put our own plain note into `para` (first 2048 bytes: "boot-recovery" and zeros, nothing else written)
# and read it back. Only over an empty note or our own plain note, never over anyone else's.
set_plain_note() {
    case "$(note_kind)" in
        none|plain) ;;
        *) log "the note in para is not ours and not empty: not setting ours over it"; return 1 ;;
    esac
    dd if="$ZERO" of="$PARA" bs=2048 count=1 conv=notrunc 2>/dev/null
    printf boot-recovery | dd of="$PARA" bs=13 count=1 conv=notrunc 2>/dev/null
    sync
    [ "$(note_kind)" = plain ] || return 1
    sleep 2
    [ "$(note_kind)" = plain ]
}

# Stay in recovery with our plain note ARMED. Used whenever a listed partition is still wrong at the end of
# a run (bad copy, restores given up, a write that did not read back): restarting with the note cleared and
# a bad verified partition would end in Red State for ever, whereas in recovery the frame is reachable over
# adb and a power cycle comes back here. Never restarts.
stay_armed() {
    stop recovery
    if set_plain_note; then
        log "$1: a listed partition is still wrong; staying in recovery with our plain note armed"
    else
        log "$1: a listed partition is still wrong and the note could not be set again; staying in recovery"
    fi
    marker "staying in recovery: a listed partition is still wrong (note armed if it could be set), no restart"
    exit 0
}

# ---------------------------------------------------------------- snapshot mode
# `rescue.sh snapshot`: copy the note aside and leave. Run by init, blocking, before the stock program.
SNAP=${RESCUE_SNAP:-/tmp/rescue.note}
if [ "$1" = snapshot ]; then
    n=0
    while [ ! -e "$PARA" ] && [ "$n" -lt 5 ]; do
        sleep 1
        n=$((n + 1))
    done
    dd if="$PARA" of="$SNAP" bs=2048 count=1 2>/dev/null
    [ -c "$KMSG" ] && echo "rescue.sh: snapshot of the note taken" > "$KMSG"
    exit 0
fi

# ---------------------------------------------------------------- main
cache_ok=0
mounted=0
log "rescue start"
wait_for "$PARA" || log "para did not appear within $WAIT s"

# Whose note is it? The stock recovery program clears the note within a second or two of starting
# (seen on the frame, 15 Nov), so the note is judged from a copy taken before that program starts:
# init runs this script with the word `snapshot` at post-fs-data, which copies the first 2048 bytes
# of `para` to $SNAP. Only if that copy is missing is `para` itself read, once, straight away.
if [ -s "$SNAP" ]; then
    kind=$(note_kind "$SNAP")
    log "note judged from the snapshot taken before the stock program started"
else
    kind=$(note_kind)
    log "no snapshot; note judged from para as it is now"
fi
case "$kind" in
    plain)     NOTE_AT_START="boot-recovery (ours)" ;;
    just_exit) NOTE_AT_START="boot-recovery --just_exit (ours)" ;;
    none)      NOTE_AT_START=none ;;
    *)         NOTE_AT_START="not ours" ;;
esac
log "note in para at start: $NOTE_AT_START"

case "$kind" in
    plain|just_exit) ;;
    *)
        log "the note is not ours: leaving everything to the stock recovery program; nothing mounted, nothing written"
        marker "finished; note not ours, nothing done"
        exit 0
        ;;
esac

# Our own mount of the cache partition. /cache itself belongs to the stock program and is never touched.
if [ "$DO_MOUNT" = 1 ]; then
    mkdir -p "$MNT"
    if wait_for "$CACHE_DEV"; then
        try=1
        while [ "$try" -le 5 ]; do
            if mount -t ext4 -o noatime,nosuid,nodev "$CACHE_DEV" "$MNT"; then
                cache_ok=1
                mounted=1
                break
            fi
            sleep 1
            try=$((try + 1))
        done
    fi
else
    [ -d "$MNT" ] && cache_ok=1
fi

if [ "$cache_ok" = 1 ]; then
    NEWLOG=$MNT/rescue.log
    if [ -f "$NEWLOG" ] && [ "$(($(wc -c < "$NEWLOG")))" -gt 262144 ]; then
        mv "$NEWLOG" "$NEWLOG.old"
    fi
    if cat "$TMPLOG" >> "$NEWLOG"; then
        LOGFILE=$NEWLOG
        MARKFILE=$MNT/rescue.marker
    fi
else
    log "cache could not be mounted; nothing will be restored"
fi
marker "started"

if [ "$kind" = just_exit ]; then
    if [ "$cache_ok" = 1 ] && [ -f "$STORE/list" ]; then
        LIST_STATE="present but not used (--just_exit)"
        log "there is a list, but the note says --just_exit: the list is NOT used"
    fi
    log "--just_exit: leaving the note and the restart to the stock recovery program"
    marker "waiting for the stock program to restart the frame"
    wait_seconds "$JUST_EXIT_WAIT"
    log "still running $JUST_EXIT_WAIT s after --just_exit: the stock program did not restart the frame"
    go_home
fi

# With our plain note the stock program reads /cache/recovery/command (an OTA package, a wipe, ...). A
# non-empty file there means this run is not ours: do nothing, as with a foreign note.
if [ "$cache_ok" = 1 ] && [ -s "$MNT/recovery/command" ]; then
    log "recovery/command in the cache is not empty: not our run; leaving everything to the stock recovery program, nothing written"
    marker "finished; recovery/command present in the cache, nothing done"
    if [ "$mounted" = 1 ]; then
        umount "$MNT"
    fi
    exit 0
fi

# Close the power-cut gap before the first write: the stock program has (or is about to have) cleared the note,
# and a power cut while mounting or hashing 110 MB of `product` would then start Android on a bad image. So: wait
# for the stock program's clear (up to 10 s), then set our plain note again. This does not touch `attempts`.
# Every normal end clears it again (go_home), or leaves it set on purpose (stay_armed).
n=0
while [ "$n" -lt 10 ] && [ "$(note_kind)" != none ]; do
    sleep 1
    n=$((n + 1))
done
if set_plain_note; then
    log "our plain note set again at the start, so that a power cut from here on comes back to recovery"
else
    case "$(note_kind)" in
        none|plain)
            log "our plain note could not be set again at the start (para not writable?); going on without it"
            ;;
        *)
            log "the note in para is no longer ours: leaving everything to the stock recovery program, nothing written"
            marker "finished; the note changed under us, nothing done"
            if [ "$mounted" = 1 ]; then
                umount "$MNT"
            fi
            exit 0
            ;;
    esac
fi

# Three ways in, by what the store says:
#   manual  a `stay` file or a `guarded` line in the list: a flash we armed ourselves. Restore at once (the
#           old behaviour); the ladder counter is not touched.
#   resume  a restore was cut off earlier (counter `attempts` is 1 or 2) and a list is there: finish it, at once.
#   ladder  everything else: our plain note without a list that says otherwise. The counter `rung` goes up by one.
mode=ladder
stay=0
if [ "$cache_ok" = 1 ]; then
    read_attempts
    if [ -e "$STORE/stay" ]; then
        mode=manual
        stay=600
        read -r secs rest < "$STORE/stay"
        case "$secs" in
            ""|0*|*[!0-9]*|?????*) ;;
            *) [ -z "$rest" ] && [ "$secs" -le 3600 ] && stay=$secs ;;
        esac
    elif list_guarded; then
        mode=manual
    elif [ -f "$STORE/attempts" ] && [ "$ATTEMPTS" -ge 1 ] && [ "$ATTEMPTS" -le 2 ] && [ -f "$STORE/list" ]; then
        mode=resume
    fi
fi

# Check the list and restore what is wrong (the full work). Used by manual, resume and rung 3.
restore_from_list() {
    if [ -f "$STORE/list" ]; then
        if check_list; then
            LIST_STATE=accepted
            log "list accepted; stopping the stock recovery program so it cannot restart the frame in mid-restore"
            stop recovery
            read_attempts
            [ "$ATTEMPTS" -ge 3 ] && log "gave up after 3 tries: no partition will be written in this run"
            marker "checking partitions"
            do_list
            if [ -z "$NOT_RESTORED" ]; then
                rm -f "$STORE/attempts"
                sync
            fi
        else
            LIST_STATE=refused
            log "nothing restored"
        fi
    else
        log "no list; nothing to restore"
    fi
    # A resume that wrote nothing in this run (list refused, copy bad, nothing left to write): drop the
    # restore-try counter, so the next entry is a rung of the ladder and resume cannot repeat for ever.
    if [ "$mode" = resume ] && [ "$ARMED" != yes ]; then
        log "resume wrote nothing: dropping the restore-try counter so the next entry is a rung"
        rm -f "$STORE/attempts"
    fi
    sync
}

if [ "$mode" = ladder ]; then
    if [ "$cache_ok" != 1 ]; then
        stay_here "cache is not usable, so the ladder cannot be counted"
    fi
    read_rung
    if [ "$RUNG" -ge 3 ]; then
        new=3
    else
        new=$((RUNG + 1))
        # The count is recorded and read back before anything else is done, so a power cut cannot reset it.
        if ! write_rung "$new"; then
            # A full or read-only cache must not trap the frame: do the restore step anyway; if nothing listed
            # is wrong, clear the note so a power cycle starts Android (which can then free space); if something
            # is wrong, stay armed.
            log "the ladder counter cannot be written"
            restore_from_list
            if [ -n "$NOT_RESTORED" ]; then
                stay_armed "counter not writable"
            fi
            clear_note
            stay_here "the ladder counter cannot be written (nothing listed is wrong; note cleared)"
        fi
    fi
    log "ladder: our plain note, no healthy clear since the last entry: rung $new"
    # Always first: every listed partition is checked and, if wrong and its copy is good, put back. The
    # same protections as ever (note armed before the first write, `attempts`, three-way copy check).
    restore_from_list
    if [ "$new" -lt 3 ] && [ -n "$NOT_RESTORED" ]; then
        stay_armed "rung $new"
    fi
    case "$new" in
        1)
            log "rung 1: restart; the note is cleared, Android arms it again itself"
            marker "rung 1: restarting"
            go_home
            ;;
        2)
            if echo ladder > "$STORE/safe"; then
                sync
                log "rung 2: safe-start flag written ($STORE/safe); restarting; the note is cleared"
            else
                log "rung 2: the safe-start flag could not be written; restarting anyway; the note is cleared"
            fi
            marker "rung 2: restarting"
            go_home
            ;;
        *)
            # Nothing wrong in the list: clear the note, so a power cycle from here starts Android and not this
            # recovery again. Something still wrong: keep it armed, a power cycle must come back here.
            if [ -n "$NOT_RESTORED" ]; then
                stay_armed "rung 3"
            fi
            clear_note
            stay_here "rung 3: no restart (Android has failed three starts in a row)"
            ;;
    esac
fi

log "mode: $mode"
restore_from_list

if [ "$stay" -gt 0 ]; then
    log "stay file found: stopping the stock recovery program and staying $stay s, then restarting"
    stop recovery
    marker "staying $stay s before restarting"
    wait_seconds "$stay"
    log "stay time is over"
fi

# Manual and resume end cleared: Android arms the note itself at its next start. Never restart while a listed
# partition is still wrong (that would be Red State for ever): stay, armed.
if [ -n "$NOT_RESTORED" ]; then
    stay_armed "$mode"
fi
# A guarded flash was in progress and the list was refused: it cannot vouch for anything, so do not restart.
if [ "$mode" = manual ] && [ "$LIST_STATE" = refused ]; then
    stay_armed "manual with a refused list"
fi
go_home
