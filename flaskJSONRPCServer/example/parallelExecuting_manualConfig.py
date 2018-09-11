# -*- coding: utf-8 -*-
import sys, time, random, os

from flaskJSONRPCServer import flaskJSONRPCServer
from flaskJSONRPCServer.execBackend import execBackend_parallelWithSocket, execBackend_parallelWithSocketNew

def slowTest(__=None):
   s=2
   for i in xrange(30):
      s=s**2
   __.call.log('>> slowTest complited!')
   return 'ok'

def bigData(__=None):
   __.call.log('>> before sending to parent')
   __.call.eval('len("%s")'%('test'*(100*1024*1024)))
   __.call.log('>> after sending to parent')
   return True

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
   """
   Testing default locking, you can see how it works with parallel exec-backend.
   """
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

class testIPCFlag:
   """
   Testing IPCFlag (with async mode), also supports 'simple' exec-backend.
   """
   def capture(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      call.IPCFlagCapture(id, limit=2)
      return 'Captured (%s): %s'%(parallelId, call.IPCFlagGet(id))

   def release(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      call.IPCFlagRelease(id)
      return 'Released (%s): %s'%(parallelId, call.IPCFlagGet(id))

   def clear(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      call.IPCFlagClear(id)
      return 'Cleared (%s): %s'%(parallelId, call.IPCFlagGet(id))

   def get(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      return 'Value (%s): %s'%(parallelId, call.IPCFlagGet(id))

   def check(self, id='test', val=2, __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      call.IPCFlagCheck(id, value=val)
      return 'Waiting ended (%s): %s'%(parallelId, call.IPCFlagGet(id))

   def captureAsync(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      def tFunc(result, error, lockId):
         print 'CaptureAsync ended (%s): %s'%(parallelId, call.IPCFlagGet(lockId))
      call.IPCFlagCaptureAsync(id, tFunc, limit=2)

   def releaseAsync(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      def tFunc(result, error, lockId):
         print 'ReleaseAsync ended (%s): %s'%(parallelId, call.IPCFlagGet(lockId))
      call.IPCFlagReleaseAsync(id, tFunc)

   def clearAsync(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      def tFunc(result, error, lockId):
         print 'ClearAsync ended (%s): %s'%(parallelId, call.IPCFlagGet(lockId))
      call.IPCFlagClearAsync(id, tFunc)

   def getAsync(self, id='test', __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      def tFunc(result, error, lockId):
         print 'GetAsync ended (%s): %s'%(parallelId, call.IPCFlagGet(lockId))
      call.IPCFlagGetAsync(id, tFunc)

   def checkAsync(self, id='test', val=2, __=None):
      call=__.myExecBackend if __.execBackendId=='simple' else __.call
      parallelId='simple' if __.execBackendId=='simple' else __.parallelId
      def tFunc(result, error, lockId):
         print 'CheckAsync ended (%s): %s'%(parallelId, call.IPCFlagGet(lockId))
      call.IPCFlagCheckAsync(id, tFunc, value=val)

if __name__=='__main__':
   print 'Running api..'
   # create and manually config execBackends
   #    <id>                        unique ID of backend
   #    <poolSize>                  count of child processes
   #    <saveResult>                switch notify-requests mode. for using like notifBackend set to False
   #    <overloadMagicVarInParent>  add special, backend-specific, methods to dispatchers, executed in parent process
   # with this settings you can run method slowTest() that executing long time and parallely run another method (for example echo()). they will executing in different processes
   myExecBackend=execBackend_parallelWithSocketNew(id='myExecBackend', poolSize=2, overloadMagicVarInParent=True, saveResult=True)
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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', tweakDescriptors=[1000, 1000], dispatcherBackend=myExecBackend, experimental=True, magicVarForDispatcher='__', servBackend='auto')
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api', dispatcherBackend='simple')
   server.registerFunction(stats, path='/api', name='stats2')

   server.registerFunction(slowTest, path='/api')
   server.registerFunction(testLong, path='/api')
   server.registerFunction(bigData, path='/api')
   server.registerFunction(sleepTest, path='/api')
   server.registerFunction(echo, path='/api')
   server.registerFunction(echo, path='/api', name='echo2', dispatcherBackend='simple')
   server.registerInstance(testLocking(), path='/api')
   server.registerInstance(testIPCFlag(), path='/ipc')
   server.registerInstance(testIPCFlag(), path='/ipc2', dispatcherBackend='simple')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
