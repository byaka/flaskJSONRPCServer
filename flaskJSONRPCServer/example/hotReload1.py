# -*- coding: utf-8 -*-
import sys, time, random, os

"""
This example show how to reload API without restarting server.
This function fully safe, waits for completing old requests,
optionally has timeout and ability for overloading variables.
"""

from flaskJSONRPCServer import flaskJSONRPCServer

# default dispatcher
class mySharedMethods:
   def __init__(self): self.data=[]

   def compute(self):
      if not len(self.data): s='No data'
      else:
         s=float(sum(self.data))/len(self.data)
      return '"compute()" method from main module: %s'%s

def stats(_connection=None):
   # return server's speed stats
   return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

# dispatcher for reloading, call him
def reloadApi(_connection=None):
   global myInstance
   # reloading really reloads module, so we need to overload variables
   def tOverloadForClassInstance(server, module, dispatcher): dispatcher.data=myInstance.data
   tArr1=[
      {
         'info':'hotReload1.py',
         'scriptPath':_connection.server._getScriptPath(True),
         'dispatcher':'mySharedMethods',
         'isInstance':True,
         'overload': tOverloadForClassInstance,
         'path':'/api' # don't forget about path
      },
      {
         'info':'rr1.py',
         'scriptPath':_connection.server._getScriptPath()+'/rr1.py',
         'dispatcher':'compute',
         'isInstance':False,
         'overload': {'data':myInstance.data},
         'path':'/api' # don't forget about path
      },
      {
         'info':'lambda',
         'dispatcher':lambda: 'dummy "compute()" method from runtime',
         'dispatcherName':'compute',
         'path':'/api' # don't forget about path
      }
   ]
   # randomly choice new dispatcher
   s=random.choice(tArr1)
   print 'Reload api to "%s"..'%s['info']
   # <clearOld>   if True, all existing dispatchers will be removed
   # <timeout>    is how long (in seconds) we wait for compliting all existing requests
   _connection.server.reload(s, clearOld=False, timeout=3)

# simply generate data for computing
def genData(data):
   for i in xrange(10000):
      data.append(round(random.random()*10, 1))

if __name__=='__main__':
   # generate random data
   global myInstance
   myInstance=mySharedMethods()
   genData(myInstance.data)
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
   # Register dispatcher for all methods of instance
   server.registerInstance(myInstance, path='/api')
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api')
   server.registerFunction(reloadApi, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
