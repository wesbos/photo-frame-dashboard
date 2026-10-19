#!/system/bin/sh
# PF1506 kiosk tuning, run by init once boot completes (frame-tuning.rc).
#
# eMMC wear: /data (f2fs) is ~4% full, so background garbage collection only
# rewrites data (~1.4 GB/day measured) with little to gain at that fill level.
# Turn it off; f2fs still
# runs foreground GC on its own if free space ever gets low.
mount -o remount,background_gc=off /data \
    && log -t frame-tuning "f2fs background_gc off on /data"
