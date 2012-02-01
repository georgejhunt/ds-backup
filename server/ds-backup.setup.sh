#!/bin/bash
DATADIR=/usr/share/ds-backup

ln -sf $DATADIR/apache-ds-backup.conf /etc/httpd/conf.d/050-ds-backup.conf
ln -sf $DATADIR/cron-ds-backup-server.conf /etc/cron.d/ds-backup-server.conf

# incrond doesn't accept symlinks
cp -f $DATADIR/incron-ds-backup.conf /etc/incron.d/ds-backup.conf

service httpd condrestart
