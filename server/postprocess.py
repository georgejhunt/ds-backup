#!/usr/bin/python
#
# Once a backup from a client is complete,
# postprocess is called by incrond finish off
# the task. Should be called in as root, and it will
# drop privileges to the user it will process.
#
# The incrond invocation line should be
# /path/to/dir IN_CREATE /path/to/postprocess.py $@ $#
#
# (in other words, we expect 2 parameters, dirpath, filename)
#
# Author: Martin Langhoff <martin@laptop.org>
#
import sys
import os
import re
import pwd
import subprocess
from subprocess import PIPE

homebasepath = '/library/users'
dirpath      = sys.argv[1]
fname        = sys.argv[2]
fpath        = dirpath + '/' + fname

#
# Sanity checks:
# - must be a file
# - username must be ^\w+$
# - uid must match username
# - must exist in /library/users
#
# Note: there are race conditions here.
#       We will drop privs before doing
#       potentially damanging stuff.
#

if not os.path.isfile(fpath):
    exit(1)
if os.path.islink(fpath):
    exit(1)
if not re.match('\w+$', fname):
    exit(1)

# we'll hit a KeyError exception and exit 1
# if the user is not found
user  = pwd.getpwnam(fname)
# match with /library/users
if not user[5].startswith(homebasepath):
    exit(1)
# user uid must match file owner uid
if not (user[3] == os.stat(fpath)[4]):
    exit(1)

# Checks done -now we drop privs and
# - remove flag file
# - hardlink files as appropriate
#
try:
    os.setgid(user[3])
    os.setuid(user[2])
except OSError, e:
    sys.stderr.write('Could not set gid %s uid %s' % (user[3], user[2]))

# rm the flagfile
os.unlink(fpath)

#
# UTC timestamp to the minute
# clients are not expected to retry often if they succeed.
# and there is no point in us trying to keep any better
# granularity than this.
#
# Popen seems to be the verbose pythonic way
# of replacing backticks. ".communicate()[0]"!
# 
datestamp = subprocess.Popen(['date', '-u', '+%Y-%m-%d_%H:%M'],stdout=PIPE
                             ).communicate()[0]
# comes with newline - rstrip() will chomp it
datestamp = datestamp.rstrip()

sys.stdout.write(datestamp)
exitcode = subprocess.call(['cp', '-al',
                            user[5] + '/datastore-current',
                            user[5] + '/datastore-' + datestamp])
if (exitcode != 0):
    sys.stderr.write('Cannot cp -al')
    exit(1)

# Set ACLs so that apache can read the homedir
exitcode = subprocess.call(['setfacl', '-m',
                            'u:apache:rx', user[5]])
if (exitcode != 0):
    sys.stderr.write('setfacl')
    exit(1)

# To say
#
# find user[5]/datastore- + datestamp -type f \
#   | xargs -n100 setfactl -m u:apache:r
# find user[5]/datastore- + datestamp -type d \
#   | xargs -n100 setfactl -m u:apache:rx
#
# We say Pythonistically
#
psrc  = Popen(['find', user[5]+'/datastore-' + datestamp,
               '-type', 'f'], stdout=PIPE)
psink = Popen(['xargs', '-n100', 'setfacl', '-m', 'u:apache:r'],
              stdin=psrc.stdout,stdout=PIPE)
psink.communicate()

psrc  = Popen(['find', user[5]+'/datastore-' + datestamp,
               '-type', 'd'], stdout=PIPE)
psink = Popen(['xargs', '-n100', 'setfacl', '-m', 'u:apache:rx'],
              stdin=psrc.stdout,stdout=PIPE)
psink.communicate()

# Note the -n parameter here. Without it
# the symlink lands inside the previous
# target of datastore-last. Oops!
exitcode = subprocess.call(['ln', '--force', '-sn',
                 user[5] + '/datastore-' + datestamp,
                 user[5] + '/datastore-last'])
if (exitcode != 0):
    sys.stderr.write('Cannot ln')
    exit(1)

# done
