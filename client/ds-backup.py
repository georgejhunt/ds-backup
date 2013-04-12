#!/usr/bin/python
# -*- coding: utf-8 -*-
#updated version
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
from urllib2 import URLError, HTTPError, urlopen
import subprocess
from subprocess import Popen, PIPE, call

from sugar import env
from sugar import profile

from sugar.datastore import datastore
from path import path
from sftp import sftp
import datetime

LIMIT = 1024
WORKPATH = path('/tmp/')
EXCLUDED = ['org.laptop.Terminal', 'org.laptop.Log']

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

def sync_time_to_xs():

    xstime = urlopen('http://schoolserver/bibliotheque/school/time')
    response = xstime.read().replace('\n','')
    txtout = 'sudo date --set="' + response + '"'
    print txtout
    fout = open('/tmp/xstime','w')
    fout.write(txtout)
    fout.close()

def datastore_to_xs():
    #open log
    log = open('/tmp/logBackup','w')
    #get journal records
    query = {}
    keys = ['uid','activity','title','title_set_by_user','mime_type','journal','keep']
    ds_objects,num_objects = datastore.find(query,properties=keys)
    print >> log, 'num_objects',num_objects
    #process each one
    for i in range(num_objects):
        ds_object = ds_objects[i]
        #is it in the journal
        try:
            journal = ds_object.metadata['journal']
        except:
            print >> log,sys.exc_info()[:2]
            #new record created since last run of ds-backup
            #is it a journal record? (title_set_by_user == 1 and has_file_path)
            print >> log, i, 'new record'
            activity = ds_object.metadata['activity']
            if activity in EXCLUDED:
                jr = False
                print >> log, 'activity',activity,'excluded'
            else:
                jr = True
            title_set_by_user = ds_object.metadata['title_set_by_user']
            file_path = ds_object.get_file_path()
            jobject = datastore.get(ds_object.object_id)
            metadata = {}
            for key in jobject.metadata.keys():
                if not key == 'preview':
                    metadata[key] = jobject.metadata[key]
            metadata_path = WORKPATH+path(file_path).namebase+'.metadata'
            fout = open(metadata_path,'w')
            fout.write(str(metadata))
            fout.close()
            if path(file_path).exists() and title_set_by_user == '1' and jr:
                #journal record
                print >>log, 'journal record',file_path
                try:
                    ds_object.metadata['journal'] = 1
                except:
                    print >> log, 'create journal key failed',sys.exc_info()[:2]
                ds_object.metadata['keep'] = 1
                script = 'cd journal\nput '+ metadata_path+'\nput '+file_path+'\n'
                result,err = sftp(script,WORKPATH)
                if err:
                    print >> log, script, 'err', err
                print >> log, ds_object.metadata['title'],'added to Journal',
                print >> log, 'keep', ds_object.metadata['keep']
                datastore.write(ds_object)
            else:
                #log record
                print >> log, 'log record'
                script = 'cd log\nput '+metadata_path+'\n'
                result,err = sftp(script,WORKPATH)
       	       	if err:
       	       	    print >> log, script, 'err', err
                else: 
                    try:
                        datastore.delete(ds_object.object_id)
                    except:
                        pass
            subprocess.call('rm -rf ' + WORKPATH / '*.metadata',shell=True)
        else:
            #journal record
            file_path = ds_object.get_file_path()
            fn = path(file_path).name
            try:
                testjournal = ds_object.metadata['journal']
            except:
                testjournal = 'key error'
            try:
                testkeep = ds_object.metadata['keep']
            except:
                testkeep = 'key error'
            print >> log, i, 'existing journal record', fn, 
            print >> log, 'journal',testjournal,
            print >> log, 'keep',testkeep
            if journal == 2:
                print >> log, 'delete requested'
                #delete it from ss
                file_path = ds_object.get_filepath
                fn = path(file_path).name
                script = 'cd journal\nrm -rf ' + fn + '*'
                result,err = sftp(script)
       	       	if result:
       	       	    print >> log, 'result',script,result
       	       	if err:
       	       	    print >> log, 'err',script,err 
                #delete locally
                try:
                    datastore.delete(ds_object.object_id)
                except:
                    pass
            else:
                try:
                    keep = ds_object.metadata['keep']
                except:
                    keep = 'key error'
                try:
                    journal = ds_object.metadata['journal']
                except:
                    journal = 'key error'
                print >> log, 'journal record: keep', keep, 'journal', journal
                if keep == 0 and journal == 1:
                    #delete local data
                    print >> log, 'deleting local data'
                    dsobject.file_path = None
                    dsobject.metadata['journal'] = 0
                    datastore.write(ds_object)
                if keep == 1 and journal == 0:
                    #get local copy of data from ss
                    print >> log, 'getting local copy of data from ss'
                    script = 'cd journal\nget '+fn
                    result,err=sftp(script,WORKPATH)
       	       	    if result:
       	       	        print >> log, 'result', script, result
       	       	    if err:
       	       	        print >> log, 'err',script,err 
                    dsobject.file_path = path('/tmp') / fn
                    dsobject.metadata['journal'] = 1
                    datastore.write(ds_object)
    #log version
    pth = path('/home/olpc/.sugar/default/patch')
    if pth.exists():
        fin = open(pth,'r')
        version = fin.read()
        fin.close()
        metadata = {}
        metadata['mtime'] = datetime.date
        metadata['title'] = 'version'
        metadata['title_set_by_user'] = 1
        metadata['version'] = version
        metadata_path = WORKPATH+path(file_path).namebase+'.metadata'
        fout = open(metadata_path,'w')
        fout.write(str(metadata))
        fout.close()
        script = 'cd log\nput '+metadata_path+'\n'
        result,err = sftp(script,WORKPATH)
        if err:
            print >> log, script, 'err', err
        else:
            try:
                datastore.delete(ds_object.object_id)
            except:
                pass
    log.close()


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


