# -*- coding: utf-8 -*-
import sys, time, random, os

from flaskJSONRPCServer import flaskJSONRPCServer

testVar1=1234
testVar2=[1234,4321]
testVar3='12344321'

def testCopyGlobal(_connection=None):
   # get data from global variable
   if _connection.get('parallelType', False):
      s=True
      s1=_connection.call.copyGlobal('testVar1', actual=True)
      # if you need multiple vars, import them at one time
      s2, s3=_connection.call.copyGlobal(['testVar2', 'testVar3'], actual=True)
   else:
      s=False
      s1=testVar1
      s2=testVar2
      s3=testVar3
   return {
      'parallelExec':s,
      'testVar1':s1,
      'testVar2':s2,
      'testVar3':s3
   }

def testChangeGlobal(_connection=None):
   if _connection.get('parallelType', False):
      _connection.call.execute('testVar1=testVar1*2', mergeGlobals=['testVar1']) # if <mergeGlobals> not passed, all globals will be merged. but it's slower, so pass only specific vars
   else:
      global testVar1
      testVar1=testVar1*2

def echo(data='Hello world', _connection=None):
   return data

# dispatcher for reloading, call him
def reloadApi(_connection=None):
   s=[
      {
         # 'scriptPath':None, #if <scriptPath> not passed, path to main script will be used
         'dispatcher':'testCopyGlobal',
         'isInstance':False,
         'path':'/api' # don't forget about API path
      },
      {
         'dispatcher':'testCopyGlobal',
         'isInstance':False,
         'name':'testCopyGlobal2',
         'path':'/api' # don't forget about API path
      }
   ]
   # <clearOld>   if True, all existing dispatchers will be removed
   # <timeout>    how long (in seconds) we wait for compliting all existing requests
   _connection.server.reload(s, clearOld=False, timeout=3)

def stats(_connection=None):
   #return server's speed stats
   return _connection.server.stats(inMS=False) #inMS=True return stats in milliseconds

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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', tweakDescriptors=[1000, 1000], dispatcherBackend='parallelWithSocket', notifBackend='simple', experimental=True)
   # Register dispatchers for single functions
   server.registerFunction(reloadApi, path='/api', dispatcherBackend='simple')
   server.registerFunction(stats, path='/api', dispatcherBackend='simple')

   server.registerFunction(echo, path='/api')
   server.registerFunction(echo, path='/api', dispatcherBackend='simple', name='echo2')

   server.registerFunction(testCopyGlobal, path='/api')
   server.registerFunction(testCopyGlobal, path='/api', dispatcherBackend='simple', name='testCopyGlobal2')

   server.registerFunction(testChangeGlobal, path='/api')
   server.registerFunction(testChangeGlobal, path='/api', dispatcherBackend='simple', name='testChangeGlobal2')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
