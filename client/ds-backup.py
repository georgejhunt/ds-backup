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

import os, re, sys, tempfile, glob, time
import urllib2
from urllib2 import URLError, HTTPError
import subprocess
from subprocess import Popen, PIPE, call

from sugar import env
from sugar import profile

class BackupError(Exception): pass
class ProtocolVersionError(BackupError): pass
class RefusedByServerError(BackupError): pass
class ServerTooBusyError(BackupError): pass
class TransferError(BackupError): pass
class NoPriorBackups(BackupError): pass
class BulkRestoreUnavailable(BackupError): pass

def check_server_available(server, xo_serial):

    try:
        ret = urllib2.urlopen(server + '/available/%s' % xo_serial).read()
        return 200
    except HTTPError, e:
        # server is there, did not fullfull req
        #  expect 404, 403, 503 as e[1]
        return e.code
    except URLError, e:
        # log it?
        # print e.reason
        return -1

def rsync_to_xs(from_path, backup_host, keyfile, user):

    to_path = backup_host + ':datastore-current'

    # add a trailing slash to ensure
    # that we don't generate a subdir
    # at the remote end. rsync oddities...
    if not re.compile('/$').search(from_path):
        from_path = from_path + '/'

    ssh_shellcmd = '/usr/bin/ssh -F /dev/null -o "PasswordAuthentication no" -o "StrictHostKeyChecking no" -i "%s" -l "%s"' \
        % (keyfile, user)
    rsync_cmd = ['/usr/bin/rsync', '-z', '-rlt', '--partial',
             '--delete', '--timeout=160',
             '-e', ssh_shellcmd, from_path, to_path]
    #print rsync

    rsync_exit = call(rsync_cmd)

    # TODO: we could track progress with a
    # for line in pipe:
    # (an earlier version had it)

    if rsync_exit != 0:
        # TODO: retry a couple of times
        # if rsync_exit is 30 (Timeout in data send/receive)
        raise TransferError('rsync error code %s'
                            % rsync_exit)

    # Transfer an empty file marking completion
    # so the XS can see we are done.
    # Note: the dest dir on the XS is watched via
    # inotify - so we avoid creating tempfiles there.
    tmpfile = tempfile.mkstemp()
    rsync_cmd = ['/usr/bin/rsync', '-z',
                 '-rlt', '--timeout', '10',
                 '-T', '/tmp', '-e', ssh_shellcmd,
                 tmpfile[1],
                 backup_host + ':/var/lib/ds-backup/completion/'+user]
    rsync_exit = call(rsync_cmd)
    if rsync_exit != 0:
        # TODO: retry a couple of times
        # if rsync_exit is 30 (Timeout in data send/receive)
        raise TransferError('rsync error code %s.'
                            % rsync_exit)

def get_sn():
    if have_ofw_tree():
        return read_ofw('mfg-data/SN')
    # on SoaS try gconf, 'identifiers'
    sn = gconf_get_string('/desktop/sugar/soas_serial')
    if sn:
        return sn
    sn = identifier_get_string('sn')
    if sn:
        return sn

    return 'SHF00000000'

def get_backup_url():

    bu = gconf_get_string('/desktop/sugar/backup_url')
    if bu:
        return bu
    try: # pre-gconf
        from iniparse import INIConfig
        conf = INIConfig(open(os.path.expanduser('~')+'/.sugar/default/config'))
        # this access mode throws an exception if the value
        # does not exist
        bu = conf['Server']['backup1']
    except:
        pass
    if bu:
        return bu
    bu = identifier_get_string('backup_url')
    if bu:
        return bu
    return ''

def gconf_get_string(key):
    """We cannot use python gconf from cron scripts,
    but cli gconftool-2 does the trick.
    Will throw subprocess.Popen exceptions"""
    try:
        value = Popen(['gconftool-2', '-g', key],
                      stdout=PIPE).communicate()[0]
        return value
    except:
        return ''

def identifier_get_string(key):
    """This is a config method used by some versions of
    Sugar -- in use in some SoaS"""
    try:
        fpath = os.path.expanduser('~')+'/.sugar/default/identifiers/'+key
        fh    = open(fpath, 'r')
        value = fh.read().rstrip('\0\n')
        fh.close()
        return value
    except:
        return ''

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

    backup_host = '' # host
    backup_url = ''  # target rsync url - set at reg time
    backup_ctrl_url = '' # http address for control proto

    ## idmgr (on XS 0.6 and earlier)
    ## sets backup_url at regtime to
    ## username@fqdn:backup - but expects the
    ## rsync cmd to go to username@fqdn:datastore-current
    ## -- so we only read the FQDN from the value.

    backup_url = get_backup_url()

    if not backup_url:
        # not registered, nothing to do!
        # (normally caught in ds-backup.sh)
        exit(0)

    # matches the host part in
    # - user@host:path
    # - host:path
    m = re.match('(\w+\@)?(\w|.+?):', backup_url)
    if not m or not m.group(2):
        sys.stderr.write("Cannot extract backup host from %s\n" % backup_url)
        exit(1)
    backup_host = m.group(2)

    backup_ctrl_url = 'http://' + backup_host + '/backup/1'

    sn = get_sn()

    ds_path = env.get_profile_path('datastore')
    pk_path = os.path.join(env.get_profile_path(), 'owner.key')

    # Check backup server availability.
    # On 503 ("too busy") apply exponential back-off
    # over 10 attempts. Combined with the staggered sleep
    # in ds-backup.sh, this should keep thundering herds
    # under control. We are also holding a flock to prevent
    # local races.
    # With range(1,7) we sleep up to 64 minutes.
    for n in range(1,7):
        sstatus = check_server_available(backup_ctrl_url, sn)
        if (sstatus == 200):
            # cleared to run
            rsync_to_xs(ds_path, backup_host, pk_path, sn)
            # this marks success to the controlling script...
            os.system('touch ~/.sugar/default/ds-backup-done')
            exit(0)
        elif (sstatus == 503):
            # exponenxtial backoff
            time.sleep(60 * 2**n)
        elif (sstatus == -1):
            # could not connect - XS is not there
            exit(1)
        else:
            # 500, 404, 403, or other unexpected value
            exit(sstatus)

