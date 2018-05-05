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
   :param float sleepTime_checkPoolStopping:
   :param bool allowThreads:
   :param bool saveResult:
   :param bool persistent_queueGet:
   :param bool persistent_waitLock:
   :param bool useCPickle:
   :param bool disableGeventInChild:
   """

   def __init__(self, id='execBackend_parallelWithSocketNew', poolSize=1, importGlobalsFromParent=True, parentGlobals=None, sleepTime_waitLock=0.05, sleepTime_IPCFlag=0.05, sleepTime_checkPoolStopping=0.3, blocking=False, saveResult=True, persistent_waitLock=True, disableGeventInChild=False, overloadMagicVarInParent=True, lockingMode='fast'):
      self.settings={
         'poolSize':poolSize,
         'poolStrategy':'round-robin',
         'sleepTime_waitLock':sleepTime_waitLock,
         'sleepTime_IPCFlag':sleepTime_IPCFlag,
         'persistent_waitLock':persistent_waitLock,
         'sleepTime_checkPoolStopping':sleepTime_checkPoolStopping,
         'importGlobalsFromParent':importGlobalsFromParent,
         'blocking':blocking,
         'lazyRequestChunk':1000,
         'allowCompress':None,  #if None, auto select mode
         'compressMinSize':1*1024*1024,
         'saveResult':saveResult,
         'disableGeventInChild':disableGeventInChild,
         'importGlobalsFromParent_typeForEval':None,
         'importGlobalsFromParent_typeForVarCheck':[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, DictType, ListType, TupleType],
         'mergeGlobalsToParent_typeForEval':'[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, TupleType]',  #must be string
         'overloadMagicVarInParent':overloadMagicVarInParent,
         'lockingMode':lockingMode
      }
      self.parentGlobals=parentGlobals or {}
      self._pool_child=[]
      self._poolApi_child=[]
      self._poolApi_child_i=0
      self._poolApi_parent=None
      self._poolApi_broadcast=[]
      self._server=None
      self._parentServer=None
      self._serverOriginalMethods={}
      self._parentServerOriginalMethods={}
      self._id=id
      if not saveResult: self._id+='NoResult'
      self._server_listener=None
      self._jsonBackend=None
      self._IPCFlag={}

   def start(self, server):
      if self._server: return
      # warnings
      # convert to tuple
      if self.settings['importGlobalsFromParent_typeForVarCheck'] is not None and not isTuple(self.settings['importGlobalsFromParent_typeForVarCheck']):
         self.settings['importGlobalsFromParent_typeForVarCheck']=tuple(self.settings['importGlobalsFromParent_typeForVarCheck'])
      # choise json-backend
      if self._jsonBackend is None:
         self._jsonBackend=server.jsonBackend
      # generate access token
      self.token='--'.join([randomEx() for i in xrange(30)])
      # link to parentServer
      self._parentServer=server
      #select compression settings
      self._allowCompress=self.settings['allowCompress']
      if self._allowCompress is None and server.settings.experimental and experimentalPack.use_moreAsync and '_compressGZIP' in experimentalPack.moreAsync_methods: self._allowCompress=True
      # import parent's globals if needed
      if self.settings['importGlobalsFromParent']:
         deniedNames=['__builtins__']  #!add other
         server._importGlobalsFromParent(scope=self.parentGlobals, typeOf=self.settings['importGlobalsFromParent_typeForVarCheck'], filterByName=deniedNames, filterByNameReversed=True)
      # generate uds-sockets for api
      for i in xrange(self.settings['poolSize']):
         s='%s/.%s.%s#child_%s.sock'%(getScriptPath(), getScriptName(withExt=False), self._id, i)
         self._poolApi_child.append(s)
      s='%s/.%s.%s#parent.sock'%(getScriptPath(), getScriptName(withExt=False), self._id)
      self._poolApi_parent=s
      # start processes pool
      if server.settings.gevent:
         from ..utils import gmultiprocessing as mp
      else:
         import multiprocessing as mp
      self._idOriginal=self._id
      self._inChild=True
      for i in xrange(self.settings['poolSize']):
         self._id='%s#child_%s'%(self._idOriginal, i)
         self._server_listener=self._poolApi_child[i]
         self._server_initBroadcasting()
         # run child process
         p=mp.Process(target=self.childCicle)
         p.daemon=True
         p.start()
         setattr(p, '_id', self._id)
         self._pool_child.append(p)
         server._logger(4, 'Started child-process <%s>'%p._id)
      # init vars
      self._inChild=False
      if self.settings['overloadMagicVarInParent']:
         server._addMagicVarOverloader(self._parentMagicVarOverload)
      self._id=self._idOriginal
      self._server_listener=self._poolApi_parent
      self._server_initBroadcasting()
      # create api-server in parent
      self._server=flaskJSONRPCServer(self._server_initListener(), blocking=False, cors=False, gevent=self._parentServer.settings.gevent, debug=False, log=self._parentServer.settings.log, fallback=False, allowCompress=self._allowCompress, compressMinSize=self.settings['compressMinSize'], jsonBackend=self._jsonBackend, tweakDescriptors=None, notifBackend='threaded', dispatcherBackend='simple', experimental=self._parentServer.settings.experimental, controlGC=False, name='API_of_<%s>'%self._id)
      self._server_initAPI(forChild=False)
      # init rpc sender
      self.sendRequest=rpcSender(self._server, compressMinSize=1*1024*1024, updateHeaders=self._rpcSender_updateHeaders, protocolDefault='uds')
      # overload some methods in parentServer for compatibility with this backend
      self._parentServer_replaceToBroadcasted()
      # run api
      self._server.start()

   def _rpcSender_updateHeaders(self, headers):
      headers['Token']=self.token

   def _server_initBroadcasting(self):
      """ Collect api-paths for all childs and parents, exclude self api. """
      tArr=self._poolApi_child+[self._poolApi_parent]
      self._poolApi_broadcast=tuple(s for s in tArr if s!=self._server_listener)

   def _server_initListener(self):
      """ Create listeners for self api. """
      sockClass=self._parentServer._socketClass()
      l=self._parentServer._initListenerUDS(self._server_listener, sockClass=sockClass)
      return (self._server_listener, l)

   def _server_initAPI(self, forChild=False):
      """ Register api-dispatchers automatically, separated for parents and childs. Also tweaks some server settings. """
      self._server.settings.antifreeze_batchMaxTime=1*1000
      self._server.settings.antifreeze_batchBreak=False
      self._server.settings.antifreeze_batchSleep=1
      token='apiChild_' if forChild else 'apiParent_'
      def tFunc0(self, name, link):
         if name.startswith('apiBoth_'):
            return True, name[8:], link
         elif name.startswith(token):
            return True, name[len(token):], link
         return False, None, None
      self._server.registerInstance(self, path='/', filter=tFunc0)

   def stop(self, server, timeout=20, processingDispatcherCountMax=0):
      # stop process's pool
      mytime=getms()
      self.sendRequest.ex(self._poolApi_broadcast, '/',
         ('stop', [timeout, processingDispatcherCountMax])
      )
      while True:
         server._sleep(self.settings['sleepTime_checkPoolStopping'])
         tArr=[p for p in self._pool_child if p.is_alive()]
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
      # reset vars
      self._pool_child=[]
      self._poolApi_child=[]
      self._poolApi_child_i=0
      self._poolApi_parent=None
      self._poolApi_broadcast=[]
      #! при остановке не сбрасывается self.parentGlobals, поскольку не ясно как вести себя в случае, если он передан извне
      # restore original methods in parent server
      for k, v in self._parentServerOriginalMethods: setattr(self._parentServer, k, v)
      self._parentServerOriginalMethods={}
      # stop api
      self._server.stop(timeout=timeout-(getms()-mytime)/1000.0)
      self._server=None
      self._serverOriginalMethods={}
      self.token=None

   def add(self, uniqueId, data, request, isJSONP=False):
      """ Callback for processing request and get result. This backend not contains 'check()', so server will use this method for complete processing. """
      # select current child for processing task
      ps=self.settings['poolStrategy']
      i=None
      l=len(self._poolApi_child)
      if ps=='round-robin':
         i=self._poolApi_child_i
         i+=1
         if i>=l: i=0
         self._poolApi_child_i=i
      else:
         return False, None, 'Unknown pool strategy: %s'%ps
      # execute task
      notify=data['id'] is None
      if not notify:
         self._parentServer.processingDispatcherCount+=1
      try:
         # check locking, so child not need this
         currentDispatcher=self._parentServer.routes[request['path']][data['method']]['link']
         self._parentServer.wait(dispatcher=currentDispatcher)
         # call dispatcher in child
         request=self._parentServer._copyRequestContext(request)
         status, params, result=self.sendRequest(self._poolApi_child[i], '/', ('callDispatcher', [uniqueId, data, request, isJSONP], notify))
      except Exception, e:
         status, params, result=False, None, e
      if not notify:
         self._parentServer.processingDispatcherCount-=1
      return status, params, result

   def stats(self, inMS=False, history=10):
      # collect stats from child
      data=self.sendRequest.ex(self._poolApi_broadcast, '/',('stats', [inMS, history]))
      res=dict((_id, tArr) for _id, tArr in data)
      # add parentProcess's api stats to result
      res['api']=self._server.stats(inMS=inMS, history=history)
      return res

   def childCicle(self):
      self._pool_child=None
      self._parentServer.execBackend={}
      # create api-server in child
      self._useGevent=not(self.settings['disableGeventInChild']) and self._parentServer.settings.gevent
      self._server=flaskJSONRPCServer(self._server_initListener(), blocking=self.settings['blocking'], cors=False, gevent=self._useGevent, debug=False, log=self._parentServer.settings.log, fallback=False, allowCompress=self._allowCompress, compressMinSize=self.settings['compressMinSize'], jsonBackend=self._jsonBackend, tweakDescriptors=None, notifBackend='threaded', dispatcherBackend='simple', experimental=self._parentServer.settings.experimental, controlGC=self._parentServer.settings.controlGC, name='API_of_<%s>'%self._id)
      # patching or un-patching (main program can patch themselve before execBackend will be started. in this case patched version of libs fall in child process)
      self._server._importAll(forceDelete=True)
      # create hashmap for parentGlobals
      self.parentGlobals_oldHash={}
      if self.settings['importGlobalsFromParent']:
         for k, v in self.parentGlobals.iteritems():
            if not isinstance(v, self.settings['importGlobalsFromParent_typeForVarCheck']): continue
            h=self.var2hash(v, k)
            if h: self.parentGlobals_oldHash[k]=h
      # overload some methods in parentServer (becouse _callDispatcher will be executed in his context)
      self._parentServer_disableNotImplemented()
      self._parentServer_replaceChildChecker()
      self._parentServerOriginalMethods['stats']=self._parentServer.stats
      self._parentServer.stats=self.childStats
      self._parentServer._speedStatsAdd('test', 1)
      # self._parentServer._speedStatsAdd=self._server._speedStatsAdd
      self._parentServer_replaceToBroadcasted()
      # also replace some methods to version from self._server
      self._parentServer_replaceToPatched()
      # overload logger globally for child
      self._serverOriginalMethods['_logger']=self._server._logger
      self._server._logger=self.childLogger
      self._parentServer._logger=self.childLogger
      # init rpc sender
      self.sendRequest=rpcSender(self._server, compressMinSize=1*1024*1024, updateHeaders=self._rpcSender_updateHeaders, protocolDefault='uds')
      # run api
      self._server_initAPI(forChild=True)
      self._server.serveForever()

   def _parentServer_disableNotImplemented(self):
      """ Disable none-implemented methods in parentServer for preventing call them from dispatcher. """
      # important, it's white-list, so all other method will be re-defined to NotImplemented
      whiteList=('_callDispatcher', '_checkFileDescriptor', '_compressResponse', '_copyRequestContext', '_countFileDescriptor', '_fixJSON', '_inChild', '_parseRequest', '_prepResponse', '_tweakLimit', 'fixJSON', '_countMemory', '_copyRequestContext', '_prepRequestContext', '_loadPostData', 'lock', 'unlock', 'wait', '_speedStatsAdd', 'stats')
      for name in dir(self._parentServer):
         if name.startswith('__') and name.endswith('__'): continue
         link=getattr(self._parentServer, name)
         if not isFunction(link): continue
         if name not in whiteList:
            self._parentServerOriginalMethods[name]=link
            # closure for accessing correct name
            def tFunc_wrapper(name):
               def tFunc_notImplemented(*args, **kwargs):
                  self._server._throw('Method "%s" not implemented in parallel backend'%name)
               return tFunc_notImplemented
            setattr(self._parentServer, name, tFunc_wrapper(name))

   def _parentServer_replaceToPatched(self):
      """ Replace some methods in parentServer to patched (or modified) methods from child process. """
      whatList=('_compressGZIP', '_uncompressGZIP', '_fileGet', '_fileWrite', '_import', '_importAll', '_importSocket', '_importThreading', '_logger', '_parseJSON', '_serializeJSON', '_sha1', '_sha256', '_throw', '_sleep', '_thread', '_controlGC', '_patchWithGevent', '_tryGevent', '_raw_input', '_socketClass', 'callAsync')
      for name in whatList:
         self._parentServerOriginalMethods[name]=getattr(self._parentServer, name)
         setattr(self._parentServer, name, getattr(self._server, name))

   def _parentServer_replaceToBroadcasted(self):
      """ Replace some methods in parentServer to modified, that send broadcast message on execute. """
      whatList={
         'lock':self.broadcastedLock,
         'unlock':self.broadcastedUnlock
      }
      for name, link in whatList.iteritems():
         self._parentServerOriginalMethods[name]=getattr(self._parentServer, name)
         setattr(self._parentServer, name, link)

   """
   сейчас обычные блокировки выполнены по принципу рассылки события.
   это работает быстро, но в процессе работы диспетчеры мы не можем гарантировать, что чтото не изменилось.
   для этого существуют IPCFlag, гарантирующие атомарные и синхронные состояния флагов.
   нужно давать возможность менять режим блокировок при инициализации бекенда (параметр <lockingMode>), один из режимов быстрый, второй через IPCFlag
   """

   def broadcastedLock(self, dispatcher=None):
      self._parentServerOriginalMethods['lock'](dispatcher=dispatcher)
      self.sendRequest.ex(self._poolApi_broadcast, '/',
         ('lock', [dispatcher._id if dispatcher else None])
      )

   def broadcastedUnlock(self, dispatcher=None, exclusive=False):
      self._parentServerOriginalMethods['unlock'](dispatcher=dispatcher, exclusive=exclusive)
      self.sendRequest.ex(self._poolApi_broadcast, '/',
         ('unlock', [dispatcher._id if dispatcher else None, exclusive])
      )

   def _parentServer_replaceChildChecker(self):
      self._parentServerOriginalMethods['_inChild']=getattr(self._parentServer, '_inChild')
      setattr(self._parentServer, '_inChild', self.childInChild)

   def childInChild(self, name=None):
      """
      Normally, server disallow some methods to be executed from child process. We need to override this behavior for some specific methods.
      """
      if not name:
         name=sys._getframe(1).f_code.co_name  #get name of caller
      if name in ('lock', 'unlock'): return None
      else: return True

   def childStats(self, inMS=False, history=10):
      return self.sendRequest.ex(self._poolApi_parent, '/', ('stats', [inMS, history]))

   def childLogger(self, level, *args):
      level, args=prepDataForLogger(level, args)
      args.insert(0, '   (%s)'%self._id)
      self._serverOriginalMethods['_logger'](level, *args)

   def _childIPCFlag_capture(self, lockId=None, limit=1, block=True, onlyExisted=False, sleepMethod=None, timeout=None):
      if limit is not None and (not isNum(limit) or limit<1):
         self._server._throw('Param "limit" must be positive integer or None')
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      needId=False
      _IPCFlag=self._IPCFlag
      # prepare new or exist flag
      if lockId is None:
         lockId=randomEx(vals=_IPCFlag)
         _IPCFlag[lockId]=0
         needId=True
      elif lockId not in _IPCFlag:
         if not onlyExisted: _IPCFlag[lockId]=0
      # synchronize with parent
      tArr=(self._poolApi_parent, '/', ('IPCFlag_capture', [lockId, onlyExisted, limit, self._server_listener]))
      _sendRequest=self.sendRequest
      mytime=getms()
      status=_sendRequest(*tArr)
      # if <limit> is None and <onlyExisted> if False, parent always returns True
      if not status:  #somebody captured this flag already, we need to wait
         if not block: return False
         # enter in queue
         timeout=timeout*1000 if timeout else None
         sleepMethod=sleepMethod or self._server._sleep
         sleepTime=self.settings['sleepTime_IPCFlag']
         while not status:
            if timeout and getms()-mytime>=timeout: return False
            sleepMethod(sleepTime)
            status=_sendRequest(*tArr)
      # set flag in current process
      _IPCFlag[lockId]+=1
      return lockId if needId else True

   def _parentIPCFlag_capture(self, lockId=None, limit=1, block=True, onlyExisted=False, sleepMethod=None, timeout=None):
      if limit is not None and (not isNum(limit) or limit<1):
         self._server._throw('Param "limit" must be positive integer or None')
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      needId=False
      _IPCFlag=self._IPCFlag
      _exist=lockId in _IPCFlag
      # prepare new or exist flag
      if lockId is None:
         lockId=randomEx(vals=_IPCFlag)
         _IPCFlag[lockId]=0
         needId=True
      elif not _exist:
         if not onlyExisted: _IPCFlag[lockId]=0
      # wait for conds
      if not block:
         if not _exist: return None if onlyExisted else False
         elif _IPCFlag[lockId]>=limit: return False
      else:
         mytime=getms()
         timeout=timeout*1000 if timeout else None
         sleepMethod=sleepMethod or self._server._sleep
         sleepTime=self.settings['sleepTime_IPCFlag']
         while not((_exist and _IPCFlag[lockId]<limit) or (not _exist and not onlyExisted)):
            if timeout and getms()-mytime>=timeout: return False
            sleepMethod(sleepTime)
            _exist=lockId in _IPCFlag
      # set flag in current process
      _IPCFlag[lockId]+=1
      # synchronize with others
      self.sendRequest.ex(self._poolApi_broadcast, '/', ('IPCFlag_capture', [lockId]))
      return lockId if needId else True

   def _bothIPCFlag_release(self, lockId):
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      _IPCFlag=self._IPCFlag
      if lockId in _IPCFlag:
         if _IPCFlag[lockId]>0: _IPCFlag[lockId]-=1
      self.sendRequest.ex(self._poolApi_broadcast, '/', ('IPCFlag_release', [lockId]))

   def _bothIPCFlag_get(self, lockId):
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      if lockId in self._IPCFlag: return self._IPCFlag[lockId]
      else: return None

   def _bothIPCFlag_check(self, lockId, value=0, block=True, onlyExisted=True, sleepMethod=None, timeout=None):
      """
      Проверяет, существует ли флаг и равен ли его счетчик переданному значению. При <onlyExisted> is False, несуществующий флаг считается прошедшим проверку. Параметр <block> переключает блокирующий режим, в котором функция ждет выполнения условия или наступления <timeout> (если он задан).
      """
      if not isNum(value) or value<0:
         self._server._throw('Param "value" must be positive integer or zero')
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      _IPCFlag=self._IPCFlag
      _exist=lockId in _IPCFlag
      if not block:
         if not _exist: return None if onlyExisted else True
         elif _IPCFlag[lockId]!=value: return False
         else: return True
      else:
         mytime=getms()
         timeout=timeout*1000 if timeout else None
         sleepMethod=sleepMethod or self._server._sleep
         sleepTime=self.settings['sleepTime_IPCFlag']
         while not((_exist and _IPCFlag[lockId]==value) or (not _exist and not onlyExisted)):
            if timeout and getms()-mytime>=timeout: return False
            sleepMethod(sleepTime)
            _exist=lockId in _IPCFlag
         return True

   def _bothIPCFlag_clear(self, lockId):
      self._server._sleep(0.001)  #we need small sleep for checking, is our API-server recivied requests
      if lockId in self._IPCFlag: del self._IPCFlag[lockId]
      self.sendRequest.ex(self._poolApi_broadcast, '/', ('IPCFlag_clear', [lockId]))

   def _bothIPCFlag_captureAsync(self, lockId, cb=None, limit=1, onlyExisted=False, forceNative=False):
      f=self._childIPCFlag_capture if self._inChild else self._parentIPCFlag_capture
      self._server.callAsync(f, kwargs={
         'lockId':lockId,
         'limit':limit,
         'onlyExisted':onlyExisted
      }, forceNative=forceNative, wait=False, cb=cb, cbData=lockId)

   def _bothIPCFlag_releaseAsync(self, lockId, cb=None, forceNative=False):
      self._server.callAsync(self._bothIPCFlag_release, kwargs={
         'lockId':lockId,
      }, forceNative=forceNative, wait=False, cb=cb, cbData=lockId)

   def _bothIPCFlag_getAsync(self, lockId, cb=None, forceNative=False):
      self._server.callAsync(self._bothIPCFlag_get, kwargs={
         'lockId':lockId,
      }, forceNative=forceNative, wait=False, cb=cb, cbData=lockId)

   def _bothIPCFlag_checkAsync(self, lockId, cb=None, value=0, onlyExisted=True, forceNative=False):
      self._server.callAsync(self._bothIPCFlag_check, kwargs={
         'lockId':lockId,
         'value':value,
         'onlyExisted':onlyExisted
      }, forceNative=forceNative, wait=False, cb=cb, cbData=lockId)

   def _bothIPCFlag_clearAsync(self, lockId, cb=None, forceNative=False):
      self._server.callAsync(self._bothIPCFlag_clear, kwargs={
         'lockId':lockId,
      }, forceNative=forceNative, wait=False, cb=cb, cbData=lockId)

   #! нужно синхронизировать состояние блокировки с стандартной реализацией, либо переопределять все её методы всегда

   # def _bothLockOverIPC(self, dispatcher=None):
   #    f=self._childIPCFlag_capture if self._inChild else self._parentIPCFlag_capture
   #    lockId=dispatcher._id if dispatcher else 'globalLocking'
   #    f(lockId=None, limit=1, block=True, onlyExisted=False, sleepMethod=None, timeout=None)

   #! а как сделать эксклюзивную разблокировку на основе IPCFlag

   # def _bothUnlockOverIPC(self, dispatcher=None, exclusive=False):
   #    self._parentServerOriginalMethods['unlock'](dispatcher=dispatcher, exclusive=exclusive)
   #    self.sendRequest.ex(self._poolApi_broadcast, '/',
   #       ('unlock', [dispatcher._id if dispatcher else None, exclusive])
   #    )

   #! метод wait должен проверять и глобальную и локальную блокировку IPCFlag

   def _childMagicVarOverload(self, magicVarForDispatcher):
      # some overloads in _callDispatcher().magicVarForDispatcher
      magicVarForDispatcher['execBackend']=self
      magicVarForDispatcher['execBackendId']=self._idOriginal
      magicVarForDispatcher['parallelType']='withSocket'
      magicVarForDispatcher['parallelPoolSize']=self.settings['poolSize']
      magicVarForDispatcher['parallelId']=self._id
      callMap=magicVarForDispatcher['call']
      # callMap['execute']=lambda code, scope=None, mergeGlobals=True, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=True, mergeGlobals=mergeGlobals, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # callMap['eval']=lambda code, scope=None, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=False, mergeGlobals=False, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # callMap['copyGlobal']=lambda name, actual=True, cb=None: self.childCopyGlobal(name, actual=actual, cb=cb, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # IPC methods
      callMap['IPCFlagCapture']=self._childIPCFlag_capture
      callMap['IPCFlagRelease']=self._bothIPCFlag_release
      callMap['IPCFlagGet']=self._bothIPCFlag_get
      callMap['IPCFlagCheck']=self._bothIPCFlag_check
      callMap['IPCFlagClear']=self._bothIPCFlag_clear
      # IPC async methods
      callMap['IPCFlagCaptureAsync']=self._bothIPCFlag_captureAsync
      callMap['IPCFlagReleaseAsync']=self._bothIPCFlag_releaseAsync
      callMap['IPCFlagGetAsync']=self._bothIPCFlag_getAsync
      callMap['IPCFlagCheckAsync']=self._bothIPCFlag_checkAsync
      callMap['IPCFlagClearAsync']=self._bothIPCFlag_clearAsync
      return magicVarForDispatcher

   def _parentMagicVarOverload(self, magicVarForDispatcher, argsPassed, currentExecBackendId, currentExecBackend):
      # some overloads in _callDispatcher().magicVarForDispatcher for parent process
      magicVarForDispatcher[self._id]=callMap=magicDict({})
      callMap['execBackend']=self
      callMap['execBackendId']=self._idOriginal
      # callMap['execute']=lambda code, scope=None, mergeGlobals=True, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=True, mergeGlobals=mergeGlobals, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # callMap['eval']=lambda code, scope=None, wait=True, cb=None: self.childEval(code, scope=scope, wait=wait, cb=cb, isExec=False, mergeGlobals=False, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # callMap['copyGlobal']=lambda name, actual=True, cb=None: self.childCopyGlobal(name, actual=actual, cb=cb, magicVarForDispatcher=weakref.ref(magicDict(magicVarForDispatcher))())
      # IPC methods
      callMap['IPCFlagCapture']=self._parentIPCFlag_capture
      callMap['IPCFlagRelease']=self._bothIPCFlag_release
      callMap['IPCFlagGet']=self._bothIPCFlag_get
      callMap['IPCFlagCheck']=self._bothIPCFlag_check
      callMap['IPCFlagClear']=self._bothIPCFlag_clear
      # IPC async methods
      callMap['IPCFlagCaptureAsync']=self._bothIPCFlag_captureAsync
      callMap['IPCFlagReleaseAsync']=self._bothIPCFlag_releaseAsync
      callMap['IPCFlagGetAsync']=self._bothIPCFlag_getAsync
      callMap['IPCFlagCheckAsync']=self._bothIPCFlag_checkAsync
      callMap['IPCFlagClearAsync']=self._bothIPCFlag_clearAsync
      return magicVarForDispatcher

   # def childEval(self, code, scope=None, wait=True, cb=None, isExec=False, mergeGlobals=False, magicVarForDispatcher=None):
   #    #! сделать обработку ошибок и развернуть код для наглядности
   #    def tFunc(data, self):
   #       data['cb'](data['result'], data['error'], magicVarForDispatcher)
   #    data={'path':'/parent', 'method':'eval', 'params':[code, scope, isExec, mergeGlobals], 'cb':cb}
   #    return self.sendRequest.ex(data, async=not(wait), cb=(tFunc if isFunction(cb) else None))

   # def childCopyGlobal(self, name, actual=True, cb=None, magicVarForDispatcher=None):
   #    # if callback passed, method work in async mode
   #    nameArr=name if isArray(name) else [name]
   #    res={}
   #    if not actual and self.settings['importGlobalsFromParent']:
   #       # get from cache without checking
   #       for k in nameArr:
   #          res[k]=self.parentGlobals.get(k, None)
   #          self._server._logger(4, 'CopyGlobal var "%s": without checking'%k)
   #       if isFunction(cb):
   #          cb((res if isArray(name) else res.values()[0]), False, magicVarForDispatcher)
   #    else:
   #       nameHash=dict((k, self.parentGlobals_oldHash.get(k, None)) for k in nameArr)
   #       data={'path':'/parent', 'method':'varCheck', 'params':[nameHash, True], 'cb':cb, 'onlyOne':not(isArray(name))}
   #       def tFunc(data, self):
   #          if data['error']:
   #             if isFunction(data['cb']):
   #                return data['cb'](None, data['error'], magicVarForDispatcher)
   #             else: self._server._throw(data['error'])
   #          res={}
   #          for k, r in data['result'].iteritems():
   #             if not r[0]: # not changed
   #                res[k]=self.parentGlobals.get(k, None)
   #                self._server._logger(4, 'CopyGlobal var "%s": not changed'%k)
   #             elif r[1] is None: # not founded or not hashable
   #                res[k]=None
   #                if k in self.parentGlobals:
   #                   del self.parentGlobals_oldHash[k]
   #                   del self.parentGlobals[k]
   #                self._server._logger(4, 'CopyGlobal var "%s": not founded or not hashable'%k)
   #             else: # changed
   #                v=r[2]
   #                # need to deseriolize value
   #                v=self._server._parseJSON(v)
   #                res[k]=v
   #                self.parentGlobals_oldHash[k]=r[1]
   #                self.parentGlobals[k]=v
   #                self._server._logger(4, 'CopyGlobal var "%s": changed'%k)
   #          if isFunction(data['cb']):
   #             data['cb']((res if not data['onlyOne'] else res.values()[0]), False, magicVarForDispatcher)
   #          else: data['result']=res
   #       res=self.sendRequest.ex(data, async=isFunction(cb), cb=tFunc)
   #       if isFunction(cb): return
   #    #return result
   #    if isArray(name):
   #       # sorting result in same order, that requested
   #       return [res[k] for k in name]
   #    else:
   #       return res.values()[0]

   def var2hash(self, var, name='<unknown>', returnSerialized=False):
      try:
         s=self._server._serializeJSON(var)
         h=self._server._sha256(s)
         if returnSerialized: return h, s
         else: return h
      except Exception, e:
         self._server._logger(1, 'Cant hash variable "%s(%s)": %s'%(name, type(var), e))
         if returnSerialized: return None, None
         else: return None

#==================== API ====================
   def _checkToken(self, _connection):
      if _connection['headers'].get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied')  #tokens not match

   """
   Methods below will be automatically registered as API-methods.

   Method, whose name started with 'apiChild_' will be registered in child process only.
   Method, whose name started with 'apiParent_' will be registered in parent process only.
   Method, whose name started with 'apiBoth_' will be registered in child and parent processes.
   """

   def apiBoth_lock(self, dispatcherId=None, _connection=None):
      self._checkToken(_connection)
      if dispatcherId is None: dispatcher=None
      else:
         try:
            dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
         except Exception, e:
            self._parentServer._throw('Wrong dispatcherId "%s": %s'%(dispatcherId, e))
      self._parentServerOriginalMethods['lock'](dispatcher=dispatcher)

   def apiBoth_unlock(self, dispatcherId=None, exclusive=False, _connection=None):
      self._checkToken(_connection)
      if dispatcherId is None: dispatcher=None
      else:
         try:
            dispatcher=self._parentServer.routes[dispatcherId['path']][dispatcherId['name']]['link']
         except Exception, e:
            self._parentServer._throw('Wrong dispatcherId "%s": %s'%(dispatcherId, e))
      self._parentServerOriginalMethods['unlock'](dispatcher=dispatcher, exclusive=exclusive)

   def apiChild_stats(self, inMS=False, history=10, _connection=None):
      self._checkToken(_connection)
      tArr=self._parentServerOriginalMethods['stats'](inMS=inMS, history=history)
      tArr['api']=self._server.stats(inMS=inMS, history=history)
      return [self._id, tArr]

   def apiChild_callDispatcher(self, uniqueId, data, request, isJSONP=False, _connection=None):
      self._checkToken(_connection)
      self._server._logger(4, 'Processing with parallel-backend: %s()'%(data['method']))
      self._parentServer.processingDispatcherCount+=1
      self._server._gcStats['processedDispatcherCount']+=1
      status, params, result=self._parentServer._callDispatcher(uniqueId, data, request, isJSONP=isJSONP, overload=self._childMagicVarOverload, ignoreLocking=True)
      if _connection['notify']:
         # for notify-request results not needed
         params, result=None, None
      else:
         # prepare for serialize
         magicVarForDispatcher=self._parentServer._flaskJSONRPCServer__settings['magicVarForDispatcher']
         if magicVarForDispatcher in params:
            convBlackList=('server', 'call', 'dispatcher', 'execBackend')
            # we cant change original object, because it can be used by dispatchers (in async methods, for example)
            params[magicVarForDispatcher]=magicVarForDispatcher=params[magicVarForDispatcher].copy()
            for k in convBlackList:
               if k in magicVarForDispatcher: del magicVarForDispatcher[k]
      self._parentServer.processingDispatcherCount-=1
      return status, params, result

   def apiChild_IPCFlag_capture(self, lockId, _connection=None):
      self._checkToken(_connection)
      _IPCFlag=self._IPCFlag
      if lockId not in _IPCFlag: _IPCFlag[lockId]=1
      else: _IPCFlag[lockId]+=1

   def apiParent_stats(self, inMS=False, history=10, _connection=None):
      self._checkToken(_connection)
      return self._parentServer.stats(inMS=inMS, history=history)

   def apiParent_IPCFlag_capture(self, lockId, onlyExisted, limit, sender, _connection=None):
      self._checkToken(_connection)
      _IPCFlag=self._IPCFlag
      if lockId not in _IPCFlag:
         if onlyExisted: return False
         _IPCFlag[lockId]=0
      if limit and _IPCFlag[lockId]>=limit: return False
      _IPCFlag[lockId]+=1
      # broadcast to others, excluding sender
      tArr=[s for s in self._poolApi_broadcast if s!=sender]
      self.sendRequest.ex(tArr, '/', ('IPCFlag_capture', [lockId]))
      return True

   def apiBoth_IPCFlag_clear(self, lockId, _connection=None):
      self._checkToken(_connection)
      if lockId in self._IPCFlag: del self._IPCFlag[lockId]

   def apiBoth_IPCFlag_release(self, lockId, _connection=None):
      self._checkToken(_connection)
      _IPCFlag=self._IPCFlag
      if lockId in _IPCFlag:
         if _IPCFlag[lockId]>0: _IPCFlag[lockId]-=1

   def apiChild_stop(self, timeout=20, processingDispatcherCountMax=0, _connection=None):
      self._checkToken(_connection)
      self._server.callAsync(self._server.stop, args=[timeout, processingDispatcherCountMax], wait=False, forceNative=True)  #? maybe forceNative=False

   # def apiParent_eval(self, code, scope=None, isExec=False, mergeGlobals=False, _connection=None):
   #    self._checkToken(_connection)
   #    # eval code in parent process
   #    if not isExec and mergeGlobals:
   #       self._server._throw('Merging globals work only with isExec=True')
   #    try:
   #       # prepare scope
   #       if scope is None:  #auto import from parent
   #          scope=self._parentServer._importGlobalsFromParent(typeOf=self.settings['importGlobalsFromParent_typeForEval'])
   #       elif not scope: scope={}  #empty
   #       elif not isDict(scope):  #scope passed as names or some scopes
   #          scope=scope if isArray(scope) else [scope]
   #          tArr1={}
   #          tArr2=self._parentServer._importGlobalsFromParent(typeOf=self.settings['importGlobalsFromParent_typeForEval'])
   #          for s in scope:
   #             if s is None: tArr1.update(tArr2)
   #             elif isDict(s): tArr1.update(s)
   #             elif isString(s): tArr1[s]=tArr2.get(s, None)
   #          scope=tArr1
   #       # add server instance to scope
   #       scope['__server__']=self._parentServer
   #       # prepare merging code
   #       if mergeGlobals:
   #          s1=self._server._serializeJSON(mergeGlobals) if isArray(mergeGlobals) else 'None'
   #          s2='None'
   #          if isString(self.settings['mergeGlobalsToParent_typeForEval']):
   #             code+='\n\nfrom types import *'
   #             s2=self.settings['mergeGlobalsToParent_typeForEval']
   #          elif self.settings['mergeGlobalsToParent_typeForEval'] is not None:
   #             self._server._logger(1, 'ERROR: Variable "mergeGlobalsToParent_typeForEval" must be string')
   #          code+='\n\n__server__._mergeGlobalsToParent(globals(), filterByName=%s, typeOf=%s)'%(s1, s2)
   #       # execute
   #       s=compile(code, '<string>', 'exec' if isExec else 'eval')
   #       res=eval(s, scope, scope)
   #    except Exception, e:
   #       self._server._throw('Cant execute code: %s'%(e))
   #    return res

   # def apiParent_varCheck(self, nameHash, returnIfNotMatch=True, _connection=None):
   #    self._checkToken(_connection)
   #    if not isDict(nameHash):
   #       self._server._throw('<nameHash> must be a dict')
   #    res={}
   #    # we use <typeOf> as callback for constructing result
   #    def tFunc1(k, v):
   #       if self.settings['importGlobalsFromParent_typeForVarCheck'] and not isinstance(v, self.settings['importGlobalsFromParent_typeForVarCheck']):  #not supported variable's type
   #          res[k]=[True, None, None]
   #       else:
   #          vHash, vSerialized=self.var2hash(v, k, returnSerialized=True)
   #          if vHash is None: res[k]=[True, None, None]
   #          elif vHash==nameHash[k]: res[k]=[False, vHash, None]
   #          else:
   #             res[k]=[True, vHash, (vSerialized if returnIfNotMatch else None)]
   #       return False
   #    self._parentServer._importGlobalsFromParent(filterByName=nameHash.keys(), typeOf=tFunc1)
   #    return res
