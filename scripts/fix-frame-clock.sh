#!/bin/bash
# Syncs a connected KPKUE DP-10B frame's clock to real local time (no RTC battery — the clock
# resets to a stale default on every power loss; see dashboard/CLAUDE.md's "No RTC battery").
#
# This device's toybox `date @<epoch>` has a quirk: it reads the epoch number as if it were
# already local wall-clock time rather than converting it from UTC, so feeding it the real,
# correct UTC epoch makes the on-screen clock run fast by the local UTC offset (4h on AST, 3h
# on ADT). Verified: setting the device to epoch 946684800 (exactly 2000-01-01 00:00:00 UTC)
# made it display 00:00:00 AST, not the correct 2000-01-01 20:00:00 AST (or equivalently, its
# `date -u` then read 4h further ahead on top of that). The old `adb shell su -c "date @$(date
# +%s)"` command this repo used to document was wrong for exactly this reason.
#
# Fix: feed it (real epoch + local UTC offset) instead of the real epoch, so its broken
# local-as-UTC interpretation lands on the correct wall-clock time. Re-derives the offset from
# `date +%z` on every run, so this stays correct across DST changes (AST <-> ADT).
set -e

OFFSET_STR=$(date +%z)
SIGN="${OFFSET_STR:0:1}"
HH="${OFFSET_STR:1:2}"
MM="${OFFSET_STR:3:2}"
OFFSET_SECONDS=$(( 10#$HH * 3600 + 10#$MM * 60 ))
if [ "$SIGN" = "-" ]; then OFFSET_SECONDS=$(( -OFFSET_SECONDS )); fi

REAL_EPOCH=$(date +%s)
ADJUSTED_EPOCH=$(( REAL_EPOCH + OFFSET_SECONDS ))

adb shell su -c "date @$ADJUSTED_EPOCH"
echo "device now shows:"
adb shell date
