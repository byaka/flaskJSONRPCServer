# -*- coding: utf-8 -*-
import sys, time, random

"""
This example show how to use notify backend for fully support "Notify-requests" (without id).
Without it client must wait for completing processing of request.
But with backend, "Notify-requests" processing in background and server simply closes client's connection.
"""

from flaskJSONRPCServer import flaskJSONRPCServer

class mySharedMethods:
   def random(self, mult=65536):
      # Sipmly return random value (0..mult)
      return int(random.random()*mult)

def block(_connection):
   # Test for notification request. When it fully implemented, client must  not wait for compliting this function
   _connection.call.sleep(2) #this contain time.sleep() patched if needed and always safely
   time.sleep(2) #but in common cases this work too
   # or you can auto patch your scope
   # _connection.server._importThreading(scope=globals())
   print 'ok'

def stats(_connection=None):
   #return server's speed stats
   return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=False, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='threadPoolNative', tweakDescriptors=[1000, 1000])
   # Register dispatcher for all methods of instance
   server.registerInstance(mySharedMethods(), path='/api')
   # Register dispatchers for single functions
   server.registerFunction(block, path='/api')
   server.registerFunction(stats, path='/api')
   # Run server
   server.start() #don't join to event loop, so we can do anything else

   # run another server but with different notifBackend
   server=flaskJSONRPCServer(("0.0.0.0", 7002), blocking=False, cors=True, gevent=True, debug=False, log=False, fallback=True, allowCompress=False, notifBackend='simple')
   server.registerInstance(mySharedMethods(), path='/api')
   server.registerFunction(block, path='/api')
   server.registerFunction(stats, path='/api')
   server.serveForever()
   # now you can test and see the difference!
