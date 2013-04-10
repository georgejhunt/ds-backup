NAME=ds-backup
VERSION = $(shell git describe | sed 's/^v//' | sed 's/-/./g')
RELEASE = 1
ARCH = noarch
BRANCH = $(shell git branch | grep '*' | sed 's/* //')

NV = $(NAME)-$(VERSION)
REL = 1

# rpm target directory
BUILDDIR = $(HOME)/rpmbuild

SOURCES: Makefile
	mkdir -p $(BUILDDIR)/BUILD $(BUILDDIR)/RPMS \
	$(BUILDDIR)/SOURCES $(BUILDDIR)/SPECS $(BUILDDIR)/SRPMS
	mkdir -p $(NV)
	git archive --format=tar --prefix="$(NV)/" HEAD > $(NV).tar
	echo $(VERSION) > $(NV)/build-version
	tar -rf $(NV).tar $(NV)/build-version
	#rm -fr $(NV)
	gzip  $(NV).tar
	mv $(NV).tar.gz $(BUILDDIR)/SOURCES/

ds-backup.spec: ds-backup.spec.in
	sed -e 's:@VERSION@:$(VERSION):g' < $< > $@

.PHONY: ds-backup.spec.in
	# This forces a rebuild of ds-backup.spec.in

RPMBUILD = rpmbuild \
	--define "_topdir $(BUILDDIR)" \

rpm: SOURCES $(NAME).spec
	$(RPMBUILD) -ba --target $(ARCH) $(NAME).spec

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
