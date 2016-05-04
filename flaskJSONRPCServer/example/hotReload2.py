# -*- coding: utf-8 -*-
import sys, time, random, os

"""
This example show how to reload API without restarting server.
This function fully safe, waits for completing old requests,
optionally has timeout and ability for overloading variables.

This version show, how also overload globals().
"""

from flaskJSONRPCServer import flaskJSONRPCServer

def stats(_connection=None):
   # return server's speed stats
   return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

def testFunc2(s):
   # this function called from dispatchers
   return 'From original: %s'%s

def testForReload1(_connection=None):
   # this method can be reloaded with reloadApi()
   s=42
   return testFunc2(s)

def testForReload2(_connection=None):
   # this method not reloaded with reloadApi(), but call same function testFunc2()
   s=42
   return testFunc2(s)

# dispatcher for reloading, call him
def reloadApi(globally=False, _connection=None):
   # callback for overloading globals
   def callbackForManualOverload(server, module, dispatcher):
      if not globally: return
      # overload globals also
      for k in dir(module):
         globals()[k]=getattr(module, k)
   # what we want to reload
   data=[
      {'dispatcher':'testForReload1', 'scriptPath':_connection.server._getScriptPath(True), 'isInstance':False,'overload':[{}, callbackForManualOverload], 'path':'/api'}
   ]
   # <clearOld>   if True, all existing dispatchers will be removed
   # <timeout>    is how long (in seconds) we wait for compliting all existing requests
   _connection.server.reload(data, clearOld=False)

if __name__=='__main__':
   print 'Running api..'
   # Creating instance of server
   #    <blocking>         switch server to sync mode when <gevent> is False
   #    <cors>             switch auto CORS support
   #    <gevent>           switch to using Gevent as backend
   #    <debug>            switch to logging connection's info from Flask
   #    <log>              switch to logging debug info from flaskJSONRPCServer
   #    <fallback>         switch auto fallback to JSONP on GET requests
   #    <allowCompress>    switch auto compression
   #    <compressMinSize>  set min limit for compression
   #    <tweakDescriptors> set descriptor's limit for server
   #    <jsonBackend>      set JSON backend. Auto fallback to native when problems
   #    <notifBackend>     set backend for Notify-requests
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=False, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000])
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api')
   server.registerFunction(reloadApi, path='/api')
   server.registerFunction(testForReload1, path='/api')
   server.registerFunction(testForReload2, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
