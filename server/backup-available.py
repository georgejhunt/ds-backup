# this is not a cgi script
# will only work as a mod_wsgi handler

import os
import re
import pwd
import random

HTTP_OK = 200
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_FORBIDDEN = 403

class BackupRefuse(Exception):
    def __init__(self, status, callback):
        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', '0')]
        callback(status, response_headers)
        return ['']
        
def application(environ, callback):

    recentclientsdir = '/var/lib/ds-backup/recentclients'
    basehomedir = '/library/users'

    # max 5% loadavg
    if (os.getloadavg()[0] > 5):
        raise(BackupRefuse, HTTP_SERVICE_UNAVAILABLE, callback)

    # we need at least a few blocks...
    libstat = os.statvfs(basehomedir);
    usedblockspc = 1 - float(libstat[4])/libstat[2]
    usedfnodespc = 1 - float(libstat[7])/libstat[5]
    if (usedblockspc > 0.9 or usedfnodespc > 0.9):
        raise(BackupRefuse, HTTP_SERVICE_UNAVAILABLE, callback)

    # Limit concurrent rsync clients
    # We touch a file with the client identifier
    # every time we reply with a 200 OK. So
    # we can check for recent "OKs".
    # (clients that retry the rsync transfer won't
    #  re-request this url, anyway.)
    clientcount = os.system('find ' + recentclientsdir + 
                            ' -mmin -5 -type f | wc -l');
    if (clientcount > 10 ):
        raise(BackupRefuse, HTTP_SERVICE_UNAVAILABLE, callback)

    # Read the XO SN
    pathinfo = environ['PATH_INFO']
    print("pathinfo:%s"%pathinfo)
    m = re.match('/available/(\w+)$', pathinfo)
    if (m):
        # req.log_error(clientid)
        clientid = m.group(1)
    else:
        # We don't like your SN
        raise(BackupRefuse, HTTP_FORBIDDEN, callback)
    
    # Have we got a user acct for the user?
    try:
        homedir = pwd.getpwnam(clientid)[5]
    except KeyError:
        raise(BackupRefuse, HTTP_FORBIDDEN, callback)

    # check the homedir is in the right place
    m = re.match(basehomedir, homedir)
    if (not m):
        raise(BackupRefuse, HTTP_FORBIDDEN, callback)

    #return apache.HTTP_UNAUTHORIZED
    #return apache.HTTP_FORBIDDEN
    #return apache.HTTP_VERSION_NOT_SUPPORTED
    #

    os.system('touch ' + recentclientsdir + '/' + clientid)
    # TODO: 1 in 10, cleanup recentclients dir
    if (random.randint(0,10) == 1):
        os.system('find ' + recentclientsdir + ' -type f -mmin +10 -print0 | xargs -0 -n 100 --no-run-if-empty rm' )
    
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', '0')]
    status = HTTP_OK

    callback(status, response_headers)
    return ['']
def start_response(status,header_info):
    print("status:%s.  header_info:%r."%(status,header_info,))

    if __name__ == "__main__" :
        inv_dict = {"PATH_INFO":"available"}
        application(inv_dict, start_response)    

