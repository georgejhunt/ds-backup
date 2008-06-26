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

##
## Are we on a School server network?
## skip if we aren't!
##
## Note: this is simplistic on purpose - as we may be
##       in one of many network topologies.
##
function skip_noschoolnet {

    # no DNS, no XS
    grep -c '^nameserver ' /etc/resolv.conf 1>&/dev/null || exit

    # can't resolve & ping? outta here
    ping -c1 schoolserver 1>&/dev/null || exit

    # TODO: if we are on a mesh, count the hops to
    # the MPP - as the MPP will be the XS _or_ will provide
    # access to it. Only continue to backup if the hopcount
    # is low...

}

# If we have backed up recently, leave it for later. Use
# -mtime 0 for "today"
# -mtime -1 for "since yesterday"
# -mtime -10 for in the last 10 days
#
# Using -daystart means that the script is more eager to backup
# from early each day. Without -daystart, backups tend to happen
# later and later everyday, as they only start trying after 24hs...
#
# Another tack could be to try -mmin -1200 (20hs) - 
#
function skip_ifrecent {
    RECENT_CHECK='-daystart -mtime 0'
    if [ `find ~/.sugar/default/ds_backup-done $RECENT_CHECK 2>/dev/null` ]
    then
	exit 0
    fi
}


# Will skip if we are on low batt
function skip_onlowbatt {

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
	if [ "$AC_STAT" = 'true' ]
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
}
##
## TODO: 
## - Handle being called from NM

## These checks are ordered cheapest first
skip_ifrecent;
skip_onlowbatt;
skip_noschoolnet;

### Ok, we are going to attempt a backup

# make the lock dir if needed
# we will keep the (empty) file around
if [ ! -d ~/.sugar/default/lock ]
then
    mkdir ~/.sugar/default/lock || exit 1;
fi

# 
#  Sleep a random amount, not greater than 20 minutes
#  We use this to stagger client machines in the 30 minute
#  slots between cron invocations...
#  (yes we need all the parenthesys)
#(sleep $(($RANDOM % 1200)));

# After the sleep, check again. Perhaps something triggered
# another invokation that got the job done while we slept
skip_ifrecent;

# Execute ds_backup.py from the same
# directory where we are. Use a flock
# to prevent concurrent runs. If the
# flock does not succeed immediately,
# we quit.
LOCKFILE=~/.sugar/default/lock/ds_backup.run
flock -n $LOCKFILE `dirname $0 `/ds_backup.py
EXITCODE=$?

# Note: we keep the lockfile around to save
# NAND cycles.

# Propagate the exit code of the flock/ds_backup invocation
exit $EXITCODE

