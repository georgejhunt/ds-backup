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
import sys
import os
import re
import pwd

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
if not re.match(homebasepath, user[5]):
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
    sys.stderr.write('Could not set gid %s uid %s' % user[3], user[2])

# rm the flagfile
os.unlink(fpath)

# os.system() rsync 
#print 







