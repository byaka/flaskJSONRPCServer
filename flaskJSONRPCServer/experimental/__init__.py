#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This package contains experimental extensions for flaskJSONRPCServer.

moreAsync:
   Tricky implemetations of some server's methods that add async executing.

asyncJSON:
   Pseudo-async implementation of JSON parser and dumper. It allow to switch context (switching to another greenlet or thread) every given seconds. Useful on processing large data.

uJSON
   Extremely fast JSON-backend. Not supports long().
"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from utils import *
else:
   import sys
   from ..utils import *

use_moreAsync=True
use_ujson=True
use_asyncJSON=True
msgShowed=False

class moreAsync:
   def __init__(self, method, getSize=None, minSize=0, newMethod=None):
      self.method=method
      self.getSize=getSize if getSize is not None else sys.getsizeof
      self.minSize=minSize
      self.server=None
      self.speedStats={}
      self.minSleep=0.2
      self.result={}
      self._newMethod=newMethod

   def overload(self, server):
      if not server.settings.gevent: return # not needed, requests processed in native threads
      # add link to server
      if self.server is None: self.server=server
      # add backup for old methods
      if not hasattr(self.server, '_moreAsync_backup'):
         setattr(self.server, '_moreAsync_backup', {})
      self.server._moreAsync_backup[self.method]=getattr(server, self.method)
      # overload method
      setattr(server, self.method, self.wrapper)

   def wrapper(self, data):
      # calc size
      size=self.getSize(data) if isFunction(self.getSize) else self.getSize
      # if size lower then minSize, call original method
      if size and size<self.minSize:
         return self.server._moreAsync_backup[self.method](data)
      #
      return self.server.callAsync(self.newMethod, args=[data, size], sleepTime=self.minSleep)

   def newMethod(self, data, size):
      try:
         mytime=getms()
         if isFunction(self._newMethod):
            res=self._newMethod(data, self)
         else:
            res=self.server._moreAsync_backup[self.method](data)
         speed=getms()-mytime
         self.speedStats[round(size/1024.0/1024.0)]=speed
         self.server._logger(4, 'MOREASYNC_%s %smb, %ss'%(self.method, round(size/1024.0/1024.0, 2), round(speed/1000.0, 1)))
         # print '>>>>>>MOREASYNC_%s %smb, %ss'%(self.method, round(size/1024.0/1024.0, 2), round(speed/1000.0, 1))
         return res
      except Exception, e:
         self.server._throw('MOREASYNC_ERROR %s: %s'%(self.method, e))

moreAsync_methods={
   '_compressGZIP': {'minSize':1*1024*1024},
   '_uncompressGZIP': {'minSize':1*1024*1024},
   '_sha256': {'minSize':100*1024*1024},
   '_sha1': {'minSize':100*1024*1024}
}

asyncJSON_limits={
   'dumps':1*1024*1024,
   'loads':1*1024*1024
}

