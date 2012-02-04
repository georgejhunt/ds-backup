Name:           ds-backup
Version:        xx
Release:        1%{?dist}

Summary:        OLPC DS backup & restore scripts
Group:          Applications/Archiving
License:        GPLv2
URL:            http://wiki.laptop.org/go/Ds-backup
Source0:        http://dev.laptop.org/git/users/martin/%{name}.git/snapshot/%{name}-%{version}.tar.bz2
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
BuildRequires:  make
BuildRequires:  python

%description
ds-backup is a GPL-licensed collection of scripts for backing up and restoring
OLPC DataStore objects and metadata.

# - Dependencies of the client package are rsync, sugar-datastore,
# sugar, crond, and the python libs sha, urllib2. Everything else I
# think is pulled in by standard base or python-base

%package client

Summary:        OLPC DS backup & restore client
Group:          Applications/Archiving

Requires:       python
Requires:       rsync
Requires:       sugar-datastore
Requires:       sugar
Requires:       vixie-cron

%package server

Summary:        OLPC DS backup & restore server
Group:          Applications/Archiving

Requires:       xs-config
Requires:       mod_python
Requires:       python
Requires:       rsync
Requires:       vixie-cron
Requires:       incron
Requires:       php
Requires:       httpd
Requires:       syck-python

%description client
ds-backup-client is a GPL-licensed collection of scripts for backing up and
restoring OLPC DataStore objects and metadata.

%description server
ds-backup-server is a GPL-licensed collection of scripts for backing up and
restoring OLPC DataStore objects and metadata.

%prep
%setup -q


%build


%install
rm -rf $RPM_BUILD_ROOT
make -f Makefile install DESTDIR=$RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT

%post server
service httpd condrestart

%files client
%defattr(-,root,root,-)
%doc README COPYING AUTHORS
%config %{_sysconfdir}/cron.d/ds-backup
%{_bindir}/ds-backup.py
%{_bindir}/ds-backup.sh

%files server
%defattr(-,root,root,-)
%doc README COPYING AUTHORS
%{_datadir}/%{name}
%{_sysconfdir}/sysconfig/olpc-scripts/setup.d/*
%{_bindir}/ds-postprocess.py
%{_bindir}/ds-cleanup.sh
%{_bindir}/ds-cleanup.py
/var/www/ds-backup/*
%attr(700, apache, apache) %dir %{_localstatedir}/lib/ds-backup/recentclients
%attr(777, nobody, nobody) %dir %{_localstatedir}/lib/ds-backup/completion

%changelog
* Fri Jul 18 2008 Martin Langhoff <martin@laptop.org - 0.7-1.olpc3
- Updated server package, several fixes.
- Fixed dependencies: cronie->vixie-cron (which cronie provides on F9)

* Mon Jul 06 2008 Michael Stone <michael@laptop.org> - 0.6-1.olpc3
- Fix dependencies: crond -> cronie.

* Wed Jul 02 2008 Michael Stone <michael@laptop.org> - 0.5-1.olpc3
- Initial release of this spec.
