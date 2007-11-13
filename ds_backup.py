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

import simplejson
#import dbus

#from sugar import env

DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

class BackupError(Exception): pass
class ProtocolVersionError(BackupError): pass
class RefusedByServerError(BackupError): pass
class ServerTooBusyError(BackupError): pass
class TransferError(BackupError): pass
class NoPriorBackups(BackupError): pass
class BulkRestoreUnavailable(BackupError): pass

# FIXME: We should not be doing this for every entry. Cannot get JSON to accept
# the dbus types?
def _sanitize_dbus_dict(dbus_dict):
    base_dict = {}
    for key, value in dbus_dict.iteritems():
        key = str(key)
        value = str(value)
        base_dict[key] = value
    return base_dict

def _write_metadata_and_files(datastore, timestamp, max_items):
    ds_dir = env.get_profile_path('datastore')
    store_dir = os.path.join(ds_dir, 'store')
    backup_metadata_path = os.path.join(ds_dir, 'backup.idx')
    backup_list_path = os.path.join(ds_dir, 'backup-files.idx')
    backup_metadata = open(backup_metadata_path, 'w')
    backup_list = open(backup_list_path, 'w')
    external_properties = ['preview']
    query = {'timestamp': {'start': timestamp, 'end': int(time.time())}}
    if max_items is not None:
        query['limit'] = max_items
    print max_items
    entries, count = datastore.find(query, [], byte_arrays=True)
    print 'Writing metadata and file indexes for %d entries.' % len(entries)
    for entry in entries:
        for prop in external_properties:
            if prop in entry:
                del entry[prop]
                file_path = os.path.join(store_dir, prop, entry['uid'])
                if os.path.exists(file_path):
                    backup_list.write(file_path + '\n')
        file_path = os.path.join(store_dir, entry['uid'])
        if os.path.exists(file_path):
            backup_list.write(file_path + '\n')
        backup_metadata.write(json.write(_sanitize_dbus_dict(entry))+'\n')
    backup_metadata.close()
    backup_list.close()
    return backup_metadata_path, backup_list_path

def _write_state(datastore):
    ds_dir = env.get_profile_path('datastore')
    backup_state_path = os.path.join(ds_dir, 'backup.idx')
    backup_state_file, backup_state_path = \
            tempfile.mkstemp(suffix='.idx', prefix='backup-state')
    entries, count = datastore.find({}, ['uid'])
    print 'Writing current state for %d entries.' % len(entries)
    for entry in entries:
        os.write(backup_state_file, entry['uid'] + '\n')
    os.close(backup_state_file)
    return backup_state_path

def write_index_since(timestamp, max_items=None):
    bus = dbus.SessionBus()
    obj = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
    datastore = dbus.Interface(obj, DS_DBUS_INTERFACE)
    backup_metadata_path, backup_files_path = \
            _write_metadata_and_files(datastore, timestamp, max_items)
    backup_state_path = _write_state(datastore)
    return backup_metadata_path, backup_state_path, backup_files_path

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

def new_backup_notify(server, nonce, xo_serial):
    try:
        auth = sha.sha(nonce + xo_serial)
        # TODO: add auth header
        ret = urllib.urlopen(server + '/new/%s' % xo_serial).read()
    except IOError, e:
        if e[1] == 403:
            # Auth not accepted. Shouldn't normally happen.
            raise BackupError(server)

def _rsync(from_list, from_path, to_path, keyfile, user):
    ssh = '/usr/bin/ssh -F /dev/null -o "PasswordAuthentication no" -i "%s" -l "%s"' \
           % (user, keyfile)
    rsync = """/usr/bin/rsync -azP --files-from='%s' -e '%s' '%s'" """ % \
            (from_path, ssh, from_path, to_path)
    pipe = popen2.Popen3(rsync_cmd, True)
    if pipe.poll() != -1:
        os.kill(pipe.pid, signal.SIGKILL)
        raise TransferError('rsync error: %s' % pipe.childerr.read())
    for line in pipe:
        # Calculate and print progress from rsync file counter
        match = re.match(r'.*to-check=(\d+)/(\d+)', line)
        if match:
            print int((int(match.group(2)) - int(match.group(1))) * 100 / float(total))
    if pipe.poll() != 0:
        os.kill(pipe.pid, signal.SIGKILL)
        raise TransferError('rsync error: %s' % pipe.childerr.read())

def _unpack_bulk_backup(restore_index):
    bus = dbus.SessionBus()
    obj = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
    datastore = dbus.Interface(obj, DS_DBUS_INTERFACE)

    for line in file(restore_index):
        props = json.read(line)
    preview_path = os.path.join('preview', props['uid'])
    if os.path.exists(preview_path):
        preview = file(preview_path).read()
        props['preview'] = dbus.ByteArray(preview_data)
    props['uid'] = ''
    datastore.create(props, file_path, transfer_ownership=True)

if __name__ == "__main__":
    SERVER_URL = 'http://127.0.0.1:8080/backup/1'
    XO_SERIAL = 'SHF7000500'

#    timestamp, nonce = find_last_backup(SERVER_URL, XO_SERIAL)
#    metadata, state, files = write_index_since(timestamp)  # timestamp or 0
    metadata, state, files = ('backup.idx', 'backup-state.idx', 'backup-files.idx')
