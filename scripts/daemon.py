#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Ohmcoin Simple Web Server
# Copyright (c) 2020 Cryptech Services (squidicuz)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__author__ = "squidicuz (Jon O)"
__copyright__ = "Copyright 2020, Cryptech Services"
__credits__ = ["RasAlGhul", "SeqSEE"]
__license__ = "MIT"
__version__ = "1.2.1"
__maintainer__ = "squidicuz"
__email__ = "squid@sqdmc.net"
__status__ = "Development"

import cherrypy
import json
import os
import sys
import time
import smtplib
import hashlib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pathlib import Path


# Main ohm web object
class OhmRoot(object):

    COOLDOWN_TIME_IP = 3  # time in seconds between mail attempts per ip..
    COOLDOWN_TIME = 120  # time in seconds between mail attempts per session..
    hostsAgents = {}  # map of host sessions and last mail times.
    hosts = {}  # map of host sessions and last mail times.
    cacheHeight = {}  # map for cache of height
    cacheBlocks = {}  # map for cache of block
    cacheConnct = {}  # map for cache of connections

    ###########################################################################
    def __init__(self, config, debug, vdebug):
        self.debug = debug;
        self.verbose = vdebug;
        self.conf = config;
        self.version = self.conf['version']
        self.localDir = self.conf['localdir']
        self.pubDir = self.localDir + "/public"
        self.COOLDOWN_TIME_IP = self.conf['mail']['cooldownhost']
        self.COOLDOWN_TIME = self.conf['mail']['cooldownagent']
        print( "Root Directory: " + self.localDir )
        print( "Public Directory: " + self.pubDir )
        print( "[RPC BIND] " + "http://" + self.conf['rpc']['server']  + ":" + self.conf['rpc']['port'] + "/" )
        # Setup Custom Error Pages
        self._cp_config = {'error_page.404': os.path.join(self.pubDir, "error/404.html"), 'error_page.403': os.path.join(self.pubDir, "error/403.html"), 'error_page.500': os.path.join(self.pubDir, "error/500.html")}

    @cherrypy.expose
    def index(self):
        message = { "response" : True, "status" : True, "message" : "Not a web server. This method is restricted." }
        return json.dumps(message)

    @cherrypy.expose
    def contact_submit(self):
        if (cherrypy.request.method == "GET") :
            message = { "response" : True, "status" : False, "message" : "post required.." }
            return json.dumps(message)
        # setup default vars
        body = json.loads("{}")
        remoteHost = "127.0.0.1"
        userAgent = "1"
        agentHash = "0"
        hostHash = "0"
        # load form data
        try:
            cl = cherrypy.request.headers['Content-Length']
            rawbody = cherrypy.request.body.read(int(cl))
            body = json.loads(rawbody)
            remoteHost = cherrypy.request.headers['X-FORWARDED-FOR']
            userAgent = cherrypy.request.headers['USER-AGENT']
            # get agent hashes..
            agentHash = self.getHostHash(remoteHost, userAgent)
            hostHash = self.getHostHash(remoteHost, 0)
        except Exception as ex:
            print("ERROR: " + ex)
            message = { "response" : False, "status" : False, "message" : "input error.." }
            return json.dumps(message)
        # Check if spam..
        if self.allowHost(hostHash) == False:
            message = { "response" : False, "status" : True, "message" : "you are doing this too often!!" }
            return json.dumps(message)
        elif remoteHost == "127.0.0.1":
            message = { "response" : False, "status" : False, "message" : "host invalid.." }
            return json.dumps(message)
        else:
            self.addHost(hostHash)
        # clean up old agent trackings..
        self.cleanHostAgents()
        # process form data..
        try:
            if 'g-recaptcha-response' in body:
                captcha = body['g-recaptcha-response']
            else:
                captcha = "NA"
            name = body['Name']
            email = body['Email']
            message = body['Message']
        except Exception as ex:
            print("ERROR: " + ex)
            message = { "response" : False, "status" : False, "message" : "input error.." }
            return json.dumps(message)
        # log to console..
        print ( "RECEIVED CONTACT FROM: " + email + "  MESSAGE: " + message )
        # Check if can send..
        if self.allowAgent(agentHash):
            dateTimeObj = datetime.now()  # current time
            # build email body..
            msg = "\nUSER HOST: " + hostHash + "\nUSER AGENT: " + agentHash + "\nSERVER TIME: " + str(dateTimeObj) + "\n\nFROM NAME: " + name + "\nFROM EMAIL: " + email + "\n\nMESSAGE:\n" + message + "";
            # send mail
            self.sendMail(name, email, msg)
            # track host..
            self.addAgent(agentHash)
            # log to file..
            file1 = open("contact.log", "a")  # append mode
            file1.write(str(dateTimeObj) + " > " + "NAME: " + name + ", EMAIL: " + email + ", MESSAGE: " + message + "\n")
            file1.close()
            # send response
            message = { "response" : True, "status" : True, "message" : "message sent!", "retry" : 0 , "id" : agentHash }
            return json.dumps(message)
        else:
            # send response
            message = { "response" : False, "status" : True, "message" : "you are doing this too often!", "retry" : self.getAgentTime(agentHash), "id" : agentHash }
            return json.dumps(message)

    ###########################################################################
    # API Functions..
    @cherrypy.expose
    def getblockheight(self):
        try:
            if self.allowHeightCache():
                method = "getblockcount"
                params = []
                hh = self.doRpcRequest(method, params)
                height = hh['result']
                self.addHeightCache(height)
            else:
                height = self.getHeightCacheVal()
            retry = self.getHeightCacheTime()
        except Exception as ex:
            print("Failed to fetch Height!")
            print(ex)
            return "error"
        return json.dumps({"height": height, "refreshtime" : retry })

    @cherrypy.expose
    def getconnectioncount(self):
        try:
            if self.allowHeightCache():
                method = "getconnectioncount"
                params = []
                cc = self.doRpcRequest(method, params)
                conns = cc['result']
                self.addConnsCache(conns)
            else:
                conns = self.getConnsCacheVal()
            retry = self.getConnsCacheTime()
        except Exception as ex:
            print("Failed to fetch Connection count!")
            print(ex)
            return "error"
        return json.dumps({"connections": conns, "refreshtime" : retry })

    @cherrypy.expose
    def getbestblock(self):
        try:
            if self.allowBlockCache():
                method = "getblockcount"
                params = []
                hh = self.doRpcRequest(method, params)
                height = hh['result']
                self.addHeightCache(height, False)
                method = "getblockhash"
                params = [ height ]
                bb = self.doRpcRequest(method, params)
                blockh = bb['result']
                self.addBlockCache(blockh)
            else:
                height = self.getHeightCacheVal()
                blockh = self.getBlockCacheVal()
            retry = self.getBlockCacheTime()
        except Exception as ex:
            print("Failed to fetch Block!")
            print(ex)
            return "error"
        return json.dumps({ "blockhash": blockh, "height": height, "refreshtime" : retry })

    ###########################################################################
    # Send Email message
    def sendMail(self, name, email, message):
        xfrom = self.conf['mail']["systemfrom"]
        xfromName = self.conf['mail']["sysnamefrom"]
        xto = self.conf['mail']["fowardto"]
        # build the message
        msg = MIMEText(message)
        msg['Subject'] = "[" + "socialsend.io" + "] New Message from '" + name + "'"
        msg['From'] = formataddr((str(Header(xfromName, 'utf-8')), xfrom))
        msg['To'] = xto
        # Send mail..
        s = smtplib.SMTP('localhost')
        s.sendmail(xfrom, xto, msg.as_string())
        s.quit()
        print( "Mail Sent!" )

    # Host Agent cleaner
    def cleanHostAgents(self):
        hosts = []
        agents = []
        # Clean Hosts
        for key in self.hosts:
            if self.getHostTime(key) <= -30:
                hosts.append(key)
        for key in hosts:
            self.hosts.pop(key)
            print( "> Removed Expired Host " + key )
        # Clean Agents
        for key in self.hostsAgents:
            if self.getAgentTime(key) <= -30:
                agents.append(key)
        for key in agents:
            self.hostsAgents.pop(key)
            print( "> Removed Expired Agent " + key )

    # Hosts
    def addHost(self, host):
        ts = time.time()
        self.hosts[host] = ts

    def getHost(self, host):
        if host in self.hosts:
            return self.hosts[host];
        return 0

    def allowHost(self, host):
        ts = time.time()
        th = self.getHost(host)
        if (th <= 0) :
            return True
        return ts - th > self.COOLDOWN_TIME_IP

    def getHostTime(self, host):
        ts = time.time()
        th = self.getHost(host)
        if (th <= 0) :
            return 0
        return self.COOLDOWN_TIME_IP - (ts - th)

    # User Agents
    def addAgent(self, host):
        ts = time.time()
        self.hostsAgents[host] = ts

    def getAgent(self, host):
        if host in self.hostsAgents:
            return self.hostsAgents[host];
        return 0

    def allowAgent(self, host):
        ts = time.time()
        th = self.getAgent(host)
        if (th <= 0) :
            return True
        return ts - th > self.COOLDOWN_TIME

    def getAgentTime(self, host):
        ts = time.time()
        th = self.getAgent(host)
        if (th <= 0) :
            return 0
        return self.COOLDOWN_TIME - (ts - th)

    # Gets hash of host or agent
    def getHostHash(self, host, client):
        h = str(host);
        c = str(client);
        return hashlib.sha256(str(h + "::" + c).encode('utf-8')).hexdigest()

    # Do RPC request
    def doRpcRequest(self, method, params):
        server = self.conf['rpc']['server']
        port = self.conf['rpc']['port']
        user = self.conf['rpc']['username']
        pazz = self.conf['rpc']['password']
        url = 'http://' + server + ':' + port
        payload = json.dumps({" jsonrpc": "2.0", "id": "pycurl", "method": method, "params": params })
        headers = { 'content-type': 'application/json' }
        if (self.debug == True):
            print( "RPC Request= " + str(payload) )
        r = requests.post(url, data=payload, headers=headers, auth=(user, pazz))
        respj = r.json()
        return respj

    # RPC Height Caching
    def addHeightCache(self, value, updatetime = True):
        host = "local"
        if updatetime == True:
            ts = time.time()
            self.cacheHeight[host] = ts
        self.cacheHeight[host + '_val'] = value

    def getHeightCache(self):
        host = "local"
        if host in self.cacheHeight:
            return self.cacheHeight[host];
        return 0

    def getHeightCacheVal(self):
        host = "local_val"
        if host in self.cacheHeight:
            return self.cacheHeight[host];
        return 0

    def allowHeightCache(self):
        ts = time.time()
        th = self.getHeightCache()
        if (th <= 0) :
            return True
        return ts - th > 16

    def getHeightCacheTime(self):
        ts = time.time()
        th = self.getHeightCache()
        if (th <= 0) :
            return 0
        return 16 - (ts - th)

    # RPC Blocks Caching
    def addBlockCache(self, value):
        host = "local"
        ts = time.time()
        self.cacheBlocks[host] = ts
        self.cacheBlocks[host + '_val'] = value

    def getBlockCache(self):
        host = "local"
        if host in self.cacheBlocks:
            return self.cacheBlocks[host];
        return 0

    def getBlockCacheVal(self):
        host = "local_val"
        if host in self.cacheBlocks:
            return self.cacheBlocks[host];
        return 0

    def allowBlockCache(self):
        ts = time.time()
        th = self.getBlockCache()
        if (th <= 0) :
            return True
        return ts - th > 20

    def getBlockCacheTime(self):
        ts = time.time()
        th = self.getBlockCache()
        if (th <= 0) :
            return 0
        return 20 - (ts - th)

    # RPC Connections Caching
    def addConnsCache(self, value):
        host = "local"
        ts = time.time()
        self.cacheConnct[host] = ts
        self.cacheConnct[host + '_val'] = value

    def getConnsCache(self):
        host = "local"
        if host in self.cacheConnct:
            return self.cacheConnct[host];
        return 0

    def getConnsCacheVal(self):
        host = "local_val"
        if host in self.cacheConnct:
            return self.cacheConnct[host];
        return 0

    def allowConnsCache(self):
        ts = time.time()
        th = self.getConnsCache()
        if (th <= 0) :
            return True
        return ts - th > 42

    def getConnsCacheTime(self):
        ts = time.time()
        th = self.getConnsCache()
        if (th <= 0) :
            return 0
        return 42 - (ts - th)

