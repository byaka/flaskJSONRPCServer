# -*- coding: utf-8 -*-
import sys, time, random, os

import sexyPrime

from flaskJSONRPCServer import flaskJSONRPCServer

needRestart=False
def restart(_connection=None):
   global needRestart
   needRestart=True

testVar='variable_from_parent'
def testFunc(s):
   import gevent
   gevent.sleep(1)
   return '__%s__'%s

def testScope(_connection=None):
   # original "testVar"
   _connection.call.log('"globals" imported:', _connection.call.eval('testFunc(testVar)'))

   # overloaded "testVar"
   _connection.call.log('"testVar" passed to scope:', _connection.call.eval('testVar', scope={'testVar':'overloaded_variable'})) # we can't call testFunc() here, it's not defined

   # overloaded "testVar" but with original globals()
   _connection.call.log('"testVar" passed to merged scope, "globals" imported:', _connection.call.eval('testFunc(testVar)', scope=[None, {'testVar':'overloaded_variable'}]))

   # overloaded "testVar" but then over-overloaded with original globals()
   _connection.call.log('"testVar" passed to scope (but overloaded with globals), "globals" imported:', _connection.call.eval('testFunc(testVar)', scope=[{'testVar':'overloaded_variable'}, None]))

   # overloaded "testVar" and imported testFunc() from globals()
   _connection.call.log('"testVar" passed to scope, "testFunc" imported:', _connection.call.eval('testFunc(testVar)', scope=[{'testVar':'overloaded_variable'}, 'testFunc']))

   # overloaded "testVar" and no imported function, must return error
   try: s=_connection.call.eval('testFunc(testVar)', scope={'testVar':'overloaded_variable'})
   except Exception, e: s=e
   _connection.call.log('"testVar" passed to scope, "testFunc" not imported:', s) # we can't call testFunc() here, it's not defined

def testEvalCB(async=True, _connection=None):
   def tFunc1(res, err, _connection):
      _connection.call.log('> From eval-callback', res, err)
   _connection.call.eval('testFunc(testVar)', cb=tFunc1, wait=not(async))
   _connection.call.log('> After eval')
   return 'ok'

def test1(onlySelf=False, _connection=None):
   _connection.call.log('>>before locking')
   if onlySelf: _connection.call.lock()
   else: _connection.server.lock()
   if onlySelf: s=_connection.call.wait(returnStatus=True)
   else: s=_connection.server.wait(returnStatus=True)
   _connection.call.log('>>check locking from dispatcher', s)
   _connection.call.sleep(5)
   if onlySelf: _connection.call.unlock()
   else: _connection.server.unlock()
   _connection.call.log('>>after locking')
   return 'test1'
test1._alias='testLock'

def test2(onlySelf=False, _connection=None):
   # if we ran this before test1(), this wait while test1() completed
   _connection.call.sleep(2)
   _connection.call.log('>>before wait()')
   if onlySelf: _connection.call.wait()
   else: _connection.server.wait()
   _connection.call.log('>>after wait()')
   return 'test2'
test2._alias='testWait'

def test3(_connection=None):
   # this will rise error, becouse this method not implemented yet
   _connection.server.reload()
   return 'test3'
test3._alias='testNotImplemented'

def test4(_connection=None):
   # simple sleep
   _connection.call.log('>>before sleep()')
   _connection.call.sleep(5)
   _connection.call.log('>>after sleep()')
   return 'ok'
test4._alias='testSleep'

testCopyGlobal=[]
def testCopyGlobal_proc(_connection=None):
   # get data from global variable
   if _connection.get('parallelType', False):
      tArr=_connection.call.copyGlobal('testCopyGlobal', actual=True)
   else: tArr=testCopyGlobal
   # here we slowly process this data
   sMax=max(tArr)
   sMin=min(tArr)
   sSum=0.0
   for s in tArr: sSum+=s
   sAverage=sSum/float(len(tArr))
   sProd=1.0
   for s in tArr: sProd*=s
   sGeomean=sProd**(1/float(len(tArr)))
   return 'max: %s, min: %s, average: %s, geomean: %s'%(sMax, sMin, sAverage, sGeomean)

def testCopyGlobal_gen(_connection=None):
   # generate random data
   global testCopyGlobal
   testCopyGlobal=None
   testCopyGlobal=[round((random.random()+0.01)*99, 2) for i in xrange(1*10**6)]

