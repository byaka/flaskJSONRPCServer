# -*- coding: utf-8 -*-
import sys, time, random

"""
This example show how to stop or restart server.
This function fully safe, waits for completing old requests,
optionally has timeout.
"""

from flaskJSONRPCServer import flaskJSONRPCServer

needRestart=False

def echo(data='Hello world!'):
   # Simply echo
   return data
echo._alias='helloworld' #setting alias for method

def restart(_connection=None):
   global needRestart
   # IMPORTANT: you can't use _connection.server.start() from dispatcher
   needRestart=True

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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', dispatcherBackend='simple', notifBackend='simple', tweakDescriptors=[1000, 1000])
   # Register dispatchers for single functions
   server.registerFunction(echo, path='/api')
   server.registerFunction(restart, path='/api')
   # Run server
   server.start()
   # Run cicle, where we check is "restart()" called
   # if you want to use "time.sleep()" instead "server._sleep()" with gevent, call "server._importThreading(scope=globals())" or "server._importAll(scope=globals())"
   if server.setts.gevent: server._importThreading(scope=globals())
   while True:
      time.sleep(5)
      if needRestart:
         needRestart=False
         print 'Restarting..'
         # <timeout> is how long (in seconds) we wait for compliting all existing requests
         # <processingDispatcherCountMax> not wait for some count of executing dispatchers
         server.stop(timeout=5, processingDispatcherCountMax=0) #stop server
         time.sleep(5) #now server stopped, try to request it
         server.start() #start again
         # or you can use server.restart(timeout=5, processingDispatcherCountMax=0)
         print 'ok'
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
