#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains dispatcher-execution backend for flaskJSONRPCServer.

"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from utils import magicDict
else:
   # from flaskJSONRPCServer.utils import magicDict
   from ..__init__ import *

class execBackend:
   """
   :param int poolSize:
   :param bool importGlobalsFromParent:
   :param scope parentGlobals:
   :param float sleepTime_resultCheck:
   :param float sleepTime_emptyQueue:
   :param float sleepTime_waitLock:
   :param int sleepTime_lazyRequest:
   :param float sleepTime_checkPoolStopping:
   :param bool allowThreads:
   :param str id:
   :param str socketPath:
   :param bool saveResult:
   :param bool persistent_queueGet:
   :param bool useCPickle:
   """

   def __init__(self, poolSize=1, importGlobalsFromParent=True, parentGlobals=None, sleepTime_resultCheck=0.15, sleepTime_emptyQueue=0.1, sleepTime_waitLock=0.75, sleepTime_lazyRequest=2*60*1000, sleepTime_checkPoolStopping=0.3, allowThreads=True, id='execBackend_parallelWithSocket', socketPath=None, saveResult=True, persistent_queueGet=True, useCPickle=False):
      self.settings=magicDict({
         'poolSize':poolSize,
         'sleepTime_resultCheck':sleepTime_resultCheck,
         'sleepTime_emptyQueue':sleepTime_emptyQueue,
         'sleepTime_waitLock':sleepTime_waitLock,
         'sleepTime_lazyRequest':sleepTime_lazyRequest,
         'sleepTime_checkPoolStopping':sleepTime_checkPoolStopping,
         'importGlobalsFromParent':importGlobalsFromParent,
         'allowThreads':allowThreads,
         'lazyRequestChunk':1000,
         'saveResult':saveResult,
         'persistent_queueGet':persistent_queueGet,
         'useCPickle':useCPickle
      })
      from collections import deque
      self.parentGlobals=parentGlobals or {}
      self.queue=deque()
      self._pool=[]
      self._server=None
      self._id=id
      if not saveResult: self._id+='NoResult'
      self.result={}
      self.socketPath=socketPath
      self._forceStop=False
      self._jsonBackend=None
      if useCPickle:
         #! try http://stackoverflow.com/a/15108940
         import cPickle
         self._jsonBackend=magicDict({
            'dumps': lambda data, **kwargs: cPickle.dumps(data),
            'loads': lambda data, **kwargs: cPickle.loads(data)
         })

   def start(self, server):
      if self._server: return
      if not server.setts.gevent:
         server._throw('ExecBackend "parallelWithSocket" not implemented for Flask backend yet')
      # warnings
      if self.settings.useCPickle:
         server._logger(2, 'WARNING: cPickle is slow backend')
      # choise json-backend
      if self._jsonBackend is None: self._jsonBackend=server.jsonBackend
      # generate socket-file
      if not self.socketPath:
         self.socketPath='%s/.%s.%s.sock'%(server._getScriptPath(), server._getScriptName(withExt=False), self._id)
      if os.path.exists(self.socketPath): os.remove(self.socketPath)
      # generate access token
      self.token='--'.join([str(int(random.random()*999999)) for i in xrange(10)])
      # import parent's globals if needed
      if self.settings.importGlobalsFromParent:
         server._importGlobalsFromParent(scope=self.parentGlobals)
      # patching
      from gevent import monkey
      monkey.patch_all(sys=False, os=False, thread=False, time=False, ssl=False, socket=False) #! "os" may cause some problems with multiprocessing. but better get original objects in execBackend
      server._importAll(forceDelete=True)
      # start processesPool
      """
      if this block go after starting new API, server has really strange problems with "doubled" variables and etc.
      But if this code go before "self._server.start()", all work fine.
      I not understand why this happened and i spend more then two days for debugging.
      """
      import multiprocessing
      for i in xrange(self.settings.poolSize): # multiprocessing.cpu_count()
         p=multiprocessing.Process(target=self.childCicle, args=(server, i))
         p.start()
         self._pool.append(p)
      # create api on unix-socket
      self._parentServer=server
      import socket
      listener=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      listener.bind(self.socketPath)
      listener.listen(1)
      #select compression settings
      allowCompress=False
      compressMinSize=100*1024*1024
      if server.settings.experimental and experimentalPack.use_moreAsync and '_compressGZIP' in experimentalPack.moreAsync_methods: allowCompress=True
      #start API
      self._server=flaskJSONRPCServer([self.socketPath, listener], blocking=False, cors=False, gevent=server.setts.gevent, debug=False, log=server.settings.log, fallback=False, allowCompress=allowCompress, compressMinSize=compressMinSize, jsonBackend=self._jsonBackend, tweakDescriptors=None, notifBackend='simple', dispatcherBackend='simple', experimental=server.settings.experimental)
      self._server.setts.antifreeze_batchMaxTime=1*1000
      self._server.setts.antifreeze_batchBreak=False
      self._server.setts.antifreeze_batchSleep=1
      self._server.registerFunction(self.api_queueGet, path='/queue', name='get')
      self._server.registerFunction(self.api_queueResult, path='/queue', name='result')
      self._server.registerFunction(self.api_parentEval, path='/parent', name='eval')
      self._server.registerFunction(self.api_parentVarCheck, path='/parent', name='varCheck')
      self._server.registerFunction(self.api_parentStats, path='/parent', name='stats')
      self._server.registerFunction(self.api_parentLock, path='/parent', name='lock')
      self._server.registerFunction(self.api_parentWait, path='/parent', name='wait')
      self._server.registerFunction(self.api_parentUnlock, path='/parent', name='unlock')
      self._server.registerFunction(self.api_parentSpeedStatsAdd, path='/parent', name='speedStatsAdd')
      self._server.start()

   def stop(self, server, timeout=20, processingDispatcherCountMax=0):
      # stop process's pool
      mytime=server._getms()
      self._forceStop=True
      while True:
         server._sleep(self.settings.sleepTime_checkPoolStopping)
         tArr=[p for p in self._pool if p.is_alive()]
         if not len(tArr): break
         elif timeout and server._getms()-mytime>=timeout*1000:
            for p in tArr:
               try: p.terminate()
               except Exception, e: pass
            break
      self._pool=[]
      self._forceStop=False
      # stop api
      self._server.stop(timeout=timeout-(server._getms()-mytime)/1000.0)
      self._server=None

   def sendRequest(self, path, method, params=None, notif=False):
      mytime=self._server._getms()
      if params is None: params=[]
      if self._server._isArray(method): #always like notify-batch
         data=[{'jsonrpc': '2.0', 'method': v['method'], 'params':v['params']} for v in method]
      else:
         data={'jsonrpc': '2.0', 'method': method, 'params':params}
         if not notif: #like notif
            data['id']=int(random.random()*999999)
      try: data=self._parentServer._serializeJSON(data)
      except Exception, e:
         self._parentServer._throw('Cant serialize JSON: %s'%(e))
      _conn=self._conn if self._conn is not None else UnixHTTPConnection(self.socketPath)
      for i in xrange(10):
         try:
            _conn.request('POST', path, data, {'Token':self.token, 'Accept-encoding':'gzip'})
            if self._conn is not None: self._conn=_conn
            break
         except Exception: pass
         self._parentServer._sleep(1)
         _conn=UnixHTTPConnection(self.socketPath)
      else: self._parentServer._throw('Cant connect to backend-API:'%self.socketPath)
      resp=_conn.getresponse()
      data2=resp.read()
      if notif or self._server._isArray(method):
         if not self._server._isArray(method) and method!='speedStatsAdd':
            self._parentServer._speedStatsAdd(method, self._server._getms()-mytime)
         return
      if resp.getheader('Content-Encoding', None)=='gzip':
         data2=self._parentServer._uncompressGZIP(data2)
      data2=self._parentServer._parseJSON(data2)
      if method!='speedStatsAdd':
         self._parentServer._speedStatsAdd(method, self._server._getms()-mytime)
      if not self._server._isDict(data2): return None
      elif data2.get('error', None):
         self._parentServer._throw('Error %s: %s'%(data2['error']['code'], data2['error']['message']))
      return data2.get('result', None)

   def sendRequestEx(self, data, async=False, cb=None, returnAllData=False):
      # helper
      def tFunc(self, data, async, cb):
         data['error']=None
         try:
            data['result']=self.sendRequest(data.get('path', '/'), data['method'], data['params'], notif=async)
         except Exception, e:
            data['result']=None
            data['error']=e
         if self._server._isFunction(cb): cb(data, self)
         elif data['error']: self._parentServer._throw(data['error'])
         return (data if returnAllData else data['result'])
      # process request
      if async and self._server._isFunction(cb): #fully async with callback
         if not self.settings.allowThreads:
            self._parentServer._logger('Fully async request only supported, if allowThreads==True')
         self._parentServer._thread(tFunc, args=[self, data, False, cb])
      else: # simple request
         return tFunc(self, data, async, cb)

   def childCicle(self, parentServer, id=0):
      self._parentServer=parentServer
      self._id='%s#child_%s'%(self._id, id)
      self._conn=None
      self._lazyRequest={}
      self._lazyRequestLatTime=None
      self._serverOriginalMethods=magicDict({})
      self._server=flaskJSONRPCServer(['', ''], gevent=parentServer.setts.gevent, log=parentServer.setts.log, jsonBackend=self._jsonBackend, tweakDescriptors=None, experimental=parentServer.settings.experimental) #we need this dummy for some methods from it
      if not self.settings.allowThreads:
         # if threads not allowed, we don't need gevent in child
         parentServer.setts.gevent=False
         parentServer._importAll(forceDelete=True)
         # in threaded mode (also gevent) we can't use same socket for read and write
         self._conn=UnixHTTPConnection(self.socketPath)
      # create hashmap for parentGlobals
      self.parentGlobalsMap={}
      if self.settings.importGlobalsFromParent:
         for k, v in self.parentGlobals.items():
            if self._server._isFunction(v) or self._server._isModule(v): continue
            self.parentGlobalsMap[k]=self.var2hash(v, k)
      # overload some methods in parentServer
      self.childDisableNotImplemented()
      parentServer.stats=lambda inMS=False: self.sendRequest('/parent', 'stats', [inMS])
      parentServer.lock=lambda dispatcher=None: self.sendRequest('/parent', 'lock', [(None if dispatcher is None else dispatcher._id)])
      parentServer.unlock=lambda dispatcher=None, exclusive=False: self.sendRequest('/parent', 'unlock', [(None if dispatcher is None else dispatcher._id), exclusive])
      parentServer.wait=self.childWait
      parentServer._speedStatsAdd=self.childSpeedStatsAdd
      self._serverOriginalMethods._logger=self._server._logger
      self._server._logger=self.childLogger
      parentServer._logger=self.childLogger
      # main cicle
      while True:
         self.childSendLazyRequest()
         p=self.sendRequest('/queue', 'get')
         if p=='__stop__': sys.exit(0)
         elif p:
            if self.settings.allowThreads:
               parentServer._thread(self.childCallDispatcher, args=[p])
            else: self.childCallDispatcher(p)
            continue
         if not self.settings.persistent_queueGet: # pause only need for non-persistent-mode
            parentServer._sleep(self.settings.sleepTime_emptyQueue)

   def childLogger(self, level, *args):
      level, args=self._server._loggerPrep(level, args)
      args.insert(0, '   (%s)'%self._id)
      self._serverOriginalMethods._logger(level, *args)

   def childSendLazyRequest(self):
      if self._lazyRequestLatTime is None: self._lazyRequestLatTime=self._server._getms()
      if self._lazyRequestLatTime is not True and self._server._getms()-self._lazyRequestLatTime<self.settings.sleepTime_lazyRequest: return
      for rId, v in self._lazyRequest.items():
         if not len(v): continue
         path=self._server._strGet(rId, '', '<')
         self._lazyRequest[rId]=v[self.settings.lazyRequestChunk:]
         self.sendRequest(path, v[:self.settings.lazyRequestChunk])
         if len(v)>self.settings.lazyRequestChunk:
            self._lazyRequestLatTime=True #shedule to next call
            return
      self._lazyRequestLatTime=self._server._getms()

   def childCallDispatcher(self, p):
      self._server._logger(4, 'Processing with parallel-backend: %s()'%(p['dataIn']['method']))
      p['request']=magicDict(p['request']) # _callDispatcher() work with this like object, not dict
      status, params, result=self._parentServer._callDispatcher(p['uniqueId'], p['path'], p['dataIn'], p['request'], overload=self.childConnectionOverload, nativeThread=self.settings.allowThreads and not(self._parentServer.setts.gevent), isJSONP=p.get('isJSONP', False))
      if not self.settings.saveResult: return
      # prepare for pickle
      #! #57 It must be on TYPE-based, not NAME-based
      convBlackList=['server', 'call', 'dispatcher']
      # convWhitelist=['cookies', 'cookiesOut', 'ip', 'notify', 'jsonp', 'path', 'parallelType', 'parallelPoolSize', 'headersOut', 'dispatcherName', 'headers', 'nativeThread', 'allowCompress']
      if '_connection' in params:
         params['_connection']=dict([(k,v) for k,v in params['_connection'].items() if k not in convBlackList])
      self.sendRequest('/queue', 'result', [p['uniqueId'], status, params, result])

   def childWait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      # parentServer.wait() is more complicated, becose it must check lock-status in parent, but suspend child
      sleepMethod=sleepMethod or self._parentServer._sleep
      while self.sendRequest('/parent', 'wait', [(None if dispatcher is None else dispatcher._id)]):
         if returnStatus: return True
         sleepMethod(self.settings.sleepTime_waitLock)
      if returnStatus: return False

   def childSpeedStatsAdd(self, name, val):
      rId='/%s/<%s>'%('parent', 'speedStatsAdd')
      if rId not in self._lazyRequest: self._lazyRequest[rId]=[]
      if not len(self._lazyRequest[rId]):
         self._lazyRequest[rId].append({'path':'/parent', 'method':'speedStatsAdd', 'params':[[], []]})
      self._lazyRequest[rId][0]['params'][0].append('execBackend_%s'%name)
      self._lazyRequest[rId][0]['params'][1].append(val)

   def childConnectionOverload(self, _connection):
      # some overloads in _callDispatcher()._connection
      _connection['parallelType']='parallelWithSocket'
      _connection['parallelPoolSize']=self.settings.poolSize
      _connection['parallelId']=self._id
      # wrap methods for passing "_connection" object
      _connection['call']['execute']=lambda code, scope=None, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=True, _connection=magicDict(_connection))
      _connection['call']['eval']=lambda code, scope=None, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=False, _connection=magicDict(_connection))
      _connection['call']['copyGlobal']=lambda var, actual=True, cb=None: self.childCopyGlobal(var, actual=actual, cb=cb, _connection=magicDict(_connection))
      return _connection

   def childDisableNotImplemented(self):
      # disable none-implemented methods in parentServer
      whiteList=['_callDispatcher', '_checkFileDescriptor', '_compressResponse', '_compressGZIP', '_uncompressGZIP', '_copyRequestContext', '_countFileDescriptor', '_fileGet', '_fileWrite', '_fixJSON', '_formatPath', '_getErrorInfo', '_getms', '_getScriptName', '_getScriptPath', '_getServerUrl', '_import', '_importAll', '_importSocket', '_importThreading', '_inChild', '_isArray', '_isDict', '_isFunction', '_isInstance', '_isNum', '_isString', '_logger', '_loggerPrep', '_parseJSON', '_parseRequest', '_prepResponse', '_serializeJSON', '_sha1', '_sha256', '_strGet', '_throw', '_tweakLimit', 'fixJSON', '_sleep', '_thread', '_randomEx', '_controlGC', '_countMemory', '_calcMimeType']
      for name in dir(self._parentServer):
         if not self._parentServer._isFunction(getattr(self._parentServer, name)): continue
         if name not in whiteList:
            s='Method "%s" not implemented in parallel backend'%(name)
            setattr(self._parentServer, name, lambda __msg=s, *args, **kwargs: self._parentServer._throw(__msg))

   def childEval(self, code, scope=None, wait=True, cb=None, isExec=False, _connection=None):
      def tFunc(o, self):
         o['cb'](o['result'], o['error'], _connection)
      data={'path':'/parent', 'method':'eval', 'params':[code, scope, isExec], 'cb':cb}
      self.sendRequestEx(data, async=not(wait), cb=(tFunc if self._server._isFunction(cb) else None))

   def childCopyGlobal(self, var, actual=True, cb=None, _connection=None):
      # if callback passed, method work in async mode
      vars=var if self._server._isArray(var) else [var]
      res={}
      if not actual and self.settings.importGlobalsFromParent:
         # get from cache without checking
         for k in vars:
            res[k]=self.parentGlobals.get(k, None)
            self._server._logger(4, 'CopyGlobal var "%s": without checking'%k)
         if self._server._isFunction(cb):
            cb((res if self._server._isArray(var) else res.values()[0]), False, _connection)
      else:
         hashs=[self.parentGlobalsMap.get(k, None) for k in vars]
         data={'path':'/parent', 'method':'varCheck', 'params':[hashs, vars, True], 'cb':cb, 'onlyOne':not(self._server._isArray(var))}
         def tFunc(data, self):
            if data['error']:
               if self._server._isFunction(data['cb']):
                  return data['cb'](None, data['error'], _connection)
               else: self._parentServer._throw(data['error'])
            res={}
            for k, r in data['result'].items():
               if not r[0]: # not changed
                  res[k]=self.parentGlobals.get(k, None)
                  self._server._logger(4, 'CopyGlobal var "%s": not changed'%k)
               elif r[1] is None: # not founded or not hashable
                  res[k]=None
                  if k in self.parentGlobals:
                     del self.parentGlobalsMap[k]
                     del self.parentGlobals[k]
                  self._server._logger(4, 'CopyGlobal var "%s": not founded or not hashable'%k)
               else: # changed
                  v=r[2]
                  # need to deseriolize value
                  v=self._server._parseJSON(v)
                  res[k]=v
                  self.parentGlobalsMap[k]=r[1]
                  self.parentGlobals[k]=v
                  self._server._logger(4, 'CopyGlobal var "%s": changed'%k)
            if self._server._isFunction(data['cb']):
               data['cb']((res if not data['onlyOne'] else res.values()[0]), False, _connection)
            else: data['result']=res
         res=self.sendRequestEx(data, async=self._server._isFunction(cb), cb=tFunc)
         if self._server._isFunction(cb): return
      return (res if self._server._isArray(var) else res.values()[0])

   def childRemoteVar(self, name, default=None, clear=False):
      """
      Инициирует обертку virtVar() для переменной, связывая ее с переменной в родительском процессе
      """
      val=default
      if clear: #непроверяя устанавливаем на сервере в значение default
         pass
      else: #проверяем значение на сервере. если переменной нет, устанавливаем значение в default
         pass
      #prepare callbacks
      def tFunc_get(w, k):
         if k not in ('_val', '_type'):
            print '!! Unknown property', k
            return
         pass
      def tFunc_set(w, k, v):
         if k not in ('_val', '_type'):
            print '!! Unknown property', k
            return
         pass
      #prepare var's wrapper
      v=virtVar(val, saveObj=False, cbGet=tFunc_get, cbSet=tFunc_set)
      v._getattrWhitemap+=['_oldType', '_oldHash', '_oldVal']
      v._oldVal=val
      v._oldType=type(val)
      v._oldHash=self.var2hash(val, name)
      return v

   def var2hash(self, var, name, returnSerialized=False):
      try:
         s=self._server._serializeJSON(var)
         h=self._server._sha256(s)
         if returnSerialized: return h, s
         else: return h
      except Exception, e:
         self._server._logger(1, 'ERROR: Cant hash variable "%s#%s": %s'%(name, type(var), e))
         if returnSerialized: return None, None
         else: return None

   def api_queueGet(self, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      # get task
      if self._forceStop: return '__stop__'
      elif not len(self.queue):
         if not self.settings.persistent_queueGet: return None
         else:
            while not len(self.queue):
               self._server._sleep(self.settings.sleepTime_emptyQueue)
      tArr1=self.queue.popleft()
      self._parentServer.processingDispatcherCount+=1
      return tArr1

   def api_queueResult(self, uniqueId, status, params, result, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      # set task's result
      if not self.settings.saveResult: return
      if params and '_connection' in params: # _requestHandler() work with this like object, not dict
         params['_connection']=magicDict(params['_connection'])
      self.result[uniqueId]=[status, params, result]
      self._parentServer.processingDispatcherCount-=1

   def api_parentStats(self, inMS, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      return self._parentServer.stats(inMS=inMS)

   def api_parentEval(self, code, scope=None, isExec=False, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._server._throw('Access denied') # tokens not match
      # eval code in parent process
      try:
         scope=scope if scope is None else scope
         if scope and not self._server._isDict(scope): # scope passed as names
            scope=scope if self._server._isArray(scope) else [scope]
            tArr={}
            for s in scope:
               if s=='_globals': tArr.update(self.parentGlobals)
               elif self._server._isDict(s): tArr.update(s)
               elif self._server._isString(s): tArr[s]=self.parentGlobals.get(s, None)
            scope=tArr
         if scope is None:
            scope={}
            self._parentServer._importGlobalsFromParent(scope=scope)
         scope['__server__']=self._parentServer # add server instance to scope
         s=compile(code, '<string>', 'exec' if isExec else 'eval')
         res=eval(s, scope)
      except Exception, e:
         self._server._throw('Cant execute code: %s'%(e))
      return res

   def api_parentVarCheck(self, hashs, vars, returnIfNotMatch, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._server._throw('Access denied') # tokens not match
      if len(hashs)!=len(vars):
         self._server._throw('Wrong length')
      if not self._server._isArray(hashs) or not self._server._isArray(vars):
         self._server._throw('Arguments "vars" and "hashs" must be array')
      scope={}
      # typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, DictType, ListType, TupleType]
      self._parentServer._importGlobalsFromParent(scope=scope)
      res={}
      for i, k in enumerate(vars):
         vHash=hashs[i]
         if k not in scope: res[k]=[True, None, None]
         else:
            vv=scope[k]
            # for faster processing, we save serialized var and pass to response it, not original var
            vvHash, vvCache=self.var2hash(vv, k, returnSerialized=True)
            if vvHash is None: res[k]=[True, None, None]
            elif vHash!=vvHash:
               res[k]=[True, vvHash, (vvCache if returnIfNotMatch else None)]
            else: res[k]=[False, hash, None]
      return res

   def api_parentLock(self, dispatcherId=None, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      if dispatcherId is None: dispatcher=None
      elif not self._parentServer._isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._parentServer._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      self._parentServer.lock(dispatcher=dispatcher)

   def api_parentWait(self, dispatcherId=None, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      if dispatcherId is None: dispatcher=None
      elif not self._server._isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._server._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      s=self._parentServer.wait(dispatcher=dispatcher, returnStatus=True)
      return s

   def api_parentUnlock(self, dispatcherId=None, exclusive=False, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      if dispatcherId is None: dispatcher=None
      elif not self._parentServer._isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._parentServer._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      self._parentServer.unlock(dispatcher=dispatcher, exclusive=exclusive)

   def api_parentSpeedStatsAdd(self, name, val, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      self._parentServer._speedStatsAdd(name, val)

   def add(self, uniqueId, path, dataIn, request, isJSONP=False):
      #callback for adding request to queue
      try:
         self.queue.append({'uniqueId':uniqueId, 'isJSONP':isJSONP, 'path':path, 'dataIn':dataIn, 'request':request, 'mytime':self._parentServer._getms()})
         return True, len(self.queue)
      except Exception, e:
         print '!!! ERROR execBackend_parallelWithSocket.add', e
         return None, str(e)

   def check(self, uniqueId):
      if not self.settings.saveResult: return None, None, 'saveResult==False'
      mytime=self._parentServer._getms()
      while uniqueId not in self.result:
         self._parentServer._sleep(self.settings.sleepTime_resultCheck)
      self._parentServer._speedStatsAdd('execBackend_check', self._parentServer._getms()-mytime)
      tArr=self.result[uniqueId]
      del self.result[uniqueId]
      return tArr[0], tArr[1], tArr[2] # status, params, result

   def stats(self, inMS=False):
      r={
         '%s_queue'%self._id:len(self.queue),
         '%s_api'%self._id:self._server.stats(inMS=inMS)
      }
      return r