# Loads the config from file into dict
def loadConf(dir):
    try:
        confpath = dir + '/.env/conf.json'
        data = json.loads("{}")
        with open(confpath) as f:
            data = json.load(f)
        version = data['CONFIG'][0]['Version']
        username = data['CONFIG'][1]['RPC'][0]['Username']
        password = data['CONFIG'][1]['RPC'][0]['Password']
        server = data['CONFIG'][1]['RPC'][0]['Server']
        port = data['CONFIG'][1]['RPC'][0]['Port']
        sysfrm = data['CONFIG'][2]['EMAIL'][0]['SystemFrom']
        sysnmefrm = data['CONFIG'][2]['EMAIL'][0]['SystemFromName']
        fwdto = data['CONFIG'][2]['EMAIL'][0]['FowardTo']
        chost = data['CONFIG'][3]['XDOS'][0]['CooldownTimeHost']
        cagnt = data['CONFIG'][3]['XDOS'][0]['CooldownTimeAgent']
        cherrysrv = data['CONFIG'][4]['HTTP'][0]['Server']
        cherryprt = data['CONFIG'][4]['HTTP'][0]['Port']
        rpc = { "username" : username, "password" : password, "server" : server, "port" : port }
        mail = { "fowardto" : fwdto, "systemfrom" : sysfrm, "sysnamefrom" : sysnmefrm, "cooldownhost" : chost, "cooldownagent" : cagnt}
        srvr = { "server": cherrysrv, "port": cherryprt }
        item = { "version" : version, "rpc" : rpc, "mail" : mail, "web" : srvr, 'localdir' : dir }
        print("Config Loaded! Version " + version)
        return item
    except Exception as ex:
        print("Config Loading Error!  " + ex)
        return {}

