#!/bin/bash
#
#
# Wrapper around ds-cleanup - 
#
# Author: Martin Langhoff <martin@laptop.org>
#

##
## We use skip_ifrecent() to ensure a daily run
## even in the face of unreliable power - so schedule
## this on cron with a reasonable frequency rather
## than once daily.
##

# If we have executed up recently, leave it for later. Use
# -mtime 0 for "today"
# -mtime -1 for "since yesterday"
# -mtime -10 for in the last 10 days
#
# Using -daystart means that the script is more eager to run
# from early each day. Without -daystart, backups tend to happen
# later and later everyday, as they only start trying after 24hs...
#
# Another tack could be to try -mmin -1200 (20hs) - 
#
function skip_ifrecent {
    RECENT_CHECK='-daystart -mtime 0'
    if [ `find /var/lib/ds-backup/ds-cleanup-done $RECENT_CHECK 2>/dev/null` ]
    then
	exit 0
    fi
}
skip_ifrecent;

# Execute ds-cleanup.py from the same
# directory where we are. Use a flock
# to prevent concurrent runs. If the
# flock does not succeed immediately,
# we quit.
LOCKFILE=/var/lib/ds-backup/ds-cleanup.run

# this script is IO heavy, and not
# a priority, so we run it under ionice -c3 (idle class)

flock -n $LOCKFILE ionice -c3 `dirname $0 `/ds-cleanup.py
EXITCODE=$?

# Propagate the exit code of the flock/ds-backup invocation
exit $EXITCODE