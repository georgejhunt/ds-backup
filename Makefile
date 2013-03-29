# CANONICAL SOURCE OF VERSION STRING:
VERSION_MAJOR=0
VERSION_MINOR=15
PACKAGE=ds-backup
PKGVER=$(PACKAGE)-$(VERSION_MAJOR).$(VERSION_MINOR)

tarball: $(PKGVER).tar.bz2

$(PKGVER).tar.bz2:
	git diff --shortstat --exit-code # check that our working copy is clean
	git diff --cached --shortstat --exit-code # uncommitted changes?
	git archive --format=tar --prefix=$(PKGVER)/ HEAD | bzip2 > $@
.PHONY: $(PKGVER).tar.bz2 # force refresh

# install targets

install: install-client install-server

install-client:
	install -D -d $(DESTDIR)/usr/bin
	install -D client/ds-backup.py $(DESTDIR)/usr/bin/
	install -D client/ds-backup.sh $(DESTDIR)/usr/bin/
	install -D -d $(DESTDIR)/usr/lib/systemd/system
	install -D -m 644 client/ds-backup.timer $(DESTDIR)/usr/lib/systemd/system/
	install -D -m 644 client/ds-backup.service $(DESTDIR)/usr/lib/systemd/system/

install-server:
	install -D -d $(DESTDIR)/usr/bin
	install -D server/ds-postprocess.py $(DESTDIR)/usr/bin
	install -D server/ds-cleanup.sh $(DESTDIR)/usr/bin
	install -D server/ds-cleanup.py $(DESTDIR)/usr/bin
	install -D -d $(DESTDIR)/var/www/ds-backup
	install -D server/backup-available.py $(DESTDIR)/var/www/ds-backup
	install -D -d $(DESTDIR)/var/lib/ds-backup
	# ownerships are set in the spec file - this execs as nonroot in rpmbuild
	install -D -d $(DESTDIR)/var/lib/ds-backup/recentclients
	# todo: tighten to group ownership
	install -D -d -m 777 $(DESTDIR)/var/lib/ds-backup/completion
	install -D -d $(DESTDIR)/etc/sysconfig/olpc-scripts/setup.d
	install -m 755 server/ds-backup.setup.sh $(DESTDIR)/etc/sysconfig/olpc-scripts/setup.d/ds-backup
	install -D -d $(DESTDIR)/usr/share/ds-backup
	install -m 644 server/incron-ds-backup.conf $(DESTDIR)/usr/share/ds-backup
	install -m 644 server/cron-ds-backup-server.conf $(DESTDIR)/usr/share/ds-backup
	install -m 644 server/apache-ds-backup.conf  $(DESTDIR)/usr/share/ds-backup