def main():
    conf = setup();
    print( "Prod Daemon Started!" )
    # start the webserver!
    cherrypy.quickstart( OhmRoot(conf, False, False) )

def debug():
    conf = setup();
    print( "Debug Daemon Started!" )
    # start the webserver!
    cherrypy.quickstart( OhmRoot(conf, True, False) )

def dev():
    conf = setup();
    print( "Dev Daemon Started!" )
    # start the webserver!
    cherrypy.quickstart( OhmRoot(conf, True, True) )

def setup():
    print( "Starting..." )
    localDir = str(Path(os.path.dirname(os.path.realpath(__file__))).resolve().parent)
    if os.path.exists(localDir + "/.env") == False or os.path.exists(localDir + "/.env/" + "conf.json") == False:
        if os.path.exists(localDir + "/.env") == False:
            os.mkdir(localDir + "/.env")
            print( "Created '.env' Directory!" )
        print( "ERROR!! Configuration File 'conf.json' was not found or is invalid!" )
        print( "Run Aborted!" )
        sys.exit()
        return
    conf = loadConf(localDir)
    print( "Binding HTTP Server Listener on " + str(conf['web']['server']) + ":" + str(conf['web']['port']) )
    # listen on all interfaces
    cherrypy.server.socket_host = conf['web']['server']
    # listen on alt port
    cherrypy.server.socket_port = conf['web']['port']
    return conf