def testCopyGlobal_async(_connection=None):
   # get data from global variable, but don't wait for completion (passing cb switch to async mode)
   if not _connection.get('parallelType', False):
      return '!! this metod for testind parallel exec-backend, but you dont use it !!'
   def tFunc(res, err, _connection):
      _connection.call.log('> From copyGlobal-callback', err, len(res))
   _connection.call.copyGlobal('testCopyGlobal', actual=True, cb=tFunc)
   _connection.call.log('> After copyGlobal')
   return 'ok'

def echo(data='Hello world', _connection=None):
   return data

sexy_speedStats={}
def sexyNum(n=None, _connection=None):
   # find sexy=prime numbers and return stats about early founded
   if n is None: n=random.randint(25000, 35000)
   mytime=_connection.server._getms()
   tArr=sexyPrime.sexy_primes(n)
   mytime=round((_connection.server._getms()-mytime)/1000.0, 1)
   if _connection.get('parallelType', False): # in parallel backend, need to access parent's memory
      _connection.call.execute('if %(n)s not in sexy_speedStats: sexy_speedStats[%(n)s]=[]\nsexy_speedStats[%(n)s].append(%(t)s)'%({'n':n, 't':mytime}))
   else: # in simple backend, variable in our globals
      if n not in sexy_speedStats: sexy_speedStats[n]=[]
      sexy_speedStats[n].append(mytime)
   # find nearest settings
   near=[]
   if _connection.get('parallelType', False): # in parallel backend, need to access parent's memory
      if _connection.call.eval('len(sexy_speedStats[%s])'%n)>1: near=['same', n]
   else: # in simple backend, variable in our globals
      if len(sexy_speedStats[n])>1: near=['same', n]
   if not len(near):
      if _connection.get('parallelType', False): # in parallel backend, need to access parent's memory
         tArr1=_connection.call.eval('sorted([s for s in sexy_speedStats.keys() if s!=%s])'%n)
      else: # in simple backend, variable in our globals
         tArr1=sorted([s for s in sexy_speedStats.keys() if s!=n])
      if len(tArr1)<3: near='Too low stats for find nearest'
      else:
         for i, s in enumerate(tArr1):
            if i<len(tArr1)-1 and s<n and tArr1[i+1]>n:
               near=['nearest (%s)'%s, s if(n-s<n-tArr1[i+1]) else tArr1[i+1]]
               break
   if _connection.server._isString(near): pass
   elif len(near):
      if _connection.get('parallelType', False): # in parallel backend, need to access parent's memory
         s=_connection.call.eval('round(sum(sexy_speedStats[%(s)s])/len(sexy_speedStats[%(s)s]), 1)'%({'s':near[1]}))
      else: # in simple backend, variable in our globals
         s=round(sum(sexy_speedStats[near[1]])/len(sexy_speedStats[near[1]]), 1)
      near='For %s settings average speed %s seconds'%(near[0], s)
   else: near='No nearest results'
   return 'For %s numbers finded %s pairs in %s seconds. %s'%(n, len(tArr), mytime, near)

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
   server.registerFunction(stats, path='/api', dispatcherBackend='simple')
   server.registerFunction(test1, path='/api')
   server.registerFunction(test2, path='/api')
   server.registerFunction(test3, path='/api')
   server.registerFunction(test4, path='/api')

   server.registerFunction(testScope, path='/api')
   server.registerFunction(testEvalCB, path='/api')

   server.registerFunction(echo, path='/api')
   server.registerFunction(echo, path='/api', dispatcherBackend='simple', name='echo2')

   server.registerFunction(sexyNum, path='/api')
   server.registerFunction(sexyNum, path='/api', dispatcherBackend='simple', name='sexyNum2')

   server.registerFunction(restart, path='/api', dispatcherBackend='simple')

   server.registerFunction(testCopyGlobal_gen, path='/api', dispatcherBackend='simple')
   server.registerFunction(testCopyGlobal_proc, path='/api')
   server.registerFunction(testCopyGlobal_async, path='/api')

   # Run server's loop in non-blocking mode
   server.start()
   while True:
      # every second check var <needRestart> and if True, restart server
      server._sleep(1)
      if needRestart:
         needRestart=False
         print 'Restarting..'
         # server.restart()
         server.stop()
         print '> stopped'
         server._sleep(5)
         server.start()
         print '>restarted'
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
