#!/usr/bin/python

## Authors: Tomeu Vizoso <tomeu@tomeuvizoso.net>
##          Martin Langhoff <martin@laptop.org>

import sys
import os
import unittest
import time
import tempfile
import shutil
from datetime import datetime

import dbus

DS_DBUS_SERVICE = "org.laptop.sugar.DataStore"
DS_DBUS_INTERFACE = "org.laptop.sugar.DataStore"
DS_DBUS_PATH = "/org/laptop/sugar/DataStore"

bus = dbus.SessionBus()
proxy = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
data_store = dbus.Interface(proxy, DS_DBUS_INTERFACE)

for i in range(0, 10):
   resultset, count = data_store.find({}, ['uid'])
   print count
   for doc in resultset:
       newdoc = data_store.get_properties(result['uid'])
       # TODO: Give it a new name, make a copy 
       # of the actual files related to this doc.
       data_store.create(newdoc, '', True)
