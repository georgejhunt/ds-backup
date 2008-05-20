#!/bin/bash
#
# Wrapper around ds_backup - will be called in 2 situations
#
#  - On cron, every 30 minutes during waking/school hours
#    If you are calling this from cron, pass 'cron' as
#    the first parameter.
#
#  - from a NetworkManager event when we
#    associate to the school network. In that case, we get
#    2 parameters - if, action
#
# Note: this wrapper _must_ be cheap to execute to avoid burning
# battery.
#
# Author: Martin Langhoff <martin@laptop.org>
#

# If we have backed up recently, leave it for later. Use
# -mtime 0 for "today"
# -mtime -1 for "since yesterday"
# -mtime -10 for in the last 10 days
#
# Using -daystart means that the script is more eager to backup
# in the morning. Without -daystart, laptops backup "later in the day"
# everyday, as they only start trying after 24hs...
#
# Another tack could be -mmin -1200 (20hs), which could be more stable.
#
if [ `find ~/.sugar/default/ds_backup-done -daystart -mtime 0 2>/dev/null` ]
then
    exit 0
fi

if [ -e /sys/class/power_supply/olpc-battery/capacity \
     -a -e /sys/class/power_supply/olpc-ac/online ]
then
    # OLPC HW
    B_LEVEL=`cat /sys/class/power_supply/olpc-battery/capacity`
    AC_STAT=`cat /sys/class/power_supply/olpc-ac/online`
else
    # Portable, but 100ms slower on XO-1
    # Note - we read the 1st battery, and the 1st AC
    # TODO: Smarter support for >1 battery
    B_HAL=`hal-find-by-capability --capability battery | head -n1`
    AC_HAL=`hal-find-by-capability --capability ac_adapter`
    if [ -z $B_HAL -o -z $AC_HAL ]
    then
	# We do expect a battery & AC
	exit 1;
    fi

    B_LEVEL=`hal-get-property --udi $B_HAL --key battery.charge_level.percentage`
    AC_STAT=`hal-get-property --udi $AC_HAL --key ac_adapter.present`

    # hal reports ac adapter presence as 'true'
    # ... translate...
    if [ AC_STAT = 'true' ]
    then
	AC_STAT=1
    else
	AC_STAT=0
    fi
fi

# If we are on battery, and below 30%, leave it for later
if [ $AC_STAT == "0" -a $B_LEVEL -lt 30 ]
then
	exit 0
fi

##
## TODO: 
## - Test: Can we see the XS?
## - Handle being called from NM
##

### Ok, we are going to make a backup

# make the lock dir if needed
if [ ! -d ~/.sugar/default/lock ]
then
    mkdir ~/.sugar/default/lock
fi

#
#  Sleep a random amount, not greater than 20 minutes
#  We use this to stagger client machines in the 30 minute
#  slots between cron invocations...
(sleep $(($RANDOM % 1200));

# Execute ds_backup.py from the same
# directory where we are. Use a flock
# to prevent concurrent runs. If the
# flock does not succeed immediately,
# we quit.
LOCKFILE=~/.sugar/default/lock/ds_backup.run
flock -n $LOCKFILE `dirname $0 `/ds_backup.py
EXITCODE=$?

# Clean up the lock - if we can ;-)
rm $LOCKFILE 2>/dev/null

# Propagate the exit code of the flock/ds_backup invocation
exit $EXITCODE

