#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains dispatcher-execution backend for flaskJSONRPCServer, that uses multiprocessing (and IPC over UDS).

"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from __init__ import flaskJSONRPCServer, experimentalPack
   from utils import *
   from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType
else:
   import sys, os
   from ..__init__ import flaskJSONRPCServer, experimentalPack
   from ..utils import *
   from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType

import weakref

class execBackend:
   """
   :param str id:
   :param int poolSize:
   :param bool importGlobalsFromParent:
   :param scope parentGlobals:
   :param float sleepTime_resultCheck:
   :param float sleepTime_emptyQueue:
   :param float sleepTime_waitLock:
   :param int sleepTime_lazyRequest:
   :param float sleepTime_checkPoolStopping:
   :param bool allowThreads:
   :param bool saveResult:
   :param bool persistent_queueGet:
   :param bool persistent_waitLock:
   :param bool useCPickle:
   :param bool disableGeventInChild:
   """

   def __init__(self, id='execBackend_parallelWithSocket', poolSize=1, importGlobalsFromParent=True, parentGlobals=None, sleepTime_resultCheck=0.005, sleepTime_emptyQueue=0.2, sleepTime_waitLock=0.75, sleepTime_lazyRequest=2*60*1000, sleepTime_checkPoolStopping=0.3, allowThreads=True, saveResult=True, persistent_queueGet=True, persistent_waitLock=True, useCPickle=False, disableGeventInChild=False, separateSockets=False):
      self.settings={
         'poolSize':poolSize,
         'sleepTime_resultCheck':sleepTime_resultCheck,
         'sleepTime_emptyQueue':sleepTime_emptyQueue,
         'persistent_queueGet':persistent_queueGet,
         'sleepTime_waitLock':sleepTime_waitLock,
         'persistent_waitLock':persistent_waitLock,
         'sleepTime_lazyRequest':sleepTime_lazyRequest,
         'sleepTime_checkPoolStopping':sleepTime_checkPoolStopping,
         'importGlobalsFromParent':importGlobalsFromParent,
         'separateSockets':separateSockets,  #if True, for every child api listens separated socket
         'allowThreads':allowThreads,
         'lazyRequestChunk':1000,
         'allowCompress':None,  #if None, auto select mode
         'compressMinSize':1*1024*1024,
         'saveResult':saveResult,
         'useCPickle':useCPickle,
         'disableGeventInChild':disableGeventInChild,
         'importGlobalsFromParent_typeForEval':None,
         'importGlobalsFromParent_typeForVarCheck':[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, DictType, ListType, TupleType],
         'mergeGlobalsToParent_typeForEval':'[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, TupleType]'
      }
      self.parentGlobals=parentGlobals or {}
      self.queue=deque2()
      self._pool=[]
      self._server=None
      self._id=id
      if not saveResult: self._id+='NoResult'
      self.queueResult={}
      self.socketPath=None
      self._forceStop=False
      self._jsonBackend=None
      self._IPCLock_queue={}
      if useCPickle:
         #! предположительно использование cPickle вместе с experimental-patch поломает систему на больших пакетах
         #! try http://stackoverflow.com/a/15108940
         import cPickle
         self._jsonBackend=magicDict({
            'dumps': lambda data, **kwargs: cPickle.dumps(data),
            'loads': lambda data, **kwargs: cPickle.loads(data)
         })

   def start(self, server):
      if self._server: return
      # warnings
      if self.settings['useCPickle']:
         if server.settings.experimental:
            server._logger(0, 'WARNING: cPickle backend not tested with experimental patch')
         server._logger(2, 'WARNING: cPickle is slow backend')
      # convert to tuple
      if self.settings['importGlobalsFromParent_typeForVarCheck'] is not None and not isTuple(self.settings['importGlobalsFromParent_typeForVarCheck']):
         self.settings['importGlobalsFromParent_typeForVarCheck']=tuple(self.settings['importGlobalsFromParent_typeForVarCheck'])
      # choise json-backend
      if self._jsonBackend is None:
         self._jsonBackend=server.jsonBackend
      # generate access token
      self.token='--'.join([randomEx() for i in xrange(30)])
      # import parent's globals if needed
      if self.settings['importGlobalsFromParent']:
         deniedNames=['__builtins__']  #!add other
         server._importGlobalsFromParent(scope=self.parentGlobals, typeOf=self.settings['importGlobalsFromParent_typeForVarCheck'], filterByName=deniedNames, filterByNameReversed=True)
      # start processesPool
      if server.settings.gevent:
         from ..utils import gmultiprocessing as mp
      else:
         import multiprocessing as mp
      listeners=[]
      if not self.settings['separateSockets']:
         # generate socket-file for API
         self.socketPath='%s/.%s.%s#child.sock'%(getScriptPath(), getScriptName(withExt=False), self._id)
         if os.path.exists(self.socketPath): os.remove(self.socketPath)
         listeners.append(self.socketPath)
      for i in xrange(self.settings['poolSize']):
         if self.settings['separateSockets']:
            # generate separated socket-file for API
            self.socketPath='%s/.%s.%s#child_%s.sock'%(getScriptPath(), getScriptName(withExt=False), self._id, i)
            if os.path.exists(self.socketPath): os.remove(self.socketPath)
            listeners.append(self.socketPath)
         # run child process
         p=mp.Process(target=self.childCicle, args=(server, i))
         p.daemon=True
         p.start()
         setattr(p, '_id', '%s#child_%s'%(self._id, i))
         self._pool.append(p)
         server._logger(4, 'Started child-process <%s>'%p._id)
      # create socket for API
      sockClass=server._socketClass()
      for i, lPath in enumerate(listeners):
         # create listener
         l=sockClass.socket(sockClass.AF_UNIX, sockClass.SOCK_STREAM)
         l.bind(lPath)
         l.listen(server.settings.backlog)
         listeners[i]=(lPath, l)
      if not self.settings['separateSockets']: listeners=listeners[0]
      # link to parentServer
      self._parentServer=server
      #select compression settings
      self._allowCompress=self.settings['allowCompress']
      if self._allowCompress is None and server.settings.experimental and experimentalPack.use_moreAsync and '_compressGZIP' in experimentalPack.moreAsync_methods: self._allowCompress=True
      #start API on unix-socket
      self._server=flaskJSONRPCServer(listeners, multipleAdress=self.settings['separateSockets'], blocking=False, cors=False, gevent=server.settings.gevent, debug=False, log=server.settings.log, fallback=False, allowCompress=self._allowCompress, compressMinSize=self.settings['compressMinSize'], jsonBackend=self._jsonBackend, tweakDescriptors=None, notifBackend='simple', dispatcherBackend='simple', experimental=server.settings.experimental, controlGC=False, name='API_of_<%s>'%self._id)
      self._server.settings.antifreeze_batchMaxTime=1*1000
      self._server.settings.antifreeze_batchBreak=False
      self._server.settings.antifreeze_batchSleep=1
      self._server.registerFunction(self.api_queueGet, path='/queue', name='get')
      self._server.registerFunction(self.api_queueResult, path='/queue', name='result')
      self._server.registerFunction(self.api_parentEval, path='/parent', name='eval')
      self._server.registerFunction(self.api_parentVarCheck, path='/parent', name='varCheck')
      self._server.registerFunction(self.api_parentStats, path='/parent', name='stats')
      self._server.registerFunction(self.api_parentLock, path='/parent', name='lock')
      self._server.registerFunction(self.api_parentWait, path='/parent', name='wait')
      self._server.registerFunction(self.api_parentUnlock, path='/parent', name='unlock')
      self._server.registerFunction(self.api_parentSpeedStatsAdd, path='/parent', name='speedStatsAdd')
      self._server.registerFunction(self.api_parentIPCLock, path='/parent', name='ipc_lock')
      self._server.registerFunction(self.api_parentIPCWait, path='/parent', name='ipc_wait')
      self._server.registerFunction(self.api_parentIPCUnlock, path='/parent', name='ipc_unlock')
      self._server.start()

   def stop(self, server, timeout=20, processingDispatcherCountMax=0):
      # stop process's pool
      mytime=getms()
      self._forceStop=True
      while True:
         server._sleep(self.settings['sleepTime_checkPoolStopping'])
         tArr=[p for p in self._pool if p.is_alive()]
         if not len(tArr): break
         elif timeout and getms()-mytime>=timeout*1000:
            server._logger(3, 'Terminate child-proceses (%s) by timeout'%(len(tArr)))
            for p in tArr:
               try:
                  p.terminate()
                  server._logger(4, 'Terminated child-process <%s>'%p._id)
               except Exception, e:
                  server._logger(4, 'Error while terminating child-process <%s>: %s'%(p._id, e))
            break
      self._pool=[]
      self._forceStop=False
      # stop api
      self._server.stop(timeout=timeout-(getms()-mytime)/1000.0)
      self._server=None
      self.token=None

   def add(self, uniqueId, dataIn, request, isJSONP=False):
      #callback for adding request to queue
      try:
         request=self._parentServer._copyRequestContext(request)
         self.queue.append({'uniqueId':uniqueId, 'isJSONP':isJSONP, 'dataIn':dataIn, 'request':request, 'mytime':getms()})
         return True, len(self.queue), None
      except Exception, e:
         print '!!! ERROR execBackend_parallelWithSocket.add', e
         return False, str(e), None

   def check(self, uniqueId, _):
      if not self.settings['saveResult']: #! maybe this case must be error
         return None, None, '<saveResult> is False'
      mytime=getms()
      queueResult=self.queueResult
      while uniqueId not in queueResult:
         self._parentServer._sleep(self.settings['sleepTime_resultCheck'])
      self._parentServer._speedStatsAdd('execBackend_check', getms()-mytime)
      tArr=queueResult[uniqueId]
      del queueResult[uniqueId]
      return tArr[0], tArr[1], tArr[2] # status, params, result

   def stats(self, inMS=False, history=10):
      r={
         '%s_queue'%self._id:len(self.queue),
         '%s_api'%self._id:self._server.stats(inMS=inMS, history=history)
      }
      return r

   def sendRequest(self, path, method, params=None, notif=False):
      mytime=getms()
      if params is None: params=[]
      headers={'Token':self.token, 'Accept-Encoding':'gzip'}
      if isArray(method): #always like notify-batch
         data=[{'jsonrpc': '2.0', 'method': v['method'], 'params':v['params']} for v in method]
      else:
         data={'jsonrpc': '2.0', 'method': method, 'params':params}
         if not notif: data['id']=randomEx()
      try: data=self._server._serializeJSON(data)
      except Exception, e:
         self._server._throw('Cant serialize JSON: %s'%(e))
      if self._allowCompress and sys.getsizeof(data)>=self.settings['compressMinSize']:
         data=self._server._compressGZIP(data)
         headers['Content-Encoding']='gzip'
      sockClass=self._server._socketClass()
      _conn=self._conn if self._conn is not None else UnixHTTPConnection(self.socketPath, socketClass=sockClass)
      for i in xrange(10):
         try:
            _conn.request('POST', path, data, headers)
            if self._conn is not None: self._conn=_conn
            break
         except Exception, e:
            self._server._sleep(1)
         _conn=UnixHTTPConnection(self.socketPath, socketClass=sockClass)
      else:
         self._server._throw('Cant connect to backend-API:'%self.socketPath)
      resp=_conn.getresponse()
      data2=resp.read()
      if notif or isArray(method):
         if not isArray(method) and method!='speedStatsAdd':
            self._parentServer._speedStatsAdd(method, getms()-mytime)
         return
      if resp.getheader('Content-Encoding', None)=='gzip':
         data2=self._server._uncompressGZIP(data2)
      try: data2=self._server._parseJSON(data2)
      except Exception, e:
         self._server._throw('Cant parse JSON: %s'%(e))
      if method!='speedStatsAdd':
         self._parentServer._speedStatsAdd(method, getms()-mytime)
      if not isDict(data2): return None
      elif data2.get('error', None):
         self._server._throw('Error %s: %s'%(data2['error']['code'], data2['error']['message']))
      return data2.get('result', None)

   def sendRequestEx(self, data, async=False, cb=None, returnAllData=False):
      """
      Если <async> равен True и не задан <cb>, запрос будет отправлен как notify-request в текущем потоке. Если же <cb> задан, обычный запрос выполнится в новом потоке и вызовет <cb> по окончании.
      """
      # helper
      def tFunc(self, data, async, cb):
         data['error']=None
         try:
            data['result']=self.sendRequest(data.get('path', '/'), data['method'], data['params'], notif=async)
         except Exception, e:
            data['result']=None
            data['error']=e
         if isFunction(cb): cb(data, self)
         elif data['error']: self._server._throw(data['error'])
         return (data if returnAllData else data['result'])
      # process request
      if async and isFunction(cb):  #fully async with callback
         # if not self.settings['allowThreads']:
         #    self._server._logger(1, 'Fully async request only supported, if allowThreads==True')
         self._server._thread(tFunc, args=[self, data, False, cb])
      else:  #simple request
         return tFunc(self, data, async, cb)

   def childCicle(self, parentServer, id=0):
      self._pool=None
      self._parentServer=parentServer
      self._idOriginal=self._id
      self._id='%s#child_%s'%(self._id, id)
      self._lazyRequest={}
      self._lazyRequestLastTime=None
      self._serverOriginalMethods={}
      #we need this dummy for some methods from it and there we store gevent's status
      self._server=flaskJSONRPCServer(['', ''], gevent=(not(self.settings['disableGeventInChild']) and self.settings['allowThreads'] and self._parentServer.settings.gevent), log=self._parentServer.settings.log, jsonBackend=self._jsonBackend, tweakDescriptors=None, experimental=self._parentServer.settings.experimental, controlGC=self._parentServer.settings.controlGC)
      #select compression settings
      self._allowCompress=self.settings['allowCompress']
      if self._allowCompress is None and self._server.settings.experimental and experimentalPack.use_moreAsync and '_compressGZIP' in experimentalPack.moreAsync_methods: self._allowCompress=True
      # patching or un-patching (main program can patch themselve before execBackend will be started. in this case patched version of libs fall in child process)
      self._server._importAll(forceDelete=True)
      # prepare connection for sendRequest
      if self.settings['allowThreads']:
         # in threaded mode (also gevent) we can't use same socket for concurrent connections
         self._conn=None
      else:
         self._conn=UnixHTTPConnection(self.socketPath, socketClass=self._server._socketClass())
      # create hashmap for parentGlobals
      self.parentGlobals_oldHash={}
      if self.settings['importGlobalsFromParent']:
         for k, v in self.parentGlobals.iteritems():
            if not isinstance(v, self.settings['importGlobalsFromParent_typeForVarCheck']): continue
            h=self.var2hash(v, k)
            if h: self.parentGlobals_oldHash[k]=h
      # overload some methods in parentServer (becouse _callDispatcher will be executed in his context)
      self.childDisableNotImplemented()
      self._parentServer.stats=lambda inMS=False: self.sendRequest('/parent', 'stats', [inMS])
      self._parentServer.lock=lambda dispatcher=None: self.sendRequest('/parent', 'lock', [(dispatcher._id if dispatcher else None)])
      self._parentServer.unlock=lambda dispatcher=None, exclusive=False: self.sendRequest('/parent', 'unlock', [(dispatcher._id if dispatcher else None), exclusive])
      self._parentServer.wait=self.childWait
      self._parentServer._speedStatsAdd=self.childSpeedStatsAdd
      # also replace some methods to version from self._server
      self.childReplaceToPatched()
      # overload logger globally for child
      self._serverOriginalMethods['_logger']=self._server._logger
      self._server._logger=self.childLogger
      self._parentServer._logger=self.childLogger
      # main cicle
      try:
         while True:
            self.childSendLazyRequest()
            if self._server._flaskJSONRPCServer__settings['controlGC']: self._server._controlGC() # call GC manually
            p=self.sendRequest('/queue', 'get')
            if p=='__stop__':
               self._server._logger(4, 'Stopping')
               sys.exit(0)
            elif p:
               if self.settings['allowThreads']:
                  self._server._thread(self.childCallDispatcher, args=[p])
                  if self._server._flaskJSONRPCServer__settings['gevent']:
                     # need small pause (really small, but not 0), for prevent greenlet switching BEFORE new greenlet started. i'm think it's bug in gevent. new greenlet must start before next line of code will be executed
                     self._server._sleep(0.001)
               else:
                  self.childCallDispatcher(p)
            elif not self.settings['persistent_queueGet']:
               # pause only need for non-persistent-mode
               self._server._sleep(self.settings['sleepTime_emptyQueue'])
      except KeyboardInterrupt: sys.exit(0)

   def childLogger(self, level, *args):
      level, args=prepDataForLogger(level, args)
      args.insert(0, '   (%s)'%self._id)
      self._serverOriginalMethods['_logger'](level, *args)

   def childSendLazyRequest(self):
      if self._lazyRequestLastTime is None: self._lazyRequestLastTime=getms()
      if self._lazyRequestLastTime is not True and getms()-self._lazyRequestLastTime<self.settings['sleepTime_lazyRequest']: return
      for rId, v in self._lazyRequest.iteritems():
         if not len(v): continue
         path=strGet(rId, '', '<')
         self._lazyRequest[rId]=v[self.settings['lazyRequestChunk']:]
         self.sendRequest(path, v[:self.settings['lazyRequestChunk']])
         if len(v)>self.settings['lazyRequestChunk']:
            self._lazyRequestLastTime=True #shedule to next call
            return
      self._lazyRequestLastTime=getms()

   def childCallDispatcher(self, p):
      self._server._logger(4, 'Processing with parallel-backend: %s()'%(p['dataIn']['method']))
      self._server.processingDispatcherCount+=1
      self._server._gcStats['processedDispatcherCount']+=1
      status, params, result=self._parentServer._callDispatcher(p['uniqueId'], p['dataIn'], p['request'], overload=self.childMagicVarOverload, isJSONP=p.get('isJSONP', False), ignoreLocking=True)
      if not self.settings['saveResult']:
         self._server.processingDispatcherCount-=1
         return
      # prepare for serialize
      convBlackList=('server', 'call', 'dispatcher')
      magicVarForDispatcher=self._parentServer._flaskJSONRPCServer__settings['magicVarForDispatcher']
      if magicVarForDispatcher in params:
         for k in convBlackList: del params[magicVarForDispatcher][k]
      self.sendRequest('/queue', 'result', [p['uniqueId'], status, params, result])
      self._server.processingDispatcherCount-=1

   def childWait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      # parentServer.wait() is more complicated, becose it must check lock-status in parent, but suspend child
      sleepMethod=sleepMethod or self._server._sleep
      while self.sendRequest('/parent', 'wait', [(dispatcher._id if dispatcher else None), returnStatus]):
         if returnStatus: return True
         sleepMethod(self.settings['sleepTime_waitLock'])
      if returnStatus: return False

   def childIPCWait(self, lockId, sleepMethod=None, returnStatus=False, andLock=False):
      # parentServer.wait() is more complicated, becose it must check lock-status in parent, but suspend child
      sleepMethod=sleepMethod or self._server._sleep
      while self.sendRequest('/parent', 'ipc_wait', [lockId, returnStatus, andLock]):
         if returnStatus: return True
         sleepMethod(self.settings['sleepTime_waitLock'])
      if returnStatus: return False

   def childSpeedStatsAdd(self, name, val):
      rId='/%s/<%s>'%('parent', 'speedStatsAdd')
      if rId not in self._lazyRequest: self._lazyRequest[rId]=[]
      if not len(self._lazyRequest[rId]):
         self._lazyRequest[rId].append({'path':'/parent', 'method':'speedStatsAdd', 'params':[[], []]})
      self._lazyRequest[rId][0]['params'][0].append('%s_%s'%(self._id, name))
      self._lazyRequest[rId][0]['params'][1].append(val)

   def childMagicVarOverload(self, magicVarForDispatcher):
      # some overloads in _callDispatcher().magicVarForDispatcher
      magicVarForDispatcher['execBackend']=self
      magicVarForDispatcher['execBackendId']=self._idOriginal
      magicVarForDispatcher['parallelType']='withSocket'
      magicVarForDispatcher['parallelPoolSize']=self.settings['poolSize']
      magicVarForDispatcher['parallelId']=self._id
      # wrap methods for passing "magicVarForDispatcher" object
      magicVarForDispatcher['call']['execute']=lambda code, scope=None, mergeGlobals=True, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=True, mergeGlobals=mergeGlobals, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      magicVarForDispatcher['call']['eval']=lambda code, scope=None, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=False, mergeGlobals=False, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      magicVarForDispatcher['call']['copyGlobal']=lambda name, actual=True, cb=None: self.childCopyGlobal(name, actual=actual, cb=cb, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      magicVarForDispatcher['call']['IPCLock']=lambda lockId=None: self.sendRequest('/parent', 'ipc_lock', [lockId])
      magicVarForDispatcher['call']['IPCUnlock']=lambda lockId, clear=False: self.sendRequest('/parent', 'ipc_unlock', [lockId, clear])
      magicVarForDispatcher['call']['IPCWait']=self.childIPCWait
      return magicVarForDispatcher

   def childDisableNotImplemented(self):
      # disable none-implemented methods in parentServer for preventing call them from dispatcher
      whiteList=['_callDispatcher', '_checkFileDescriptor', '_compressResponse', '_copyRequestContext', '_countFileDescriptor', '_fixJSON', '_inChild', '_parseRequest', '_prepResponse', '_tweakLimit', 'fixJSON', '_countMemory', '_copyRequestContext', '_prepRequestContext', '_loadPostData']
      for name in dir(self._parentServer):
         if name.startswith('__') and name.endswith('__'): continue
         if not isFunction(getattr(self._parentServer, name)): continue
         if name not in whiteList:
            # closure for accessing correct name
            def tFunc_wrapper(name):
               def tFunc_notImplemented(*args, **kwargs):
                  self._server._throw('Method "%s" not implemented in parallel backend'%name)
               return tFunc_notImplemented
            setattr(self._parentServer, name, tFunc_wrapper(name))

   def childReplaceToPatched(self):
      # replace some methods in parentServer to patched (of modified) methods from this process
      whatList=['_compressGZIP', '_uncompressGZIP', '_fileGet', '_fileWrite', '_import', '_importAll', '_importSocket', '_importThreading', '_logger', '_parseJSON', '_serializeJSON', '_sha1', '_sha256', '_throw', '_sleep', '_thread', '_controlGC', '_patchWithGevent', '_tryGevent', '_raw_input', '_socketClass', 'callAsync']
      for name in whatList:
         setattr(self._parentServer, name, getattr(self._server, name))

   def childEval(self, code, scope=None, wait=True, cb=None, isExec=False, mergeGlobals=False, magicVarForDispatcher=None):
      #! сделать обработку ошибок и развернуть код для наглядности
      def tFunc(data, self):
         data['cb'](data['result'], data['error'], magicVarForDispatcher)
      data={'path':'/parent', 'method':'eval', 'params':[code, scope, isExec, mergeGlobals], 'cb':cb}
      return self.sendRequestEx(data, async=not(wait), cb=(tFunc if isFunction(cb) else None))

   def childCopyGlobal(self, name, actual=True, cb=None, magicVarForDispatcher=None):
      # if callback passed, method work in async mode
      nameArr=name if isArray(name) else [name]
      res={}
      if not actual and self.settings['importGlobalsFromParent']:
         # get from cache without checking
         for k in nameArr:
            res[k]=self.parentGlobals.get(k, None)
            self._server._logger(4, 'CopyGlobal var "%s": without checking'%k)
         if isFunction(cb):
            cb((res if isArray(name) else res.values()[0]), False, magicVarForDispatcher)
      else:
         nameHash=dict((k, self.parentGlobals_oldHash.get(k, None)) for k in nameArr)
         data={'path':'/parent', 'method':'varCheck', 'params':[nameHash, True], 'cb':cb, 'onlyOne':not(isArray(name))}
         def tFunc(data, self):
            if data['error']:
               if isFunction(data['cb']):
                  return data['cb'](None, data['error'], magicVarForDispatcher)
               else: self._server._throw(data['error'])
            res={}
            for k, r in data['result'].iteritems():
               if not r[0]: # not changed
                  res[k]=self.parentGlobals.get(k, None)
                  self._server._logger(4, 'CopyGlobal var "%s": not changed'%k)
               elif r[1] is None: # not founded or not hashable
                  res[k]=None
                  if k in self.parentGlobals:
                     del self.parentGlobals_oldHash[k]
                     del self.parentGlobals[k]
                  self._server._logger(4, 'CopyGlobal var "%s": not founded or not hashable'%k)
               else: # changed
                  v=r[2]
                  # need to deseriolize value
                  v=self._server._parseJSON(v)
                  res[k]=v
                  self.parentGlobals_oldHash[k]=r[1]
                  self.parentGlobals[k]=v
                  self._server._logger(4, 'CopyGlobal var "%s": changed'%k)
            if isFunction(data['cb']):
               data['cb']((res if not data['onlyOne'] else res.values()[0]), False, magicVarForDispatcher)
            else: data['result']=res
         res=self.sendRequestEx(data, async=isFunction(cb), cb=tFunc)
         if isFunction(cb): return
      #return result
      if isArray(name):
         # sorting result in same order, that requested
         return [res[k] for k in name]
      else:
         return res.values()[0]

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
         self._server._logger(1, 'ERROR: Cant hash variable "%s(%s)": %s'%(name, type(var), e))
         if returnSerialized: return None, None
         else: return None

   def api_queueGet(self, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      # get task
      queue=self.queue
      if self._forceStop: return '__stop__'
      elif not len(queue):
         if not self.settings['persistent_queueGet']: return None
         else:
            while not len(queue):
               if self._forceStop: return '__stop__'
               if self._parentServer.exited: sys.exit(0)
               self._server._sleep(self.settings['sleepTime_emptyQueue'])
      tArr1=queue.popleft()
      if self.settings['saveResult']:
         self._server.processingDispatcherCount+=1
      # check locking, so child not need this
      currentDispatcher=self._parentServer.routes[tArr1['request']['path']][tArr1['dataIn']['method']]['link']
      self._parentServer.wait(dispatcher=currentDispatcher)
      return tArr1

   def api_queueResult(self, uniqueId, status, params, result, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      # set task's result
      if not self.settings['saveResult']: return
      self.queueResult[uniqueId]=[status, params, result]
      self._parentServer.processingDispatcherCount-=1

   def api_parentStats(self, inMS, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      return self._parentServer.stats(inMS=inMS)

   def api_parentEval(self, code, scope=None, isExec=False, mergeGlobals=False, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._server._throw('Access denied') # tokens not match
      # eval code in parent process
      if not isExec and mergeGlobals:
         self._server._throw('Merging globals work only with isExec=True')
      try:
         # prepare scope
         if scope is None: #auto import from parent
            scope=self._parentServer._importGlobalsFromParent(typeOf=self.settings['importGlobalsFromParent_typeForEval'])
         elif not scope: scope={} #empty
         elif not isDict(scope): # scope passed as names or some scopes
            scope=scope if isArray(scope) else [scope]
            tArr1={}
            tArr2=self._parentServer._importGlobalsFromParent(typeOf=self.settings['importGlobalsFromParent_typeForEval'])
            for s in scope:
               if s is None: tArr1.update(tArr2)
               elif isDict(s): tArr1.update(s)
               elif isString(s): tArr1[s]=tArr2.get(s, None)
            scope=tArr1
         # add server instance to scope
         scope['__server__']=self._parentServer
         # prepare merging code
         if mergeGlobals:
            s1=self._server._serializeJSON(mergeGlobals) if isArray(mergeGlobals) else 'None'
            s2='None'
            if isString(self.settings['mergeGlobalsToParent_typeForEval']):
               code+='\n\nfrom types import *'
               s2=self.settings['mergeGlobalsToParent_typeForEval']
            elif self.settings['mergeGlobalsToParent_typeForEval'] is not None:
               self._server._logger(1, 'ERROR: Variable "mergeGlobalsToParent_typeForEval" must be string')
            code+='\n\n__server__._mergeGlobalsToParent(globals(), filterByName=%s, typeOf=%s)'%(s1, s2)
         # execute
         s=compile(code, '<string>', 'exec' if isExec else 'eval')
         res=eval(s, scope, scope)
      except Exception, e:
         self._server._throw('Cant execute code: %s'%(e))
      return res

   def api_parentVarCheck(self, nameHash, returnIfNotMatch=True, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._server._throw('Access denied') # tokens not match
      if not isDict(nameHash):
         self._server._throw('<nameHash> must be a dict')
      res={}
      # we use <typeOf> as callback for constructing result
      def tFunc1(k, v):
         if self.settings['importGlobalsFromParent_typeForVarCheck'] and not isinstance(v, self.settings['importGlobalsFromParent_typeForVarCheck']): # not supported variable's type
            res[k]=[True, None, None]
         else:
            vHash, vSerialized=self.var2hash(v, k, returnSerialized=True)
            if vHash is None: res[k]=[True, None, None]
            elif vHash==nameHash[k]: res[k]=[False, vHash, None]
            else:
               res[k]=[True, vHash, (vSerialized if returnIfNotMatch else None)]
         return False
      self._parentServer._importGlobalsFromParent(filterByName=nameHash.keys(), typeOf=tFunc1)
      return res

   def api_parentLock(self, dispatcherId=None, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      if dispatcherId is None: dispatcher=None
      elif not isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._parentServer._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      self._parentServer.lock(dispatcher=dispatcher)

   def api_parentUnlock(self, dispatcherId=None, exclusive=False, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      if dispatcherId is None: dispatcher=None
      elif not isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._parentServer._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      self._parentServer.unlock(dispatcher=dispatcher, exclusive=exclusive)

   def api_parentWait(self, dispatcherId=None, ignorePersistent=False, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      if dispatcherId is None: dispatcher=None
      elif not isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._server._throw('Wrong dispatcherId: %s'%dispatcherId)
      else:
         dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
      if self.settings['persistent_waitLock'] and not ignorePersistent:
         self._parentServer.wait(dispatcher=dispatcher)
         return False
      else:
         return self._parentServer.wait(dispatcher=dispatcher, returnStatus=True)

   def api_parentSpeedStatsAdd(self, name, val, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      self._parentServer._speedStatsAdd(name, val)

   def _IPCLock(self, lockId=None):
      """
      IPC locking - mechanism, that allows syncing different child-processes.
      """
      if lockId is None:
         lockId=randomEx(vals=self._IPCLock_queue)
      if lockId not in self._IPCLock_queue: self._IPCLock_queue[lockId]=1
      else: self._IPCLock_queue[lockId]+=1
      return lockId

   def api_parentIPCLock(self, lockId=None, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      return self._IPCLock(lockId)

   def api_parentIPCUnlock(self, lockId, clear=False, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      if lockId not in self._IPCLock_queue: return None
      s=self._IPCLock_queue[lockId]-1
      self._IPCLock_queue[lockId]=s
      if s<1 or clear:
         del self._IPCLock_queue[lockId]
         return False
      return s

   def api_parentIPCWait(self, lockId, ignorePersistent=False, andLock=True, _connection=None):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match
      if lockId not in self._IPCLock_queue:
         if andLock: self._IPCLock(lockId)
         return False
      elif self.settings['persistent_waitLock'] and not ignorePersistent:
         while lockId in self._IPCLock_queue:
            self._server._sleep(self.settings['sleepTime_waitLock'])
         if andLock: self._IPCLock(lockId)
         return False
      else:
         if andLock:
            self._server._throw('IPCWait: You cant use both <andLock> and <ignorePersistent>')
         return self._IPCLock_queue[lockId]