def shutdown():
    print("Shutdown Signal Sent!")
    time.sleep(1)
    cherrypy.engine.exit()
    time.sleep(2)

###############################################################################
if __name__ == '__main__':
    args = sys.argv[1:];
    if len(args) > 0:
        if args[0] == '-m' and len(args) > 1:
            if args[1] == 'prod':
                main()
                exit()
            elif args[1] == 'debug':
                debug()
                exit()
            elif args[1] == 'develop' or args[1] == 'dev':
                debug()
                exit()
            else:
                print("MODE ARGS: prod|debug|develop")
        elif args[0] == '-r':
            main()
            exit()
        elif args[0] == '-s' or args[0] == '-stop':
            shutdown()
            exit()
        elif args[0] == '-help' or args[0] == '-h' or args[0] == '?':
            print( "================ Ohm Web Daemon Commands ================" )
            print( "> daemon.py -r         - Runs the daemon normally (production)" )
            print( "> daemon.py -s         - Stops the daemon safely" )
            print( "> daemon.py -m prod    - Runs the daemon in production mode" )
            print( "> daemon.py -m debug   - Runs the daemon is debug mode" )
            print( "> daemon.py -m dev     - Runs the daemon is development mode" )
            exit()
    print("COMMAND HELP: daemon.py ?")