def _patchServer(server):
   global msgShowed
   if not msgShowed:
      server._logger(0, 'EXPERIMENTAL futures used')
   msgShowed=True
   global use_moreAsync, use_ujson, use_asyncJSON
   # overload methods to moreAsync
   if server.settings.gevent and use_moreAsync:
      for k, v in moreAsync_methods.items():
         o=moreAsync(k, **v)
         o.overload(server)
   # try import and use ujson
   if use_ujson:
      try: import ujson
      except ImportError:
         server._logger(2, 'EXPERIMENTAL_PATCH: ujson not found')
      else:
         server._jsonBackend_backup=server.jsonBackend
         # wrapper for json.dumps with auto-switching
         def tFunc_dumps(data, server=server, **kwargs):
            try: return ujson.dumps(data)
            except Exception, e:
               if str(e)=='long too big to convert':
                  return server._jsonBackend_backup.dumps(data, **kwargs)
               raise
         # wrapper for json.loads with auto-switching
         def tFunc_loads(data, server=server, **kwargs):
            try: return ujson.loads(data)
            except Exception, e:
               if str(e)=='Value is too big!':
                  return server._jsonBackend_backup.loads(data, **kwargs)
               raise
         server.jsonBackend=jsonBackendWrapper(tFunc_dumps, tFunc_loads)
   # try import and use asyncJSON
   if use_asyncJSON:
      try: import asyncjson
      except ImportError:
         server._logger(2, 'EXPERIMENTAL_PATCH: asyncjson not found')
      else:
         server._asyncJSON_backup=server.jsonBackend
         # wrapper for json.dumps with auto-switching
         def tFunc_dumps(data, server=server, **kwargs):
            size=sys.getsizeof(data)
            if size is not None and size<asyncJSON_limits['dumps']:
               return server._asyncJSON_backup.dumps(data)
            mytime=getms()
            res=asyncjson.dumps(data, maxProcessTime=0.1, cb=lambda *args:server._sleep(0.001))
            speed=getms()-mytime
            server._logger(4, 'asyncJSON.dumps: %smb, %ss'%(round(size/1024.0/1024.0, 2), round(speed/1000.0, 2)))
            return res
         # wrapper for json.loads with auto-switching
         def tFunc_loads(data, server=server, **kwargs):
            size=sys.getsizeof(data)
            if size is not None and size<asyncJSON_limits['loads']:
               return server._asyncJSON_backup.loads(data)
            mytime=getms()
            res=asyncjson.loads(data, maxProcessTime=0.1, cb=lambda:server._sleep(0.001))
            speed=getms()-mytime
            server._logger(4, 'asyncJSON.loads: %smb, %ss'%(round(size/1024.0/1024.0, 2), round(speed/1000.0, 2)))
            return res
         server.jsonBackend=jsonBackendWrapper(tFunc_dumps, tFunc_loads)

def initLocal(scope, server):
   global msgShowed
   if not msgShowed:
      server._logger(0, 'EXPERIMENTAL futures used')
   msgShowed=True
   scope['_patchServer']=_patchServer

def initGlobal(scope):
   global msgShowed
   # if not msgShowed:
   #    server._logger(0, 'EXPERIMENTAL futures used')
   # msgShowed=True
   pass

if __name__=='__main__':
   import asyncjson, json

   # obj=[[{"jsonrpc": "2.0", "method": u"привет", "params": [{"jsonrpc": "1.0", "method": "test2", "params": {"param1": -23, "param2": 42.2, "param3":True, "param4":False, "param5":None, "param6":u'[{"jsonrpc": "2.0", "method": "привет", "params": [{"jsonrpc": "1.0", "method": "test2", "params": {"param1": -23, "param2": 42.2, "param3":True, "param4":False, "param5":None}, "id": 3}, 23.123], "id": 1}]'}, "id": 3}, 23.123], "id": 1}]]
   # obj={"id": '{"id": 1}'}
   # obj={'key1':'value"]', 'key2':'value:{2}'}
   obj={'k':'test "1\n1" 2\t2 test'}

   print 'ORIGINAL:', obj
   data1=asyncjson.dumps(obj)
   data2=asyncjson.dumps_native(obj)
   data3=json.dumps(obj)
   print 'SERIALIZED async compiled: %s'%(data1,)
   print 'SERIALIZED async native  : %s'%(data2,)
   print 'SERIALIZED default       : %s'%(data3,)

   obj_p1=asyncjson.loads(data1)
   obj_p2=asyncjson.loads_native(data2)
   obj_p3=json.loads(data3)
   print 'PARSED async compiled:', obj_p1
   print 'PARSED async native  :', obj_p2
   print 'PARSED default       :', obj_p3
   print 'PARSED default 2     :', asyncjson.loads_native(data3)
   print 'PARSED default 3     :', asyncjson.loads(data3)
   print obj==obj_p1
   sys.exit(0)
