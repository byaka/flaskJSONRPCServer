# -*- coding: utf-8 -*-
import sys, time, random, os

from flaskJSONRPCServer import flaskJSONRPCServer
from flaskJSONRPCServer.execBackend import execBackend_parallelWithSocket

def slowTest(__=None):
   s=2
   for i in xrange(30):
      s=s**2
   __.call.log('>> slowTest complited!')
   return 'ok'

def bigData():
   return 'test'*(10*1024*1024)

def testLong():
   # throw exception, see https://github.com/byaka/flaskJSONRPCServer/issues/78
   return 2**64

def sleepTest(__=None):
   __.call.log('>> before sleep')
   __.call.sleep(5)
   __.call.log('>> after sleep')
   return 'ok'

def echo(data='Hello world', __=None):
   if __.notify: __.call.log(data)
   return data

def stats(__=None):
   #return server's speed stats
   return __.server.stats(inMS=False) #inMS=True return stats in milliseconds

class testLocking:
   def lockFor(self, n=5, andUnlockEcho=False, __=None):
      __.call.lock()
      if andUnlockEcho:
         #but unlock 'echo' dispatcher
         __.call.unlock(dispatcher=echo, exclusive=True)
      __.call.log('LOCKED!')
      #now all server locked
      __.call.sleep(n)
      __.call.unlock()
      if andUnlockEcho:
         #return to normal state
         __.call.unlock(dispatcher=echo)
      __.call.log('UNLOCKED!')

if __name__=='__main__':
   print 'Running api..'
   # create and manually config execBackends
   #    <id>               unique ID of backend
   #    <poolSize>         count of child processes
   #    <saveResult>       switch notify-requests mode. for using like notifBackend set to False
   # with this settings you can run method slowTest() that executing long time and parallely run another method (for example echo()). they will executing in different processes
   myExecBackend=execBackend_parallelWithSocket(id='myExecBackend', saveResult=True, poolSize=2)
   myNotifBackend=execBackend_parallelWithSocket(id='myNotifBackend', saveResult=False, poolSize=2)
   # Creating instance of server
   #    <blocking>         switch server to one-request-per-time mode
   #    <cors>             switch auto CORS support
   #    <gevent>           switch to patching process with Gevent
   #    <debug>            switch to logging connection's info from serv-backend
   #    <log>              set logging level (0-critical, 1-errors, 2-warnings, 3-info, 4-debug)
   #    <fallback>         switch auto fallback to JSONP on GET requests
   #    <allowCompress>    switch auto compression
   #    <compressMinSize>  set min limit for compression
   #    <tweakDescriptors> set file-descriptor's limit for server (useful on high-load servers)
   #    <jsonBackend>      set JSON-backend. Auto fallback to native when problems
   #    <notifBackend>     set exec-backend for Notify-requests
   #    <servBackend>      set serving-backend ('pywsgi', 'werkzeug', 'wsgiex' or 'auto'). 'auto' is more preffered
   #    <experimental>     switch using of experimental perfomance-patches
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', tweakDescriptors=[1000, 1000], dispatcherBackend=myExecBackend, notifBackend=myNotifBackend, experimental=True, magicVarForDispatcher='__', servBackend='auto')
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api', dispatcherBackend='simple')

   server.registerFunction(slowTest, path='/api')
   server.registerFunction(testLong, path='/api')
   server.registerFunction(bigData, path='/api')
   server.registerFunction(sleepTest, path='/api')
   server.registerFunction(echo, path='/api')
   server.registerInstance(testLocking(), path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
