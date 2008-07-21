# this is not a cgi script
# will only work as a mod_python handler

from mod_python import apache
import os
import re
import pwd
import random

def handler(req):

    recentclientsdir = '/var/lib/ds-backup/recentclients'
    basehomedir = '/library/users'

    req.content_type= 'text/plain'

    # max 5% loadavg
    if (os.getloadavg()[0] > 5):
        return apache.HTTP_SERVICE_UNAVAILABLE

    # we need at least a few blocks...
    libstat = os.statvfs(basehomedir);
    usedblockspc = 1 - float(libstat[4])/libstat[2]
    usedfnodespc = 1 - float(libstat[7])/libstat[5]
    if (usedblockspc > 0.9 or usedfnodespc > 0.9):
        return apache.HTTP_SERVICE_UNAVAILABLE

    # Limit concurrent rsync clients
    # We touch a file with the client identifier
    # every time we reply with a 200 OK. So
    # we can check for recent "OKs".
    # (clients that retry the rsync transfer won't
    #  re-request this url, anyway.)
    clientcount = os.system('find ' + recentclientsdir + 
                            ' -mmin -5 -type f | wc -l');
    if (clientcount > 10 ):
        return apache.HTTP_SERVICE_UNAVAILABLE

    # Read the XO SN
    req.add_common_vars()
    pathinfo = req.subprocess_env['PATH_INFO']
    m = re.match('/available/(\w+)$', pathinfo)
    if (m):
        # req.log_error(clientid)
        clientid = m.group(1)
    else:
        # We don't like your SN
        return apache.HTTP_FORBIDDEN
    
    # Have we got a user acct for the user?
    try:
        homedir = pwd.getpwnam(clientid)[5]
    except KeyError:
        return apache.HTTP_FORBIDDEN

    # check the homedir is in the right place
    m = re.match(basehomedir, homedir)
    if (not m):
        return apache.HTTP_FORBIDDEN

    #return apache.HTTP_UNAUTHORIZED
    #return apache.HTTP_FORBIDDEN
    #return apache.HTTP_VERSION_NOT_SUPPORTED
    #
    req.write('')

    os.system('touch ' + recentclientsdir + '/' + clientid)
    # TODO: 1 in 10, cleanup recentclients dir
    if (random.randint(0,10) == 1):
        os.system('find ' + recentclientsdir + ' -type f -mmin +10 -print0 | xargs -0 -n 100 --no-run-if-empty rm' )
    return apache.OK
