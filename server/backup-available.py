# this is not a cgi script
# will only work as a mod_wsgi handler

import os
import re
import pwd
import random

HTTP_OK = "200 OK"
HTTP_SERVICE_UNAVAILABLE = "503 SERVICE_UNAVAILABLE"
HTTP_FORBIDDEN = "403 FORBIDDEN"

class Debugger:

    def __init__(self, object):
        self.__object = object
        print("got to debugger class")

    def __call__(self, *args, **kwargs):
        import pdb, sys
        debugger = pdb.Pdb()
        debugger.use_rawinput = 0
        debugger.reset()
        sys.settrace(debugger.trace_dispatch)

        try:
            return self.__object(*args, **kwargs)
        finally:
            debugger.quitting = 1
            sys.settrace(None)

def application(environ, callback):
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', '0')]

    recentclientsdir = '/var/lib/ds-backup/recentclients'
    basehomedir = '/library/users'

    # max 5% loadavg
    if (os.getloadavg()[0] > 5):
        callback(HTTP_SERVICE_UNAVAILABLE, response_headers)
        return ['']

    # we need at least a few blocks...
    libstat = os.statvfs(basehomedir);
    usedblockspc = 1 - float(libstat[4])/libstat[2]
    usedfnodespc = 1 - float(libstat[7])/libstat[5]
    if (usedblockspc > 0.9 or usedfnodespc > 0.9):
        callback(HTTP_SERVICE_UNAVAILABLE, response_headers)
        return ['']

    # Limit concurrent rsync clients
    # We touch a file with the client identifier
    # every time we reply with a 200 OK. So
    # we can check for recent "OKs".
    # (clients that retry the rsync transfer won't
    #  re-request this url, anyway.)
    clientcount = os.system('find ' + recentclientsdir +
                            ' -mmin -5 -type f | wc -l');
    if (clientcount > 10 ):
        callback(HTTP_SERVICE_UNAVAILABLE, response_headers)
        return ['']

    # Read the XO SN
    pathinfo = environ['PATH_INFO']
    print("pathinfo:%s"%pathinfo)
    m = re.match('/available/(\w+)$', pathinfo)
    if (m):
        # req.log_error(clientid)
        clientid = m.group(1)
    else:
        # We don't like your SN
        callback(HTTP_FORBIDDEN, response_headers)
        return ['']

    # Have we got a user acct for the user?
    try:
        homedir = pwd.getpwnam(clientid)[5]
    except KeyError:
        callback(HTTP_FORBIDDEN, response_headers)

    # check the homedir is in the right place
    m = re.match(basehomedir, homedir)
    if (not m):
        callback(HTTP_FORBIDDEN, response_headers)
        return ['']

    #return apache.HTTP_UNAUTHORIZED
    #return apache.HTTP_FORBIDDEN
    #return apache.HTTP_VERSION_NOT_SUPPORTED
    #

    os.system('touch ' + recentclientsdir + '/' + clientid)
    # TODO: 1 in 10, cleanup recentclients dir
    if (random.randint(0,10) == 1):
        os.system('find ' + recentclientsdir + ' -type f -mmin +10 -print0 | xargs -0 -n 100 --no-run-if-empty rm' )

    status = HTTP_OK
    print("status return:%s"%status)
    callback(status, response_headers)
    return ['']

# to debug this wsgi stub, uncomment the following and run "httpd -X" at the server
#application = Debugger(application)
if __name__ == "__main__" :
    #inv_dict = {"PATH_INFO":"available"}
    #application(inv_dict, start_response)
    pass
