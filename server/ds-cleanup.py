#!/usr/bin/python
#
# This is the datastore backup cleanup.
#
# Invoke once an hour from cron.d, can be
# invoked by the postprocess script if
# we are tight on disk space on the partition.
#
# This script will run to completion only once a day
# but the XS may not get power all day.
#  

# 3 months - 90 days max keep for daily snapshots
MAX_AGE_DAILY=90
# 70% default softquota
DS_SOFT_QUOTA=70

# Execution plan
#
#
# - Keep one monthly snapshot per user for snapshots
#   older than 3 months (MAX_AGE_DAILY).
#   Laptops will attempt daily backups - so we keep all the
#   dailies the first 90 days...
#
# - Service and user fairness
#   Be default 70% the /library/users partition is for ds-backup.
#   This can be overriden by an /etc/xs_quota.conf file 
#
#   Past the threshold, we will count the user accts with datastore dirs
#   divide the avaialble blocks on the partition, du -sh on each user, and
#   trim old monthly snapshots of the heaviest users until we are below
#   the quota.
#
#   The fact that we are undertaking wide hardlinking means that deleting old
#   snapshots might not free up as much as expected.
#
# - Hard-link across users? TODO :-)
#
#

import yaml
import os
import sys
import subprocess
from subprocess import PIPE
import re
import time

basehomedir = '/library/users'

# max 5% loadavg - run only on idle...
if (os.getloadavg()[0] > 5):
    sys.exit0()

if os.path.exists('/etc/xs-quotas.conf'):
    #qf = file('/etc/xs-quotas.conf', 'r')
    quotaconf = yaml.load(open('/etc/xs-quotas.conf', 'r').read());
    if (quotaconf.has_key('ds-backup')):
        quotaconf['ds-backup'] = int(quotaconf['ds-backup'])
        if (quotaconf['ds-backup'] < 100):
            DS_SOFT_QUOTA = quotaconf['ds-backup']
        else:
            sys.stderr.write('Odd quota')

# take a measure of disk usage...
# multiply the 'totals' by .95 to reflect that root
# has 5% of the disk resources set aside
libstat = os.statvfs(basehomedir)
usedblockspc = 1 - float(libstat[4])/(libstat[2]*0.95)
usedfnodespc = 1 - float(libstat[7])/(libstat[5]*0.95)

# if below the quota, mark as done, do nothing
if (usedblockspc < (DS_SOFT_QUOTA/100.0) and
    usedfnodespc < (DS_SOFT_QUOTA/100.0)):
    # mark as done for the day
    os.system('touch /var/lib/ds-backup/ds-cleanup-done')
    sys.exit(0)

#
# Remove dailies older than MAX_AGE_DAILY
#
# 
# `find /library/users -maxdepth 2 -mindepth 2 -type d -name 'datastore-[0-9]*' | sort`
# unfortunately, the piping below is memory-bound.
#
# TODO: `find|sort > tmpfile` and then read line by line from tmpfile
# so only the sort stage is memory-bound, and we free up RAM for others.
pfind  = subprocess.Popen(['find', basehomedir, '-maxdepth','2','-mindepth','2',
               '-type', 'd', '-name', 'datastore-[0-9]*'], stdout=PIPE)
psort = subprocess.Popen(['sort'],
              stdin=pfind.stdout, stdout=PIPE)

# Prepare for the job...
# by making cutdate a string, the comparison later is logically simple
# and fast.
rex = re.compile(basehomedir+'/(.+?)/datastore-(\d\d\d\d)-(\d\d)-(\d\d)')
cutdate = time.gmtime(time.time() - MAX_AGE_DAILY *60*60*24)
cutdate =  ('%04d%02d%02d' % (cutdate[0], cutdate[1], cutdate[2]))

# The directories will come in ASCENDING
# order. So we will only keep the first of
# each user/year/month 
lastuserid = None
lastyear   = None
lastmonth  = None
while 1:
    ds_snapshot = psort.stdout.readline()
    if not ds_snapshot:
        break
    ds_snapshot = ds_snapshot.rstrip()

    m = rex.match(ds_snapshot)
    if m:
        (userid, year, month, day)= m.groups();
        # same user,year,month
        if (userid==lastuserid and year==lastyear and month==lastmonth
            and cutdate > year+month+day):
            # Call scary rm -fr -- using sudo to confine
            # it to the approp
            subprocess.call(['sudo', '-u', userid, 'rm', '-fr',
                             '--one-file-system', '--', ds_snapshot])
        # keep track of last-seen vars
        lastuserid = userid
        lastyear   = year
        lastmonth  = month


for retries in range(10):
    # If we did this loop with a while 1 we could
    # get into an infinite loop where we are over quota
    # and no amount of pruning of ds snapshots
    # can help. Some situations like a huge _current_ snapshot
    # can DoS the backup service.

    # take a measure of disk usage -- 
    # multiply the 'totals' by .95 to reflect that root
    # has 5% of the disk resources set aside
    libstat = os.statvfs(basehomedir)
    usedblockspc = 1 - float(libstat[4])/(libstat[2]*0.95)
    usedfnodespc = 1 - float(libstat[7])/(libstat[5]*0.95)

    # if below the quota, mark as done, do nothing
    if (usedblockspc < (DS_SOFT_QUOTA/100.0) and
        usedfnodespc < (DS_SOFT_QUOTA/100.0)):
        # mark as done for the day
        os.system('touch /var/lib/ds-backup/ds-cleanup-done')
        sys.exit(0)

    # sys.stderr.write('over the quota? '+str(usedblockspc) + '<' +str(DS_SOFT_QUOTA/100.0)+"\n")

    ##
    ## Remove old snapshots of users over the implied per-user quota
    ## note that as user accounts are added we will dynamically shrink
    ## the per-user quota.
    ##
    # surprise - we do want shell expansion here
    # with subprocess '*' does not work :-/
    userdirs = os.popen('du -s ' + basehomedir + '/*').readlines()

    usercount = len(userdirs)
    userquota = ((DS_SOFT_QUOTA/100.0) * libstat[2]) / usercount
    userquota = int(userquota)

    # Remove one old snapshot of every user over the threshold - the oldest one

    while len(userdirs):
        userdir    = userdirs.pop()
        userblocks = int(userdir.split("\t")[0])
        # du fakes the blocks to 1K while the
        # quota blocks we have might have a different blocksize
        userblocks = userblocks * (libstat[0] / 1024)
        if userblocks > userquota:
            userdir = userdir.split("\t")[1].rstrip()
            pfind   = subprocess.Popen(['find', userdir, '-maxdepth','1','-mindepth','1',
                                        '-type', 'd', '-name', 'datastore-[0-9]*'], stdout=PIPE)
            psort = subprocess.Popen(['sort'],
                                     stdin=pfind.stdout, stdout=PIPE)
            ds_snapshot = psort.stdout.readline().rstrip()
            m = rex.match(ds_snapshot)
            if m:
                (userid, year, month, day)= m.groups();
                subprocess.call(['sudo', '-u', userid, 'rm', '-fr',
                                 '--one-file-system', '--', ds_snapshot])


# done
os.system('touch /var/lib/ds-backup/ds-cleanup-done')
