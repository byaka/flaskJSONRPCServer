# -*- coding: utf-8 -*-
import sys, time, random, os

from flaskJSONRPCServer import flaskJSONRPCServer
from flaskJSONRPCServer.execBackend import execBackend_parallelWithSocket

def slowTest(_connection=None):
   s=2
   for i in xrange(30):
      s=s**2
   _connection.call.log('>> slowTest complited!')
   return 'ok'

def sleepTest(_connection=None):
   _connection.call.log('>> before sleep')
   _connection.call.sleep(5)
   _connection.call.log('>> after sleep')
   return 'ok'

def echo(data='Hello world', _connection=None):
   if _connection.notify: _connection.call.log(data)
   return data

def stats(_connection=None):
   #return server's speed stats
   return _connection.server.stats(inMS=False) #inMS=True return stats in milliseconds

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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', tweakDescriptors=[1000, 1000], dispatcherBackend=myExecBackend, notifBackend=myNotifBackend, experimental=True)
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api', dispatcherBackend='simple')

   server.registerFunction(slowTest, path='/api')
   server.registerFunction(sleepTest, path='/api')
   server.registerFunction(echo, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
