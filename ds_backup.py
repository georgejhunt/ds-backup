#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2007 Ivan Krstić
# Copyright (C) 2007 Tomeu Vizoso
# Copyright (C) 2007 One Laptop per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License (and
# no other version) as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import sha
import urllib
import os.path
import tempfile
import time
import glob
import popen2
import re

from sugar import env
from sugar import profile

class BackupError(Exception): pass
class ProtocolVersionError(BackupError): pass
class RefusedByServerError(BackupError): pass
class ServerTooBusyError(BackupError): pass
class TransferError(BackupError): pass
class NoPriorBackups(BackupError): pass
class BulkRestoreUnavailable(BackupError): pass

def find_last_backup(server, xo_serial):
    try:
        ret = urllib.urlopen(server + '/last/%s' % xo_serial).read()
        return ret.split(',', 1)
    except IOError, e:
        if e[1] == 404:
            raise ProtocolVersionError(server)
        elif e[1] == 403:
            raise RefusedByServerError(server)
        elif e[1] == 503:
            raise ServerTooBusyError(server)

def find_restore_path(server, xo_serial):
    try:
        ret = urllib.urlopen(server + '/restore/%s' % xo_serial).read()
        if ret == '0':
            raise NoPriorBackups(server)
        else:
            return ret
    except IOError, e:
        if e[1] == 500:
            raise BulkRestoreUnavailable(server)
        elif e[1] == 503:
            raise ServerTooBusyError(server)

def rsync_to_xs(from_path, to_path, keyfile, user):

    # add a trailing slash to ensure
    # that we don't generate a subdir
    # at the remote end. rsync oddities...
    if not re.compile('/$').search(from_path):
        from_path = from_path + '/'

    ssh = '/usr/bin/ssh -F /dev/null -o "PasswordAuthentication no" -i "%s" -l "%s"' \
        % (keyfile, user)
    rsync = "/usr/bin/rsync -az --partial --delete --timeout=160 -e '%s' '%s' '%s' " % \
            (ssh, from_path, to_path)
    print rsync
    rsync_p = popen2.Popen3(rsync, True)

    # here we could track progress with a
    # for line in pipe:
    # (an earlier version had it)

    # wait() returns a DWORD, we want the lower
    # byte of that.
    rsync_exit = os.WEXITSTATUS(rsync_p.wait())
    if rsync_exit != 0:
        # TODO: retry a couple of times
        # if rsync_exit is 30 (Timeout in data send/receive)
        raise TransferError('rsync error code %s, message:'
                            % rsync_exit, rsync_p.childerr.read())

    # Transfer an empty file marking completion
    # so the XS can see we are done.
    tmpfile = tempfile.mkstemp()
    rsync = ("/usr/bin/rsync --timeout 10 -e '%s' '%s' '%s' "
             % (ssh, tmpfile[1], to_path+'/.transfer_complete'))
    rsync_p = popen2.Popen3(rsync, True)
    rsync_exit = os.WEXITSTATUS(rsync_p.wait())
    if rsync_exit != 0:
        # TODO: retry a couple ofd times
        # if rsync_exit is 30 (Timeout in data send/receive)
        raise TransferError('rsync error code %s, message:'
                            % rsync_exit, rsync_p.childerr.read())

def have_ofw_tree():
    return os.path.exists('/ofw')

def read_ofw(path):
    path = os.path.join('/ofw', path)
    if not os.path.exists(path):
        return None
    fh = open(path, 'r')
    data = fh.read().rstrip('\0\n')
    fh.close()
    return data

# if run directly as script
if __name__ == "__main__":

    backup_url = 'http://schoolserver/backup/1'

    if have_ofw_tree():
        sn = read_ofw('mfg-data/SN')
    else:
        sn = 'SHF00000000'

    ds_path = env.get_profile_path('datastore')
    pk_path = os.path.join(env.get_profile_path(), 'owner.key')

    # TODO: Check backup server availability
    # if ping_xs():
    rsync_to_xs(ds_path, 'schoolserver:datastore', pk_path, sn)
    # this marks success to the controlling script...
    os.system('touch ~/.sugar/default/ds_backup-done')
