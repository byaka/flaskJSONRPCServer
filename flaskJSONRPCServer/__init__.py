#!/usr/bin/env python
# -*- coding: utf-8 -*

__ver_major__ = 0
__ver_minor__ = 9
__ver_patch__ = 2
__ver_sub__ = "dev"
__version__ = "%d.%d.%d" % (__ver_major__, __ver_minor__, __ver_patch__)
"""
This library is an extended implementation of server for JSON-RPC protocol. It supports only json-rpc 2.0 specification for now, which includes batch submission, keyword arguments, notifications, etc.

:authors: John Byaka
:copyright: Copyright 2016, Buber
:license: Apache License 2.0

:license:

   Copyright 2016 Buber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import sys, inspect, random, decimal, json, datetime, time, os, imp, hashlib, threading, gc, socket, Cookie, httplib, wsgiref.util
from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType
from cStringIO import StringIO
from gzip import GzipFile
gevent=None
geventMonkey=None
geventSocket=None
geventFileObjectThread=None

from utils import *

import execBackend as execBackendCollection
import servBackend as servBackendCollection
from postprocess import postprocess

try:
   import experimental as experimentalPack
   experimentalPack.initGlobal(globals())
except ImportError, e:
   print 'EXPERIMENTAL package not loaded:', e

class MainError(Exception):
   """ Main error class for flaskJSONRPCServer. """
   pass

class flaskJSONRPCServer:
   """
   Main class of server.

   :param list ipAndPort: List or sequence, containing IP and PORT or SOCKET_PATH and SOCKET.
   :param bool multipleAdress: If True, <ipAndPort> must be list, containing different <ipAndPort>. All of them will be binded to this server.
   :param bool blocking: Switch server to blocking mode (only one request per time will be processed).
   :param bool|dict cors: Add CORS headers to output (Access-Control-Allow-*). If 'dict', can contain values for <origin> and <method>.
   :param bool gevent: Patch Serv-backend and all process with Gevent.
   :param bool debug: Allow log messages from WSGI-backend.
   :param int|bool log: Set log-level or disable log messages about activity of flaskJSONRPCServer. If it's <int>, set log-level. 1 is error, 2 is warning, 3 is info, 4 is debug.
   :param bool fallback: Automatically accept and process JSONP requests.
   :param bool allowCompress: Allowing compression of output.
   :param list ssl: List or sequence, containing KEY and CERT. If passed, WSGI-backend will be switched to SSL protocol.
   :param list(int,int) tweakDescriptors: List containing new soft and hard limits of file-descriptors for current process.
   :param int compressMinSize: Max length of output in bytes that was not compressed.
   :param str|obj jsonBackend: Select JSON-backend for json.loads() and json.dumps(). If this parameter 'str' type, module with passed name will be imported.  If this parameter 'obj' type, it must contain methods loads() and dumps().
   :param str|dict|'simple' dispatcherBackend: Select default dispatcher-exec-backend for processing regular requests. Lib include some prepared backends. Variable <execBackendCollection.execBackendMap> contained all of them. If this parameter 'dict' type, it must contain 'add' key as function, that will be called on every notify-request and recive all data about request, and '_id' key, containing unique identificator. Also it must contain 'check' function, that will be called for waiting result of processed requests. Optionally it can contain 'start' and 'stop' keys as functions (it will be called when server starting or stopping).
   :param str|dict|'simple' notifBackend: Select default dispatcher-exec-backend for processing notify-requests. Lib include some prepared backends. Variable <execBackendCollection.execBackendMap> contained all of them. If this parameter 'dict' type, it must contain 'add' key as function, that will be called on every notify-request and recive all data about request, and '_id' key, containing unique identificator. Optionally it can contain 'start' and 'stop' keys as functions (it will be called when server starting or stopping).
   :param func auth: This function will be called on every request to server 9before processing it) and must return status as 'bool' type.
   :param bool experimental: If 'True', server will be patched with 'experimental' package.
   :param bool controlGC: If 'True', server will control GarbageCollector and manually call 'gc.collect()' (by default every 30 minutes or 150k requests or 50k dispatcher's calls).
   :param str magicVarForDispatcher: Name for variable, that can be passed to every dispatcher and will contain many useful data and methods. For more info see <server>.aboutMagicVarForDispatcher.
   :param str name: Optional name of server. If not passed, it will be generated automatically.
   :param str|dict|'auto' servBackend: Select serving-backend. Lib include some prepared backends. Variable <servBackendCollection.servBackendMap> contained all of them. If this parameter 'dict' type, it must contain 'start' key as function, that will be called on server's start, and '_id' key, containing unique identificator. Optionally it can contain 'stop' key as function (it will be called when server stopping).
   """

   def __init__(self, bindAdress, multipleAdress=False, blocking=False, cors=False, gevent=False, debug=False, log=3, fallback=True, allowCompress=False, ssl=False, tweakDescriptors=False, compressMinSize=1*1024*1024, jsonBackend='json', notifBackend='simple', dispatcherBackend='simple', auth=None, experimental=False, controlGC=True, magicVarForDispatcher='_connection', name=None, servBackend='auto'):
      self.started=False  #indicate is server started
      self.exited=False  #indicate is server (and main process) wait for terminating, useful for exec-backends
      self._pid=os.getpid()
      # prepare speedStats
      self.speedStats={}
      self.speedStatsMax={}
      # tweak descriptor's limit
      self._tweakLimit(tweakDescriptors)
      # init settings
      self.settings=magicDictCold({
         'multipleAdress':False,
         'fakeListener':False,
         'ip':[],
         'port':[],
         'socketPath':[],
         'socket':[],
         'blocking':blocking,
         'fallback_JSONP':fallback,
         'postprocess':{
            'byStatus':{}
         },
         'CORS':cors,
         'gevent':gevent,
         'servBackend':servBackend,
         'debug':debug,
         'log':log,
         'allowCompress':allowCompress,
         'compressMinSize':compressMinSize,
         'ssl':ssl,
         'sleepTime_checkProcessingCount':0.3,
         'sleepTime_waitLock':0.1,
         'sleepTime_waitDeepLock':0.1,
         'antifreeze_batchMaxTime':0.5*1000,
         'antifreeze_batchSleep':0.5,
         'antifreeze_batchBreak':False,
         'auth':auth,
         'experimental':experimental,
         'controlGC':controlGC,
         'controlGC_everySeconds':3*60,  # every 30 minutes
         'controlGC_everyRequestCount':150*1000,  # every 150k requests
         'controlGC_everyDispatcherCount':150*1000,  # every 150k dispatcher's calls
         'backlog':10*1000,
         'magicVarForDispatcher':magicVarForDispatcher
      })
      self.setts=self.settings  #backward compatible
      self.__settings=self.settings  #after server starts we copy settings here like dict() for bursting performance and avoid of changing settings
      # set name
      self.name=name or randomEx(10**4, pref='flaskJSONRPCServer_<', suf='>')
      self.version=__version__
      if not bindAdress:
         # fake server without listeners
         self.settings['fakeListener']=True
      else:
         # set adress for real listeners
         self.settings['multipleAdress']=multipleAdress
         bindAdress=bindAdress if multipleAdress else [bindAdress]
         for bind in bindAdress:
            tArr={'ip':None, 'port':None, 'socketPath':None, 'socket':None}
            if isString(bind):
               if not checkPath(bind):
                  self._throw('Wrong path for UDS socket: %s'%bind)
               tArr['socketPath']=bind
            else:
               if len(bind)!=2:
                  self._throw('Wrong "bindAdress" parametr: %s'%bind)
               isSocket=str(type(bind[1])) in ["<class 'socket._socketobject'>", "<class 'gevent.socket.socket'>", "<class 'gevent._socket2.socket'>"]
               if isSocket:
                  tArr['socketPath']=bind[0]
                  tArr['socket']=bind[1]
               else:
                  tArr['ip']=bind[0]
                  tArr['port']=bind[1]
            for k, v in tArr.iteritems():
               self.settings[k].append(v)
      # other
      self._magicVarForDispatcherOverload=[]
      self.servBackend=None
      self.locked=False
      self._parentModule=None
      self._findParentModule()
      self._reloadBackup={}
      self._gcStats={'lastTime':0, 'processedRequestCount':0, 'processedDispatcherCount':0, 'processing':False}
      self.deepLocked=False
      self.processingRequestCount=0
      self.processingDispatcherCount=0
      self.routes={}
      self.fixJSON=self._fixJSON
      # prepare connPerMinute
      self.connPerMinute={
         'nowMinute':0, 'count':0, 'oldCount':0, 'maxCount':0, 'minCount':0,
         'history':{'minute':deque2([], 9999), 'count':deque2([], 9999)}
      }
      # select JSON-backend
      self.jsonBackend=json
      if isString(jsonBackend):
         try: self.jsonBackend=__import__(jsonBackend)
         except: self._logger(2, 'Cant import JSON-backend "%s", used standart'%(jsonBackend))
      elif jsonBackend: self.jsonBackend=jsonBackend
      self.execBackend={}
      # select Dispatcher-backend
      self.defaultDispatcherBackendId=self._registerExecBackend(dispatcherBackend, notif=False)
      # select Notif-backend
      self.defaultNotifBackendId=self._registerExecBackend(notifBackend, notif=True)
      # enable experimental
      if experimental: experimentalPack.initLocal(locals(), self)
      # call patchServer if existed
      if isFunction(locals().get('_patchServer', None)): locals()['_patchServer'](self)
      # check JSON-backend
      try:
         testVal_o=[{'test1':[1, '2', True, None]}]
         testVal_c=self._parseJSON(self._serializeJSON(testVal_o))
         if testVal_o!=testVal_c:
            self._throw('Checking JSONBackend: values not match (%s, %s)'%(testVal_o, testVal_c))
      except Exception, e:
         self._throw('Unsupported JSONBackend %s: %s'%(jsonBackend, e))
      # enable GC manual control
      if self.settings.controlGC: self._controlGC()

   def _initListenerUDS(self, path, sockClass=None, backlog=None):
      """ Create listeners for UDS socket. """
      sockClass=sockClass or self._socketClass()
      backlog=backlog or self.__settings['backlog']
      if os.path.exists(path):  #remove if exist
         os.remove(path)
      l=sockClass.socket(sockClass.AF_UNIX, sockClass.SOCK_STREAM)
      l.bind(path)
      l.listen(backlog)
      return l

   def _registerExecBackend(self, execBackend, notif):
      """
      This merhod register new execute backend in server, backend will be start when <server>.start() called.

      :param str|obj execBackend: registered backend name or obj.
      :param bool notif: flag indicating is this backend a notification backend.
      :return: unique identification.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # check if execBackend._id passed. If true, not needed to initialize it
      if execBackend in self.execBackend: return execBackend
      # get _id of backend and prepare
      _id=None
      if execBackend!='simple' and isString(execBackend):  #registered exec-backend
         if execBackend not in execBackendCollection.execBackendMap:
            self._throw('Unknown Exec-backend "%s"'%execBackend)
         execBackend=execBackendCollection.execBackendMap[execBackend](notif)
         _id=getattr(execBackend, '_id', None)
      elif execBackend=='simple':  #without exec-backend
         return 'simple'
      elif isDict(execBackend):
         _id=execBackend.get('_id', None)
         execBackend=magicDict(execBackend)
      elif isInstance(execBackend):
         _id=getattr(execBackend, '_id', None)
      else:
         self._throw('Unsupported Exec-backend type "%s"'%type(execBackend))
      # try to add execBackend
      if not _id:
         self._throw('No "_id" in Exec-backend "%s"'%execBackend)
      if not hasattr(execBackend, 'add'):
         self._throw('No "add()" in Exec-backend "%s"'%execBackend)
      if _id not in self.execBackend:  # add execBackend to map if not exist
         self.execBackend[_id]=execBackend
      return _id

   def postprocessAdd(self, type, cb, mode=None, status=None):
      """
      Add new postprocess callback of given <type>.

      :param str type: Type of given <cb>, now supported ('wsgi', 'cb').
      :param func cb:
      :param str mode: Set mode for this <cb>. If None, used default.
      :param int status: Use this <cb> on this http status.
      """
      if self.started:
         self._throw("You can't add new postprocesser while server runned")
      if mode and mode not in postprocess._modeSupported:
         self._throw("Unsupported postprocess-mode, now suppoerted only %s"%list(postprocess._modeSupported))
      if type not in postprocess._typeSupported:
         self._throw("Unsupported postprocess-type, now suppoerted only %s"%list(postprocess._typeSupported))
      if status is not None:
         status=status if isArray(status) else [status]
         for s in status:
            # use by this status
            if not isInt(s):
               raise TypeError('<status> must be number or list of numbers')
            if s not in self.settings.postprocess['byStatus']:
               self.settings.postprocess['byStatus'][s]=[]
            self.settings.postprocess['byStatus'][s].append((type, mode, cb))
      else:
         #! need to test "use always" type
         self._throw("Postprocessers without conditions currently not supported")

   def postprocessAdd_wsgi(self, wsgi, mode=None, status=None):
      """
      Add new postprocess WSGI.

      :param wsgi:
      :param str mode: Set mode for this <wsgi>. If None, used default.
      :param int status: Use this <wsgi> on this http status.
      """
      self.postprocessAdd('wsgi', wsgi, mode, status)

   def postprocessAdd_cb(self, cb, mode=None, status=None):
      """
      Add new postprocess simple callback.

      :param cb:
      :param str mode: Set mode for this <cb>. If None, used default.
      :param int status: Use this <cb> on this http status.
      """
      self.postprocessAdd('cb', cb, mode, status)

   def _tryGevent(self):
      global gevent, geventMonkey, geventSocket, geventFileObjectThread
      if gevent and geventMonkey and geventSocket and geventFileObjectThread: return False
      try:
         import gevent
         from gevent import monkey as geventMonkey
         from gevent import socket as geventSocket
         from gevent.fileobject import FileObjectThread as geventFileObjectThread
         return True
      except ImportError, e:
         self._throw('gevent not found: %s'%e)

   def _import(self, modules, scope=None, forceDelete=True):
      """
      This method replace existed (imported) modules and monke_patch if needed.
      """
      #! Add checking with "monkey.is_module_patched()"
      # delete existed
      for k, v in modules.iteritems():
         if k in globals(): del globals()[k]
         if scope is not None and k in scope: del scope[k]
         if forceDelete and k in sys.modules: del sys.modules[k] # this allow unpatch monkey_patched libs
      # apply patchs
      if self.__settings['gevent']:
         self._tryGevent()
         for k, v in modules.iteritems():
            if not v: continue
            v=v if isArray(v) else [v]
            patchName=v[0]
            if not hasattr(geventMonkey, patchName):
               self._logger(2, 'Warning: unknown patch "%s"'%patchName)
               continue
            patch=getattr(geventMonkey, patchName)
            patchSupported, _, _, _=inspect.getargspec(patch)
            patchArgs_default=v[1] if len(v)>1 else {}
            patchArgs={}
            for k, v in patchArgs_default.iteritems():
               if k in patchSupported: patchArgs[k]=v
            patch(**patchArgs)
      #add to scope
      for k, v in modules.iteritems():
         m=__import__(k)
         globals()[k]=m
         if scope is not None: scope[k]=m
      return scope

   def _importThreading(self, scope=None, forceDelete=True):
      """
      This method import (or patch) module <threading>(and time.sleep) to scope.

      :param dict scope:
      :param bool forceDelete: if True really delete existed modul before importing.
      :return: scope
      """
      modules={
         'threading':None,
         'thread':['patch_thread', {'threading':True, '_threading_local':True, 'Event':False, 'logging':True, 'existing_locks':False}],
         'time':'patch_time'
      }
      return self._import(modules, scope=scope, forceDelete=forceDelete)

   def _importSocket(self, scope=None, forceDelete=True):
      """
      This method import (or patch) module <socket> (and some others) to scope.

      :param dict scope:
      :param bool forceDelete: if True really delete existed modul before importing.
      :return: scope
      """
      modules={
         'httplib':None,
         'urllib2':None,
         'socket':['patch_socket', {'dns':True, 'aggressive':True}],
         'ssl':'patch_ssl',
         'select':['patch_select', {'aggressive':True}]
      }
      return self._import(modules, scope=scope, forceDelete=forceDelete)

   def _importAll(self, scope=None, forceDelete=True):
      """
      This method call _importThreading() and _importSocket().
      """
      self._importThreading(scope=scope, forceDelete=forceDelete)
      self._importSocket(scope=scope, forceDelete=forceDelete)

   def _tweakLimit(self, descriptors=(65536, 65536)):
      """
      This method change file descriptor's limit of current process.

      :param  list(int, int) descriptors: New soft and hard limit.
      """
      try:
         import resource
      except ImportError:
         self._logger(2, 'WARNING: tweaking file descriptors limit not supported on your platform')
         return None
      if descriptors:
         try:  #for Linux
            if resource.getrlimit(resource.RLIMIT_NOFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_NOFILE, descriptors)
         except: pass
         try:  #for BSD
            if resource.getrlimit(resource.RLIMIT_OFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_OFILE, descriptors)
         except: pass

   def _countFileDescriptor(self, pid=None):
      """
      This method return number of used file descriptors by process.

      :param int|str pid: Process ID if None then pid is ID of current proccess.
      :return int:
      """
      mytime=getms()
      pid=os.getpid() if pid is None else pid
      try:
         # c=0
         # for s in os.listdir('/proc/%s/fd'%pid): c+=1
         c=len(os.listdir('/proc/%s/fd'%pid))
         self._speedStatsAdd('countFileDescriptor', getms()-mytime)
         return c
      except Exception, e:
         self._speedStatsAdd('countFileDescriptor', getms()-mytime)
         self._logger(2, "Can't count File Descriptor for PID %s: %s"%(pid, e))
         return None

   def _countMemory(self, pid=None):
      """
      This method return used memory by process in kilobytes.

      :param int pid: Process ID if None then pid is ID of current proccess.
      :return dict: {'peak': 'max used memory', 'now': 'current used memory'}
      """
      mytime=getms()
      pid=os.getpid() if pid is None else pid
      f=None
      res={}
      try:
         f=open('/proc/%s/status'%pid)
         if self.__settings['gevent']:
            self._tryGevent()
            f=geventFileObjectThread(f)
         for s in f:
            parts=s.split()
            key=parts[0][2:-1].lower()
            if key=='peak': res['peak']=int(parts[1])
            elif key=='rss': res['now']=int(parts[1])
      except Exception, e:
         self._logger(2, "Can't count memory for PID %s: %s"%(pid, e))
         res=None
      if f is not None: f.close()
      self._speedStatsAdd('countMemory', getms()-mytime)
      return res

   def _checkFileDescriptor(self, multiply=1.0):
      """
      This method check if used file descriptors near limit.

      :param float multiply: Multiply factor.
      :return bool:
      """
      try:
         import resource
      except ImportError:
         self._logger(1, 'ERROR: checking file descriptors limit not supported on your platform')
         return None
      limit=None
      try:  #for Linux
         limit=resource.getrlimit(resource.RLIMIT_NOFILE)[0]
      except:
         try:  #for BSD
            limit=resource.getrlimit(resource.RLIMIT_OFILE)[0]
         except: pass
      if limit is None:
         self._logger(2, "WARNING: Can't get File Descriptor Limit")
         return None
      c=self._countFileDescriptor()
      if c is None: return None
      res=c*multiply>=limit
      if res:
         self._logger(2, 'WARNING: reached file descriptors limit %s(%s)/%s'%(c, c*multiply, limit))
      return res

   def _inChild(self):
      """
      This methotd  retur True if used in  Child proccess or return False if used in Parent.

      :return bool:
      """
      return self._pid!=os.getpid()

   def _fileGet(self, fName, mode='r'):
      """
      This method open file and read content in mode <mode>, if file is archive then open it and find file with name <mode>.

      :Attention:
      Auto-unpacking of zip-files temporally disabled.

      :param str fName: Path to file.
      :param str mode: Read-mode or file name.
      :return str:
      """
      fName=fName.encode('cp1251')
      if not os.path.isfile(fName): return None
      f=None
      try:
         f=open(fName, mode)
         if self.__settings['gevent']:
            self._tryGevent()
            f=geventFileObjectThread(f)
         s=f.read()
      except Exception, e:
         self._logger(1, 'Error fileGet', fName, ',', mode, e)
         s=None
      if f is not None: f.close()
      return s

   def _fileWrite(self, fName, text, mode='w'):
      """
      This method write content to file with specific mode.
      If mode is 'a' method append data to the end of file.

      :param str text:
      :param str fName: Path to file.
      :param str mode: Write-mode.
      :return str:
      """
      if not isString(text): text=self._serializeJSON(text)
      f=None
      try:
         f=open(fName, mode)
         if self.__settings['gevent']:
            self._tryGevent()
            f=geventFileObjectThread(f)
         f.write(text)
      except Exception, e:
         self._logger(1, 'Error fileWrite', fName, ',', mode, e)
      if f is not None: f.close()

   def _strGet(self, text, pref='', suf='', index=0, default=None):
      """
      This method find prefix, then find suffix and return data between them.
      If prefix is empty, prefix is beginnig of input data.
      If suffix is empty, suffix is ending of input data.

      :param str text: Input data.
      :param str pref: Prefix.
      :param str suf: Suffix.
      :param int index: Position for finding.
      :param any default: Return this if nothing finded.
      :return str:
      """
      if(text==''): return ''
      text1=text.lower()
      pref=pref.lower()
      suf=suf.lower()
      if pref!='': i1=text1.find(pref,index)
      else: i1=index
      if i1==-1: return default
      if suf!='': i2=text1.find(suf,i1+len(pref))
      else: i2=len(text1)
      if i2==-1: return default
      return text[i1+len(pref):i2]

   def _sha1(self, text, onError=None):
      """
      This method generate hash with sha1.
      Length of symbols = 40.

      :param str text:
      :param func|any onError:
      :return str:
      """
      mytime=getms()
      try:
         try: c=hashlib.sha1(text)
         except UnicodeEncodeError: c=hashlib.sha1(text.encode('utf8'))
         s=c.hexdigest()
         self._speedStatsAdd('sha1', getms()-mytime)
         return s
      except Exception, e:
         self._speedStatsAdd('sha1', getms()-mytime)
         self._logger(1, 'ERROR in _sha1():', e)
         if isFunction(onError): return onError(text)
         return onError

   def _sha256(self, text, onError=None):
      """
      This method generate hash with sha1.
      Length of symbols = 64.

      :param str text:
      :param func|any onError:
      :return str:
      """
      mytime=getms()
      try:
         try: c=hashlib.sha256(text)
         except UnicodeEncodeError: c=hashlib.sha256(text.encode('utf8'))
         s=c.hexdigest()
         self._speedStatsAdd('sha256', getms()-mytime)
         return s
      except Exception, e:
         self._speedStatsAdd('sha256', getms()-mytime)
         self._logger(1, 'ERROR in _sha256():', e)
         if isFunction(onError): return onError(text)
         return onError

   def _throw(self, data):
      """
      This method throw exception of class <MainError:data>.

      :param str data: Info about error.
      """
      raise MainError(data)

   def _thread(self, target, args=None, kwargs=None, forceNative=False):
      """
      This method is wrapper above threading.Thread() or gevent.spawn(). Method swithing automatically, if <forceNative> is False. If it's True, always use unpatched threading.Thread(). Spawned threads always will be started like daemons.

      :param func target:
      :param list args:
      :param dict kwargs:
      :param bool forceNative:
      """
      args=args or []
      kwargs=kwargs or {}
      if not self.__settings['gevent']:
         t=threading.Thread(target=target, args=args, kwargs=kwargs)
         t.daemon=True
         t.start()
      else:
         self._tryGevent()
         if forceNative:
            if hasattr(gevent, '_threading'):
               t=gevent._threading.start_new_thread(target, tuple(args), kwargs)
            else:
               try:
                  thr=geventMonkey.get_original('threading', 'Thread')
               except:
                  self._throw('Cant find nativeThread implementation in gevent')
               t=thr(target=target, args=args, kwargs=kwargs)
               t.start()
         else:
            t=gevent.spawn(target, *args, **kwargs)
      return t

   def callAsync(self, target, args=None, kwargs=None, sleepTime=0.3, sleepMethod=None, returnChecker=False, wait=True, forceNative=True, cb=None, cbData=None):
      """
      This method allow to run <target> asynchronously (without blocking server) when used with gevent, or simply in threaded-mode without gevent. It can return result of executed function <target>, or function 'checker', that must be called for getting result (or happened errors). If <wait> and <returnChecker> both passed to False, <target> will be executed in background (without blocking current thread or greenlet) and return nothing.
      You also can pass optional callback, that will be called after <target> completed and before results returned to main thread. So, if you only want to use callback and nothing more, set <wait> to False also.

      :Attention:

      It's not a silver bullet! This method incress perfomance only for limited cases, like executing C-code or perfoming IO-ops, that not frendly for gevent. It really help with <pymysql> on large responses. In all other cases it not incress perfomance, but incress responsiveness of server. This mean, while some function executed in this way, server still availible and can process other requests.

      :Attention:

      This method use hack, that combine greenlets and native threads. It can really burst responsiveness of your server, but strongly recomended to use it only for functions, that don't do any "complicated" things, like working with shared memory, threads or server's instances.

      :param func target:
      :param list args:
      :param dict kwargs:
      :param float sleepTime:
      :param func(<sleepTime>) sleepMethod: This method will be called, while <target> not complete and <wait> is True. If None, default will be used.
      :param bool returnChecker: If True, return function, that must be called for get result.
      :param bool wait: If True, current thread or greenlet will be blocked until results.
      :param bool forceNative: If this False, method will use greenlets instead of native threads (ofcourse if gevent allowed). This cancels all benefits of this method, but can be useful, if you simply want to run code in greenlet and wait for result.
      :param func(result, error, <cbData>) cb: If passed, this function will be called after <target> completed and before results returned to main thread.
      :param any cbData:
      :return any|func: Returns result of executed function or checker.
      """
      sleepMethod=sleepMethod or self._sleep
      args=args or []
      kwargs=kwargs or {}
      mytime=getms()
      save=wait or returnChecker
      # prepare queue
      if not hasattr(self, '_callAsync_queue'): self._callAsync_queue={}
      # generate unique id and workspace
      cId=randomEx(vals=self._callAsync_queue)
      self._callAsync_queue[cId]={'result':None, 'inProgress':True, 'error':None, '_thread':None}
      # init wrapper
      def tFunc_wrapper(self, cId, target, args, kwargs, save, cb, cbData):
         link=self._callAsync_queue[cId]
         try:
            link['result']=target(*args, **kwargs)
         except Exception, e:
            print self._getErrorInfo()
            link['error']=e
         if cb:
            cb(link['result'], link['error'], cbData)
         link['inProgress']=False
         if not save:
            e=link['error']
            del link, self._callAsync_queue[cId]
            if e: raise e
      # call in native thread
      self._callAsync_queue[cId]['_thread']=self._thread(tFunc_wrapper, args=[self, cId, target, args, kwargs, save, cb, cbData], forceNative=forceNative)
      if not save: return
      # return checker or get result
      if returnChecker:
         # init checker
         def tFunc_checker(__cId=cId):
            link=self._callAsync_queue[__cId]
            if link['inProgress']: return False, None, None
            else:
               res=link['result']
               err=link['error']
               del link, self._callAsync_queue[__cId]
               return True, res, err
         return tFunc_checker
      else:
         # wait for completion and get result
         link=self._callAsync_queue[cId]
         while link['inProgress']: sleepMethod(sleepTime)
         res=link['result']
         err=link['error']
         del link, self._callAsync_queue[cId]
         self._speedStatsAdd('callAsync', getms()-mytime)
         # raise error or return result
         if err: raise err
         else: return res

   def _socketClass(self):
      """
      This method returns correct socket class. For gevent return gevent's implementation.
      """
      if not self.__settings['gevent']: return socket
      else:
         self._tryGevent()
         return geventSocket

   def _raw_input(self, msg=None, forceNative=False):
      """
      Non-blocking console input. Without gevent uses native raw_input.

      :param str msg:
      :param bool forceNative:
      """
      if forceNative or not self.__settings['gevent']: return raw_input(msg)
      else:
         if msg: sys.stdout.write(msg)
         self._socketClass().wait_read(sys.stdin.fileno())
         return sys.stdin.readline()

   def _sleep(self, s, forceNative=False):
      """
      This method is wrapper above time.sleep() or gevent.sleep(). Method swithing automatically, if <forceNative> is False. If it's True, always use unpatched time.sleep().

      :param float s: Delay in seconds.
      :param bool forceNative:
      """
      if not self.__settings['gevent']:
         _sleep=time.sleep
      else:
         self._tryGevent()
         if forceNative:
            _sleep=geventMonkey.get_original('time', 'sleep')
         else:
            _sleep=gevent.sleep
      _sleep(s)

   def _findParentModule(self):
      """
      This method find parent module and pass him to attr <_parentModule> of server.
      """
      m=None
      mainPath=getScriptPath(True, False)
      for stk in reversed(inspect.stack()):
         # find frame of parent by module's path
         if mainPath!=stk[1]: continue
         m=inspect.getmodule(stk[0])
         break
      if m is None:
         return self._logger(1, "Cant find parent's module")
      self._parentModule=m

   def _importGlobalsFromParent(self, scope=None, typeOf=None, filterByName=None, filterByNameReversed=False):
      """
      This function import global attributes from parent module (main program) to given scope.
      Imported attributes can be filtered by type, by name or by callback.
      Source based on http://stackoverflow.com/a/9493520/5360266

      :param None|dict scope: Scope for add or change resulting variables. If not passed, new will be created.
      :param None|True|func(name,value)|list typeOf: Filtering by type or callback. If None, filtering disabled. If True, auto filtering by types [Int, Float, Long, Complex, None, Unicode, String, Boolean, Lambda, Dict, List, Tuple, Module, Function].
      :param list filterByName: If passed, only variables with this names will be imported.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if self._parentModule is None:
         self._throw("Parent module not founded")
      if typeOf is True: # check by standart types
         typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType]
      try:
         mytime=getms()
         scope=scope if scope is not None else {}
         if not isFunction(typeOf):
            typeOf=None if typeOf is None else tuple(typeOf)
         if filterByName is None:
            tArr1=dir(self._parentModule)
         elif filterByNameReversed: #exclude specific names
            tArr1=filterByName if isArray(filterByName) else [filterByName]
            tArr1=[k for k in dir(self._parentModule) if k not in tArr1]
         else: #include only specific names
            tArr1=filterByName if isArray(filterByName) else [filterByName]
         for k in tArr1:
            v=getattr(self._parentModule, k)
            # check type if needed or use callback
            if typeOf is None: pass
            elif isFunction(typeOf) and not typeOf(k, v): continue
            elif not isinstance(v, typeOf): continue
            # importing
            scope[k]=v
         self._speedStatsAdd('importGlobalsFromParent', getms()-mytime)
         return scope
      except Exception, e:
         self._throw("Cant import parent's globals: %s"%e)

   def _mergeGlobalsToParent(self, scope, typeOf=None, filterByName=None, filterByNameReversed=False):
      """
      This function merge given scope with global attributes from parent module (main program).
      Merged attributes can be filtered by type, by name or by callback.

      :param dict scope: Scope that will be merged.
      :param None|True|func(name,value)|list typeOf: Filtering by type or callback. If None, filtering disabled. If True, auto filtering by types [Int, Float, Long, Complex, None, Unicode, String, Boolean, Lambda, Dict, List, Tuple, Module, Function].
      :param list filterByName: If passed, only variables with this names will be imported.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if self._parentModule is None:
         self._throw("Parent module not founded")
      if not isDict(scope):
         self._throw("Incorrect scope type: %s"%type(scope))
      if typeOf is True: # check by standart types
         typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, FunctionType]
      try:
         mytime=getms()
         if not isFunction(typeOf):
            typeOf=None if typeOf is None else tuple(typeOf)
         if filterByName is None:
            tArr1=scope.keys()
         elif filterByNameReversed: #exclude specific names
            tArr1=filterByName if isArray(filterByName) else [filterByName]
            tArr1=[k for k in scope.iterkeys() if k not in tArr1]
         else: #include only specific names
            tArr1=filterByName if isArray(filterByName) else [filterByName]
         for k in tArr1:
            v=scope.get(k, None)
            # check type if needed or use callback
            if typeOf is None: pass
            elif isFunction(typeOf) and not typeOf(k, v): continue
            elif not isinstance(v, typeOf): continue
            # merging
            setattr(self._parentModule, k, v)
         self._speedStatsAdd('mergeGlobalsToParent', getms()-mytime)
         return scope
      except Exception, e:
         self._throw("Cant merge parent's globals: %s"%e)

   def _speedStatsAdd(self, name, val):
      """
      This methos write stats about passed <name>. You also can pass multiple names and values like list.

      :param str|list name:
      :param float|list val: time in milliseconds, that will be writed to stats.
      """
      if isArray(name) and isArray(val):
         names, vals=name, val
         if len(names)!=len(vals):
            self._throw('Wrong length')
         for i, name in enumerate(names):
            val=vals[i]
            if name not in self.speedStats:
               self.speedStats[name]=deque2([], 99999)
            self.speedStats[name].append(val)
            if name not in self.speedStatsMax: self.speedStatsMax[name]=val
            elif val>self.speedStatsMax[name]: self.speedStatsMax[name]=val
      else:
         if name not in self.speedStats:
            self.speedStats[name]=deque2([], 99999)
         self.speedStats[name].append(val)
         if name not in self.speedStatsMax: self.speedStatsMax[name]=val
         elif val>self.speedStatsMax[name]: self.speedStatsMax[name]=val

   def registerInstance(self, dispatcher, path='/', fallback=None, dispatcherBackend=None, notifBackend=None, includePrivate=None, filter=None):
      """
      This method Create dispatcher for methods of given class's instance.
      If methods has attribute _alias(List or String), it used as aliases of name.

      :param instance dispatcher: Class's instance.
      :param str path: Optional string that contain path-prefix.
      :param bool|string fallback: Switch JSONP-mode fot this dispatchers.
      :param str|obj dispatcherBackend: Set specific backend for this dispatchers.
      :param str|obj notifBackend: Set specific backend for this dispatchers.
      :param list|None includePrivate: By default this method ignore private and special methods of instance. If you want to include some of them, pass theirs names.
      :param func filter: If this param passed, this function will be called for every method of instance. It must return tuple(<use>, <name>, <link>), and only methods with <use> is True will be registered. This param also disable ignoring private and special methods of instance, so param <includePrivate> also will be disabled.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if not isInstance(dispatcher):
         self._throw('Bad dispatcher type: %s'%type(dispatcher))
      includePrivate=includePrivate or tuple()
      fallback=self.__settings['fallback_JSONP'] if fallback is None else fallback
      path=self._formatPath(path)
      if path not in self.routes: self.routes[path]={}
      # select Dispatcher-backend
      if dispatcherBackend is None: dBckId=self.defaultDispatcherBackendId
      else: dBckId=self._registerExecBackend(dispatcherBackend, notif=False)
      # select Notif-backend
      if notifBackend is None: nBckId=self.defaultNotifBackendId
      else: nBckId=self._registerExecBackend(notifBackend, notif=True)
      # add dispatcher to routes
      for name in dir(dispatcher):
         link=getattr(dispatcher, name)
         if filter:
            s, name, link=filter(dispatcher, name, link)
            if not s: continue
         elif name[0]=='_' and name not in includePrivate: continue  #skip private and special methods
         if isFunction(link):
            # extract arguments
            _args, _, _, _=inspect.getargspec(link)
            _args=tuple([s for i, s in enumerate(_args) if not(i==0 and s=='self')])
            # add dispatcher to routes
            self.routes[path][name]={'allowJSONP':fallback, 'link':link, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId, 'args':_args}
            link.__func__._id={'path':path, 'name':name} #save path for dispatcher in routes
            if hasattr(link, '_alias'):
               tArr1=link._alias if isArray(link._alias) else [link._alias]
               for alias in tArr1:
                  if isString(alias):
                     self.routes[path][alias]={'allowJSONP':fallback, 'link':link, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId, 'args':_args}

   def registerFunction(self, dispatcher, path='/', fallback=None, name=None, dispatcherBackend=None, notifBackend=None):
      """
      This method reate dispatcher for given function.
      If methods has attribute _alias(List or String), it used as aliases of name.

      :param instance dispatcher: Class's instance.
      :param str path: Optional string that contain path-prefix.
      :param bool|string fallback: Switch JSONP-mode fot this dispatcher.
      :param str name: Alternative name for this dispatcher.
      :param str|obj dispatcherBackend: Set specific backend for this dispatcher.
      :param str|obj notifBackend: Set specific backend for this dispatchers.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if not isFunction(dispatcher): self._throw('Bad dispatcher type: %s'%type(dispatcher))
      fallback=self.__settings['fallback_JSONP'] if fallback is None else fallback
      name=name or dispatcher.__name__
      path=self._formatPath(path)
      if path not in self.routes: self.routes[path]={}
      # select Dispatcher-backend
      if dispatcherBackend is None: dBckId=self.defaultDispatcherBackendId
      else: dBckId=self._registerExecBackend(dispatcherBackend, notif=False)
      # select Notif-backend
      if notifBackend is None: nBckId=self.defaultNotifBackendId
      else: nBckId=self._registerExecBackend(notifBackend, notif=True)
      # extract arguments
      _args, _, _, _=inspect.getargspec(dispatcher)
      _args=tuple([s for i, s in enumerate(_args) if not(i==0 and s=='self')])
      # add dispatcher to routes
      self.routes[path][name]={'allowJSONP':fallback, 'link':dispatcher, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId, 'args':_args}
      if hasattr(dispatcher, '__func__'):
         dispatcher.__func__._id={'path':path, 'name':name}  #save path for dispatcher in routes
      else:
         dispatcher._id={'path':path, 'name':name}  #save path for dispatcher in routes
      if hasattr(dispatcher, '_alias'):
         tArr1=dispatcher._alias if isArray(dispatcher._alias) else [dispatcher._alias]
         for alias in tArr1:
            if isString(alias):
               self.routes[path][alias]={'allowJSONP':fallback, 'link':dispatcher, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId}

   def _formatPath(self, path=''):
      """
      This method format path and add trailing slashs.

      :params str path:
      :return str:
      """
      if not path:
         return '/'
      else:
         path=path if path[0]=='/' else '/'+path
         path=path if path[-1]=='/' else path+'/'
         return path

   def _parseJSON(self, data):
      """
      This method parse JSON-data to native object.

      :param str data:
      :return native:
      """
      mytime=getms()
      s=self.jsonBackend.loads(data)
      self._speedStatsAdd('parseJSON', getms()-mytime)
      return s

   def _parseRequest(self, data):
      """
      This method parse reguest's data and validate.

      :param str data:
      :return set(bool, list): First argument is validation status.
      """
      try:
         mytime=getms()
         tArr1=self._parseJSON(data)
         tArr2=[]
         tArr1=tArr1 if isArray(tArr1) else (tArr1, ) #support for batch requests
         for r in tArr1:
            correctId=None
            if 'id' in r:
               # if in request exists key "id" but it's "null", we process him like correct request, not notify-request
               correctId=0 if r['id'] is None else r['id']
            tArr2.append({
               'jsonrpc': r['jsonrpc'] if 'jsonrpc' in r else None,
               'method': r['method'] if 'method' in r else None,
               'params': r['params'] if 'params' in r else None,
               'id':correctId
            })
         self._speedStatsAdd('parseRequest', getms()-mytime)
         return True, tArr2
      except Exception, e:
         self._speedStatsAdd('parseRequest', getms()-mytime)
         self._logger(1, 'Error parseRequest', e)
         return False, e

   def _prepResponse(self, data, isError=False):
      """
      This method prepare data for responce.

      :param dict data:
      :param bool isError: Switch response's format.
      :return dict:
      """
      if 'id' in data:
         _id=data['id']
         del data['id']
      else: _id=None
      if isError:
         s={"jsonrpc": "2.0", "error": data, "id": _id}
      elif id:
         s={"jsonrpc": "2.0", "result": data['data'], "id": _id}
      return s

   def _fixJSON(self, o):
      """
      This method can be called by JSON-backend and process special types.
      """
      if isinstance(o, decimal.Decimal): return str(o)  #fix Decimal conversion
      elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)): return o.isoformat()  #fix DateTime conversion
      # elif isNum(o) and o>=sys.maxint: return str(o) #? fix LONG

   def _serializeJSON(self, data):
      """
      This method convert native python object to JSON.

      :param native data:
      :return str:
      """
      def _fixJSON(o):
         if isFunction(self.fixJSON): return self.fixJSON(o)
      mytime=getms()
      #! без экранирования кавычек такой хак поломает парсер, кроме того он мешает поддерживать не-JSON парсеры
      # if isString(data) and not getattr(self.jsonBackend, '_skipFastStringSerialize', False): data='"'+data+'"'
      data=self.jsonBackend.dumps(data, indent=None, separators=(',',':'), ensure_ascii=True, sort_keys=False, default=_fixJSON)
      self._speedStatsAdd('serializeJSON', getms()-mytime)
      return data

   def _getErrorInfo(self):
      """
      This method return info about last exception.

      :return str:
      """
      tArr=inspect.trace()[-1]
      fileName=tArr[1]
      lineNo=tArr[2]
      exc_obj=sys.exc_info()[1]
      s='%s:%s > %s'%(fileName, lineNo, exc_obj)
      sys.exc_clear()
      return s

   def stats(self, inMS=False, history=10):
      """
      This method return statistics of server.

      :param bool inMS: If True, all speed-stats will be in milliseconds, else in seconds.
      :param bool|int history: Size of sliced connPerSec history.
      :return dict: Collected perfomance stats
      """
      res={'connPerSec_now':round(self.connPerMinute['count']/60.0, 2), 'connPerSec_old':round(self.connPerMinute['oldCount']/60.0, 2), 'connPerSec_max':round(self.connPerMinute['maxCount']/60.0, 2), 'speedStats':{}, 'processingRequestCount':self.processingRequestCount, 'processingDispatcherCount':self.processingDispatcherCount}
      if history and isNum(history):
         l=history*-1
         res['connPerSec_history']={
            'minute':list(self.connPerMinute['history']['minute'])[l:],
            'count':list(self.connPerMinute['history']['count'])[l:]
         }
      elif history:
         res['connPerSec_history']={
            'minute':list(self.connPerMinute['history']['minute']),
            'count':list(self.connPerMinute['history']['count'])
         }
      #calculate speed stats
      for k, v in self.speedStats.iteritems():
         v1=max(v)
         v2=float(sum(v))/len(v)
         v3=self.speedStatsMax[k]
         res['speedStats'][k+'_max']=round(v1/1000.0, 1) if not inMS else round(v1, 1)
         res['speedStats'][k+'_average']=round(v2/1000.0, 1) if not inMS else round(v2, 1)
         res['speedStats'][k+'_max2']=round(v3/1000.0, 1) if not inMS else round(v3, 1)
      #get backend's stats
      for _id, backend in self.execBackend.iteritems():
         if hasattr(backend, 'stats'):
            r=backend.stats(inMS=inMS, history=history)
         elif 'stats' in backend:
            r=backend['stats'](inMS=inMS, history=history)
         else: continue
         res.update(r)
      return res

   def _logger(self, level, *args):
      """
      This method is wrapper for logger. First parametr <level> is optional, if it not setted, message is interpreted as "critical" and will be shown also if logging disabled.

      :param int level: Info-level of message. 0 is critical (and visible always), 1 is error, 2 is warning, 3 is info, 4 is debug. If is not number, it passed as first part of message.
      """
      level, args=prepDataForLogger(level, args)
      if level!=0 and level is not None:  #non-critical or non-fallback msg
         loglevel=self.__settings['log']
         if not loglevel: return
         elif loglevel is True: pass
         elif level>loglevel: return
      levelPrefix=('', 'ERROR:', 'WARNING:', 'INFO:', 'DEBUG:')
      _write=sys.stdout.write
      _repr=self._serializeJSON
      for i, s in enumerate(args):
         # auto-prefix
         if not i and level and level<len(levelPrefix):
            s2=levelPrefix[level]
            if not isString(s) or not s.startswith(s2): _write(s2+' ')
         # try to printing
         try: _write(s)
         except:
            try:
               s=_repr(s)
               try:
                  if s: _write(s)
               except UnicodeEncodeError:
                  _write(s.encode('utf8'))
            except Exception, e:
               _write('<UNPRINTABLE_DATA: %s>'%e)
         if i<len(args)-1: _write(' ')
      _write('\n')
      sys.stdout.flush()

   def lock(self, dispatcher=None):
      """
      This method locking server or specific <dispatcher>.

      :param func dispatcher:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if dispatcher is None: self.locked=True  #global lock
      else:  #local lock
         if isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'):
               setattr(dispatcher.__func__, '__locked', True)
            else:
               setattr(dispatcher, '__locked', True)

   def unlock(self, dispatcher=None, exclusive=False):
      """
      This method unlocking server or specific <dispatcher>.
      If all server locked, you can unlock specific <dispatcher> by pass <exclusive> to True.

      :Attention:

      If you use exclusive unlocking, don't forget to switch locking-status to normal state after all done. For doing this simply call this method for exclusivelly locked dispatcher with <exclusive=False> flag (or without passing <exclusive> flag). This will automatically reset status of exclusive unlocking for given <dispatcher>.

      :param func dispatcher:
      :param bool exclusive:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      #exclusive=True unlock dispatcher also if global lock=True
      if dispatcher is None: self.locked=False  #global lock
      else:  #local lock
         if isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'):
               setattr(dispatcher.__func__, '__locked', False if exclusive else None)
            else:
               setattr(dispatcher, '__locked', False if exclusive else None)

   def wait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      """
      This method wait while server or specific <dispatcher> locked or return locking status.
      If <returnStatus> is True, method only return locking status.
      If <returnStatus> is False, method cyclically call <sleepMethod> until server or <dispatcher> locked. If <sleepMethod> not passed, it will be automatically selected.

      :param func dispatcher:
      :param func sleepMethod:
      :param bool returnStatus:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=getms()
      sleepMethod=sleepMethod or self._sleep
      if dispatcher is None:  #global lock
         while self.locked:
            if returnStatus:
               self._speedStatsAdd('wait', getms()-mytime)
               return True
            sleepMethod(self.__settings['sleepTime_waitLock'])  #global lock
      else:  #local and global lock
         if hasattr(dispatcher, '__func__'): dispatcher=dispatcher.__func__
         while True:
            # local
            locked=getattr(dispatcher, '__locked', None)
            # global
            if locked is False: break  #exclusive unlock
            elif not locked and not self.locked: break
            if returnStatus:
               self._speedStatsAdd('wait', getms()-mytime)
               return True
            sleepMethod(self.__settings['sleepTime_waitLock'])
      self._speedStatsAdd('wait', getms()-mytime)
      if returnStatus: return False

   def _deepLock(self):
      """
      This method locks the server completely.
      While locked, server doesn't process requests, but receives them. All request will wait, until server unlocked.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self.deepLocked=True

   def _deepUnlock(self):
      """
      This method unlocks the server completely.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self.deepLocked=False

   def _deepWait(self):
      """
      This method waits while server be locked.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      while self.deepLocked:
         self._sleep(self.__settings['sleepTime_waitDeepLock'])

   def _reload(self, api, clearOld=False, timeout=60, processingDispatcherCountMax=0, safely=True):
      """
      This method  overload server's source without stopping.

      :param list|dict api:
      :param bool clearOld:
      :param int timeout:
      :param int processingDispatcherCountMax:
      :param bool safely:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self._deepLock()
      mytime=getms()
      self._waitProcessingDispatchers(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop execBackends
      self._stopExecBackends(timeout=timeout-(getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)
      # reloading
      oldRoutes=self.routes
      if clearOld: self.routes={}
      api=api if isArray(api) else [api]
      try:
         for o in api:
            if not isDict(o): continue
            path=o.get('path', '')
            dispatcher=o.get('dispatcher')
            if not dispatcher:
               self._deepUnlock()
               self._throw('Empty dispatcher"')
            if o.get('isInstance', False):
               self.registerInstance(dispatcher, path, fallback=o.get('fallback', None), dispatcherBackend=o.get('dispatcherBackend', None), notifBackend=o.get('notifBackend', None))
            else:
               self.registerFunction(dispatcher, path, name=o.get('name', None), fallback=o.get('fallback', None), dispatcherBackend=o.get('dispatcherBackend', None), notifBackend=o.get('notifBackend', None))
      except Exception, e:
         msg='Cant reload server: %s'%e
         if safely:
            self.routes=oldRoutes
            self._logger(1, msg)
            self._logger(3, 'Server is reloaded in safe-mode, so all dispatchers was restored. But if you overloaded some globals in callback, they can not be restored!')
         else: self._throw(msg)
      # start execBackends
      self._startExecBackends()
      self._deepUnlock()

   def reload(self, api, clearOld=False, timeout=60, processingDispatcherCountMax=0, safely=True):
      """
      This method is wrapper above <server>._reload(). It overload server's source without stopping.

      :Example:

      # example of passed <api>
      api={
         'dispatcher':str() or "function" or "class's instance", # dispatcher's name (replace next param) or link to function (that will be loaded)
         'name':str(), # name of dispatcher that will overloaded
         'dispatcherName':str(), # same as <name>, for backward compatibility
         'scriptPath':str(), # path to source, that must be loaded. If not passed, main program's path will be used
         'scriptName':str(), # don't use it
         'isInstance':bool(), # is passed dispatcher instance of class
         'overload':list(), # overload this attrs in source or call this function
         'path':str() # API path for dispatcher
      }

      :param list(dict)|dict api: see example
      :param bool clearOld:
      :param int timeout:
      :param int processingDispatcherCountMax:
      :param bool safely:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      api2=api if isArray(api) else [api]
      mArr={}
      api=[]
      for o in api2:
         if not isDict(o): continue
         scriptPath=o.get('scriptPath', getScriptPath(True))
         scriptName=o.get('scriptName', '')
         dispatcherName=o.get('dispatcher', '')
         isInstance=o.get('isInstance', False)
         exclusiveModule=o.get('exclusiveModule', False)
         exclusiveDispatcher=o.get('exclusiveDispatcher', False)
         overload=o.get('overload', None)
         path=o.get('path', '')
         name=o.get('name', o.get('dispatcherName', None))
         # start importing new code
         if scriptPath and dispatcherName and isString(dispatcherName):
            # passed path to module and name of dispatcher
            if exclusiveModule:
               module=imp.load_source(scriptName, scriptPath)
            else:
               if '%s_%s'%(scriptName, scriptPath) not in mArr:
                  mArr['%s_%s'%(scriptName, scriptPath)]={'module':imp.load_source(scriptName, scriptPath), 'dArr':{}}
                  if scriptPath==getScriptPath(True) or scriptPath==getScriptPath(True, False):
                     # passed parent module
                     self._parentModule=mArr['%s_%s'%(scriptName, scriptPath)]['module']
               module=mArr['%s_%s'%(scriptName, scriptPath)]['module']
            if exclusiveDispatcher or '%s_%s'%(scriptName, scriptPath) not in mArr:
               # module not imported yet
               dispatcher=getattr(module, dispatcherName)
            else:
               # imported module, use it
               if dispatcherName not in mArr['%s_%s'%(scriptName, scriptPath)]['dArr']:
                  # dispatcher not imported yet
                  mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]=getattr(module, dispatcherName)
                  if isInstance:
                     mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]=mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]()
               dispatcher=mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]
         elif name and isFunction(dispatcherName):
            # passed function as new (or existed) dispatcher
            dispatcher=dispatcherName
            module=dispatcherName
         else:
            self._throw('Incorrect data for "reload()"')
         # overloading with passed objects or via callback
         overload=overload if isArray(overload) else [overload]
         for oo in overload:
            if not oo: continue
            elif isDict(oo):
               for k, v in oo.iteritems(): setattr(module, k, v)
            elif isFunction(oo): oo(self, module, dispatcher)
         # additional settings
         allowJSONP=o.get('fallback', None)
         dispatcherBackend=o.get('dispatcherBackend', None)
         notifBackend=o.get('notifBackend', None)
         # get additional settings from original dispatcher
         if isInstance:
            if (allowJSONP is None) or (dispatcherBackend is None) or (notifBackend is None):
               # dispatcher's settings stored for Class methods, not for Class instance
               # so we need to find at least one Class method, stored previosly
               d=None
               p=self._formatPath(path)
               if p in self.routes:
                  for n in dir(dispatcher):
                     link=getattr(dispatcher, n)
                     if not isFunction(link): continue
                     if n not in self.routes[p]: continue
                     d=self.routes[p][n]
                     break
               if d:
                  if allowJSONP is None: allowJSONP=d['allowJSONP']
                  if dispatcherBackend is None: dispatcherBackend=d['dispatcherBackendId']
                  if notifBackend is None: notifBackend=d['notifBackendId']
         else:
            n=(name or dispatcherName)
            p=self._formatPath(path)
            if p in self.routes and n in self.routes[p]:
               if allowJSONP is None: allowJSONP=self.routes[p][n]['allowJSONP']
               if dispatcherBackend is None: dispatcherBackend=self.routes[p][n]['dispatcherBackendId']
               if notifBackend is None: notifBackend=self.routes[p][n]['notifBackendId']
         # add result
         api.append({'dispatcher':dispatcher, 'path':path, 'isInstance':isInstance, 'name':name, 'fallback':allowJSONP, 'dispatcherBackend':dispatcherBackend, 'notifBackend':notifBackend})
      self._thread(target=self._reload, kwargs={'api':api, 'clearOld':clearOld, 'timeout':timeout, 'processingDispatcherCountMax':processingDispatcherCountMax, 'safely':safely})

   aboutMagicVarForDispatcher="""
      This variable passed to dispatcher, if required. You can set name for this var by passing <magicVarForDispatcher> parametr to server's constructor. By default it named "_connection".

      :param dict headers: Request's headers.
      :param list cookies: Request's cookies.
      :param str ip: Request's IP (ip of client).
      :param dict headersOut: You can set headers, that will be passed to response.
      :param list cookiesOut: You can set cookies, that will be passed to response.
      :param str uniqueId: Unique identificator of request.
      :param bool|str jsonp: If this requests is JSONP fallback, the output format string passed here, otherwise False. You can change this for JSONP fallback requests.
      :param str mimeType: Request's MimeType. You can change this for setting MimeType of Response.
      :param bool allowCompress: Is compressing allowed for this request. You can change it for forcing compression.
      :param instance server: Link to server's instance.
      :param str serverName: Name of server.
      :param set(isRawSocket,(ip|socketPath),(port|socket)) servedBy: Info about server's adress. Usefull if you use multiple adresses for one server.
      :param dict('lock','unlock','wait','sleep','log',..) call: Some useful server's methods, you can call them.
      :param bool nativeThread: Is this request and dispatcher executed in native python thread.
      :param bool notify: Is this request is Notify-request.
      :param func dispatcher: Link to dispatcher.
      :param str path: Server's path, that client used for sending request. Useful if you bind one dispatcher to different paths.
      :param str dispatcherName: Name of dispatcher, that passed with request. Useful if you bind one dispatcher to different names.
      :param str parallelType: Optional parametr. Can be passed by ExecBackend and contain name of it.
      :param int parallelPoolSize: Optional parametr. Can be passed by ExecBackend and contain size of exec's pool.
      :param str parallelId: Optional parametr. Can be passed by ExecBackend and contain identificator of process or thread, that processing this request.
   """

   def _addMagicVarOverloader(self, f):
      if not isFunction(f):
         self._throw('You must pass function, passed %s'%type(f))
      self._magicVarForDispatcherOverload.append(f)

   def _callDispatcher(self, uniqueId, data, request, isJSONP=False, nativeThread=None, overload=None, ignoreLocking=False):
      """
      This method call dispatcher, requested by client.

      :param str uniqueId: Unique ID of current request.
      :param list|dict data: Request's params.
      :param dict request: Reuest's and Enveronment's variables of WSGI or another backend.
      :param bool|str isJSONP:
      :param bool nativeThread:
      :param dict|func overload: Overload magicVarForDispatcher param.
      """
      argsPassed=locals()
      params={}
      try:
         mytime=getms()
         self.processingDispatcherCount+=1
         self._gcStats['processedDispatcherCount']+=1
         if nativeThread:
            def tFunc_sleep(s, forceNative=True):
               self._sleep(s, forceNative=forceNative)
         else:
            tFunc_sleep=self._sleep
         currentDispatcher=self.routes[request['path']][data['method']]
         currentDispatcherLink=currentDispatcher['link']
         _args=self.routes[request['path']][data['method']]['args']
         if isDict(data['params']):
            params=data['params']
         elif isArray(data['params']):  #convert *args to **kwargs
            for i, v in enumerate(data['params']): params[_args[i]]=v
         magicVarForDispatcher=self.__settings['magicVarForDispatcher']
         if magicVarForDispatcher in _args:  #add magicVarForDispatcher if requested
            # link to current execBackend
            if data['id'] is None:
               currentExecBackendId=currentDispatcher['notifBackendId']
            else:
               currentExecBackendId=currentDispatcher['dispatcherBackendId']
            if currentExecBackendId in self.execBackend:
               currentExecBackend=self.execBackend[currentDispatcher['dispatcherBackendId']]
            else:
               currentExecBackend=None
               currentExecBackendId='simple'
            # create magicVarForDispatcher
            params[magicVarForDispatcher]={
               'headers':request['headers'],
               'cookies':request['cookies'],
               'ip':request['ip'],
               'cookiesOut':[],
               'headersOut':{},
               'uniqueId':uniqueId,
               'jsonp':isJSONP,
               'mimeType':self._calcMimeType(request),
               'allowCompress':self.__settings['allowCompress'],
               'server':self,
               'serverName':self.name,
               'servedBy':request['servedBy'],
               'call':magicDict({
                  'lockThis':lambda: self.lock(dispatcher=currentDispatcherLink),
                  'unlockThis':lambda exclusive=False: self.unlock(dispatcher=currentDispatcherLink, exclusive=exclusive),
                  'waitThis':lambda returnStatus=False: self.wait(dispatcher=currentDispatcherLink, sleepMethod=tFunc_sleep, returnStatus=returnStatus),
                  'lock':self.lock,
                  'unlock':self.unlock,
                  'wait':lambda dispatcher=None, returnStatus=False: self.wait(dispatcher=dispatcher, sleepMethod=tFunc_sleep, returnStatus=returnStatus),
                  'sleep':tFunc_sleep,
                  'log':self._logger
               }),
               'nativeThread':nativeThread if nativeThread is not None else not(self.__settings['gevent']),
               'notify':data['id'] is None,
               'request':data,
               'dispatcher':currentDispatcherLink,
               'path':request['path'],
               'dispatcherName':data['method'],
               'execBackend':currentExecBackend,
               'execBackendId':currentExecBackendId
            }
            # overload magicVarForDispatcher (passed)
            if overload and isDict(overload):
               for k, v in overload.iteritems(): params[magicVarForDispatcher][k]=v
            elif overload and isFunction(overload):
               params[magicVarForDispatcher]=overload(params[magicVarForDispatcher])
            # overload magicVarForDispatcher (global)
            if self._magicVarForDispatcherOverload:
               for f in self._magicVarForDispatcherOverload:
                  params[magicVarForDispatcher]=f(params[magicVarForDispatcher], argsPassed, currentExecBackendId, currentExecBackend)
            params[magicVarForDispatcher]=magicDict(params[magicVarForDispatcher])
         self._speedStatsAdd('callDispatcherPrepare', getms()-mytime)
         if not ignoreLocking:  #locking
            self.wait(dispatcher=currentDispatcherLink, sleepMethod=tFunc_sleep)
         # call dispatcher
         mytime=getms()
         result=currentDispatcherLink(**params)
         self._speedStatsAdd('callDispatcher', getms()-mytime)
         self.processingDispatcherCount-=1
         return True, params, result
      except Exception:
         self.processingDispatcherCount-=1
         return False, params, self._getErrorInfo()

   def _controlGC(self, force=False):
      """
      This method collects garbage if one off specific conditions is True or if <force> is True.

      :param bool force:
      """
      if (gc.isenabled() or not self._gcStats['lastTime']) and self.__settings['controlGC']:
         # gc.set_threshold(0)
         gc.disable()
         self._logger(3, 'GC disabled by manual control')
         self._gcStats['lastTime']=getms(False)
         self._gcStats['processedRequestCount']=0
         self._gcStats['processedDispatcherCount']=0
         if not force: return
      # check
      if self._gcStats['processing']: return
      mytime=getms(False)
      # self._logger('controlGC', self._gcStats['lastTime'], mytime-self._gcStats['lastTime'])
      if not force:
         if not self._gcStats['lastTime']: return
         if mytime-self._gcStats['lastTime']<self.__settings['controlGC_everySeconds'] and \
            self._gcStats['processedRequestCount']<self.__settings['controlGC_everyRequestCount'] and \
            self._gcStats['processedDispatcherCount']<self.__settings['controlGC_everyDispatcherCount']: return
      # collect garbage and reset stats
      self._gcStats['processing']=True
      mytime=getms()
      m1=self._countMemory()
      s=gc.collect()
      s+=gc.collect()
      s+=gc.collect()
      s+=gc.collect()
      m2=self._countMemory()
      if s and m1 and m2:
         self._logger(3, 'GC executed manually: collected %s objects, memore freed %smb, used %smb, peak %smb'%(s, round((m1['now']-m2['now'])/1024.0, 1), round(m2['now']/1024.0, 1), round(m2['peak']/1024.0, 1)))
      self._speedStatsAdd('controlGC', getms()-mytime)
      self._gcStats['lastTime']=getms(False)
      self._gcStats['processedRequestCount']=0
      self._gcStats['processedDispatcherCount']=0
      self._gcStats['processing']=False

   def _compressResponse(self, headers, data):
      """
      This method compress responce and add compression-headers.

      :param list headers: List of headers of response, that can be modified.
      :param str data: Response data, that will be compressed.
      :return tuple(headers, data):
      """
      data=self._compressGZIP(data)
      headers.append(('Content-Encoding', 'gzip'))
      headers.append(('Vary', 'Accept-Encoding'))
      # headers.append(('Content-Length', len(data))) # serv-backend set it automatically
      return (data, headers)

   def _compressGZIP(self, data):
      """
      This method compress input data with gzip.

      :param str data:
      :return str:
      """
      mytime=getms()
      gzip_buffer=StringIO()
      l=len(data)
      f=GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=3)
      f.write(data)
      f.close()
      res=gzip_buffer.getvalue()
      self._logger(4, '>> compression %s%%, original size %smb'%(round((1-len(res)/float(l))*100.0, 1), round(l/1024.0/1024.0, 2)))
      self._speedStatsAdd('compressResponse', getms()-mytime)
      return res

   def _uncompressGZIP(self, data):
      """
      This method uncompress input data with gzip.

      :param str data:
      :return str:
      """
      mytime=getms()
      gzip_buffer=StringIO(data)
      f=GzipFile('', 'r', 0, gzip_buffer)
      res=f.read()
      f.close()
      self._speedStatsAdd('uncompressResponse', getms()-mytime)
      return res

   def _loadPostData(self, request):
      """
      Load POST data for given <request>.

      :param dict request:
      :return dict:
      """
      if request['data'] is None:
         size=int(request['environ']['CONTENT_LENGTH']) if 'CONTENT_LENGTH' in request['environ'] else 0
         request['data']=request['environ']['wsgi.input'].read(size) if size else ''
         # decompress if needed
         if 'gzip' in request['headers'].get('Content-Encoding', '').lower():
            self._logger(4, 'COMPRESSED_REQUEST: %skb'%round(sys.getsizeof(request['data'])/1024.0, 2))
            request['data']=self._uncompressGZIP(request['data'])
         # prep for printing
         if len(request['data'])>128:
            request['dataPrint']=request['data'][:50]+' <..> '+request['data'][-50:]
      return request['data']

   def _prepRequestContext(self, env):
      """
      Prepare request's context from given <env>.

      :param dict env:
      :return dict:
      """
      # parsing query string. we need clean dict, so can't use urlparse.parse_qs()
      mytime=getms()
      args={}
      if 'QUERY_STRING' in env and env['QUERY_STRING']:
         for s in env['QUERY_STRING'].split('&'):
            if not s: continue
            if '=' in s:
               i=s.find('=')
               args[s[:i]]=s[i+1:]
            else: args[s]=''
      # prep headers
      headers=dict((k[5:].replace('_', '-').title(), v) for k, v in env.iteritems() if k[:5]=='HTTP_')
      # parsing cookies
      cookies={}
      if 'HTTP_COOKIE' in env and env['HTTP_COOKIE']:
         for s in env['HTTP_COOKIE'].split(';'):
            s=s.strip()
            if not s: continue
            if '=' in s:
               i=s.find('=')
               cookies[s[:i]]=s[i+1:]
            else: cookies[s]=''
      # gen request
      request={
         'path':self._formatPath(env['PATH_INFO'] if 'PATH_INFO' in env else ''),
         'fileName':'', # for JSONP
         'headers':headers,
         'cookies':cookies,
         'environ':env,
         'remote_addr':env['REMOTE_ADDR'] if 'REMOTE_ADDR' in env else '',
         'method':env['REQUEST_METHOD'] if 'REQUEST_METHOD' in env else '',
         'url':wsgiref.util.request_uri(env, include_query=True),
         'data':None,
         'dataPrint':None,
         'args':args,
         'servedBy':env['flaskJSONRPCServer_binded'] if 'flaskJSONRPCServer_binded' in env else (None, None, None)
      }
      # prepare client's ip
      request['ip']=env['HTTP_X_REAL_IP'] if 'HTTP_X_REAL_IP' in env else request['remote_addr']
      self._speedStatsAdd('prepRequestContext', getms()-mytime)
      return request

   def _copyRequestContext(self, request, typeOf=True):
      """
      This method create shallow copy of <request> and skip some not-serializable keys.

      :param dict request:
      :return dict:
      """
      mytime=getms()
      typeOf=(IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, DictType, ListType)
      requestCopy=request.copy()
      requestCopy['environ']=dict((k, v) for k, v in request['environ'].iteritems() if isinstance(v, typeOf))
      self._speedStatsAdd('copyRequestContext', getms()-mytime)
      return requestCopy

   def _calcMimeType(self, request):
      """
      This method generate mime-type of response by given <request>.

      :param dict request:
      :return str:
      """
      return 'text/javascript' if request['method']=='GET' else 'application/json'

   def _toHttpStatus(self, code):
      """
      Complete HTTP status from given <code>.

      :param int code:
      :return str:
      """
      if code in httplib.responses:
         return str(code)+' '+httplib.responses[code]
      else:
         self._throw('Unknow http code: %s'%code)

   def _fromHttpStatus(self, status):
      """
      Convert given HTTP status to code.

      :param str status:
      :return int:
      """
      try:
         return int(status[:3])
      except:
         self._throw('Unknow http status: %s'%status)

   def simulateRequest(self, dispatcherName, args=None, path='/', headers=None, cookies=None, notify=False):
      """
      This method simulate request to server and return result.

      :param str dispatcherName:
      :param list|dict args:
      :param str path: Simulated api path.
      :param dict headers: Simulated headers. Don't pass cookies here, they will not been processed.
      :param dict cookies: Pass cookies here if needed.
      :param bool notify: Is this a notify-request.
      """
      #! симуляция не поддерживает постпроцессеры
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      d={"jsonrpc": "2.0", "method": dispatcherName, "params": args or []}
      if not notify: d['id']=1
      request={
         'path':path,
         'fileName':'',
         'headers':headers or {},
         'cookies':cookies or {},
         'environ':{
            'wsgi.multiprocess': False,
            'CONTENT_TYPE': 'application/json-rpc',
            'wsgi.multithread': True,
            'SERVER_SOFTWARE': 'FAKE_REQUEST',
            'SCRIPT_NAME': '',
            'wsgi.input': True,
            'REQUEST_METHOD': 'POST',
            'HTTP_HOST': 'localhost',
            'PATH_INFO': path,
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'QUERY_STRING': '',
            'CONTENT_LENGTH': '9999',  #! we don't know real length, but it needed for postprocessing
            'wsgi.version': (1, 0),
            'SERVER_NAME': 'FAKE_REQUEST',
            'GATEWAY_INTERFACE': 'CGI/1.1',
            'wsgi.run_once': False,
            'wsgi.errors': None,
            'REMOTE_ADDR': 'localhost',
            'wsgi.url_scheme': 'fake',
            'SERVER_PORT': '',
            'REMOTE_HOST': 'localhost',
            'HTTP_ACCEPT_ENCODING': 'identity'
         },
         'remote_addr':'localhost',
         'method':'POST',
         'url':'localhost'+path,
         'data':None,
         'dataPrint':None,
         'args':{},
         'servedBy':(None, None, None),
         'ip':'localhost',
         'data':[d],
         'dataPrint':'',  #! add correct
         'fake':True
      }
      # add headers to environ
      if headers:
         for k, v in headers.iteritems():
            request['environ']['HTTP_'+k.replace('-', '_').upper()]=v
      # add cookies to environ
      if cookies:
         request['environ']['HTTP_COOKIE']=' '.join('%s=%s;'%(k, v) for k, v in cookies.iteritems())
      # start processing request in thread
      out={'status':None, 'headers':None, 'result':None}
      def tFunc_start_response(status, headers):
         out['status']=status
         out['headers']=headers
      def tFunc_wrapper(*args, **kwargs):
         out['result']=self._requestHandler(*args, **kwargs)[0]
      self._thread(target=tFunc_wrapper, args=(request, tFunc_start_response), kwargs={'prepRequest':False}).join()
      if out['status']=='200 OK' and 'result' in out['result']:
         return out['result']['result'], out['headers']
      elif 'error' in out['result']:
         self._throw(out['result']['error']['message'])
      else:
         self._throw('%s: %s'%(out['status'], out['result']))

   def _requestHandler(self, env, start_response, prepRequest=True):
      """
      This method is callback, that will be called by WSGI or another backend for every request.
      It implement error's handling of <server>._requestProcess() and some additional funtionality.

      :param dict env:
      :param func start_response:
      :param bool prepRequest: If this True, environ will be prepared via <server>._prepRequestContext().
      :return tuple: Response as iterator.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=getms()
      self.processingRequestCount+=1
      self._gcStats['processedRequestCount']+=1
      # calculate connections per second
      nowMinute=int(time.time())/60
      if nowMinute!=self.connPerMinute['nowMinute']:
         # add to history
         self.connPerMinute['history']['minute'].append(self.connPerMinute['nowMinute'])
         self.connPerMinute['history']['count'].append(round(self.connPerMinute['count']/60.0, 2))
         # replace old values
         self.connPerMinute['nowMinute']=nowMinute
         if self.connPerMinute['count']:
            self.connPerMinute['oldCount']=self.connPerMinute['count']
         if self.connPerMinute['count']>self.connPerMinute['maxCount']:
            self.connPerMinute['maxCount']=self.connPerMinute['count']
         if self.connPerMinute['count']<self.connPerMinute['minCount'] or not self.connPerMinute['minCount']:
            self.connPerMinute['minCount']=self.connPerMinute['count']
         self.connPerMinute['count']=0
      self.connPerMinute['count']+=1
      # DeepLocking
      self._deepWait()
      if self.__settings['blocking']: self._deepLock()
      # processing request
      try:
         request=self._prepRequestContext(env) if prepRequest else env
         status, headers, data, dataRaw=self._requestProcess(request)
      except Exception:
         e=self._getErrorInfo()
         self._logger(1, 'ERROR processing request: %s'%e)
         status, headers, data, dataRaw=(500, {}, e, None)
      if self.__settings['postprocess']:
         # call postprocessers
         try:
            pp=postprocess(self, self.__settings['postprocess'])
            status, headers, data=pp(request, status, headers, data, dataRaw)
         except Exception:
            e=self._getErrorInfo()
            self._logger(1, 'ERROR in postprocess: %s'%e)
            status, headers, data=(500, {}, e)
      # convert status to http-status
      if not isString(status): status=self._toHttpStatus(status)
      # convert string-data to iterator
      if isString(data): data=(data,)
      # finalize
      self.processingRequestCount-=1
      self._logger(4, 'GENERATE_TIME:', round(getms()-mytime, 1))
      self._speedStatsAdd('generateResponse', getms()-mytime)
      if self.__settings['blocking']: self._deepUnlock()
      if self.__settings['controlGC']: self._controlGC()  # call GC manually
      start_response(status, headers)
      return data

   def _requestProcess(self, request):
      """
      This method implement all logic of proccessing requests.

      :param dict request:
      :return tuple(int(code), dict(headers), str(data), object(dataRaw)):
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # process only (GET, POST, OPTIONS) requests
      if request['method'] not in ('GET', 'POST', 'OPTIONS'):
         self._logger(3, 'Unsupported method:', request['method'])
         return (405, {}, 'Method Not Allowed', None)
      # to local vars
      isFake='fake' in request and request['fake']
      request_method=request['method']
      request_path=request['path']
      request_fileName=request['fileName']
      request_data=None
      request_dataPrint=None
      request_ip=request['ip']
      request_url=request['url']
      request_args=request['args']
      # extract <method> for JSONP fallback
      if request_method=='GET':
         tArr=request_path[1:-1].split('/')
         if not tArr[-1]:
            self._throw('Incorrect path for GET request: %s'%request_path)
         request_fileName=request['fileName']=tArr[-1]
         request_path=request['path']=self._formatPath('/'.join(tArr[:-1]))
      # don't process request with unknown path
      if request_path not in self.routes:
         self._logger(3, 'Unknown path:', request_path)
         return (404, {}, 'Not Found', None)
      # start processing request
      outHeaders={}
      outCookies=[]
      dataOut=[]
      dataRaw={'rpcError':None, 'result':[]}
      allowCompress=self.__settings['allowCompress']
      mimeType=None
      # get post data
      if request_method=='POST':
         request_data=self._loadPostData(request)
         request_dataPrint=request['dataPrint']
      self._logger(4, 'RAW_REQUEST:', request_url, request_method, request_dataPrint or request_data)
      # AUTH
      if self.__settings['auth'] and isFunction(self.__settings['auth']):
         if self.__settings['auth'](self, request) is not True:
            self._logger(3, 'Access denied:', request_url, request_method, request_dataPrint or request_data)
            return (403, {}, 'Forbidden', None)
      # CORS
      if self.__settings['CORS']:
         outHeaders['Access-Control-Allow-Headers']='Origin, Authorization, X-Requested-With, Content-Type, Accept'
         outHeaders['Access-Control-Max-Age']='0'
         if isDict(self.__settings['CORS']):
            outHeaders['Access-Control-Allow-Origin']=self.__settings['CORS'].get('origin', '*')
            outHeaders['Access-Control-Allow-Methods']=self.__settings['CORS'].get('methods', 'GET, POST, OPTIONS')
         else:
            outHeaders['Access-Control-Allow-Origin']='*'
            outHeaders['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
      # Look at request's type
      if request_method=='OPTIONS':
         self._logger(4, 'REQUEST_TYPE == OPTIONS')
      elif request_method=='POST':  #JSONRPC
         error=[]
         out=[]
         self._logger(4, 'REQUEST:', request_dataPrint or request_data)
         if isFake:
            status, dataInList=(True, request_data)
            request_data='<fakeRequest>'  #for generating uniqueId
         else:
            status, dataInList=self._parseRequest(request_data)
         if not status:  #error of parsing
            error={"code": -32700, "message": "Parse error"}
         else:
            procTime=getms()
            for dataIn in dataInList:
               # protect from freezes at long batch-requests
               if self.__settings['antifreeze_batchMaxTime'] and getms()-procTime>=self.__settings['antifreeze_batchMaxTime']:
                  self._logger(3, 'ANTIFREEZE_PROTECTION', len(dataInList), getms()-procTime)
                  if self.__settings['antifreeze_batchBreak']: break
                  else: self._sleep(self.__settings['antifreeze_batchSleep'])
                  procTime=getms()
               # try to process request
               if not dataIn['jsonrpc'] or not dataIn['method'] or (dataIn['params'] and not(isDict(dataIn['params'])) and not(isArray(dataIn['params']))):  #syntax error in request
                  error.append({"code": -32600, "message": "Invalid Request"})
               elif dataIn['method'] not in self.routes[request_path]:  #call of uncknown method
                  error.append({"code": -32601, "message": "Method not found", "id":dataIn['id']})
               else:  #process correct request
                  # generate unique id
                  uniqueId='%s--%s--%s--%s--%s--%i--%i'%(dataIn['method'], dataIn['id'], request_ip, self._sha1(request_data), getms(), random.random()*sys.maxint, random.random()*sys.maxint)
                  # select dispatcher
                  dispatcher=self.routes[request_path][dataIn['method']]
                  #select backend for executing
                  if dataIn['id'] is None:
                     # notification request
                     execBackend=self.execBackend[dispatcher['notifBackendId']] if dispatcher['notifBackendId'] in self.execBackend else None
                     if execBackend and hasattr(execBackend, 'add'):
                        #! нужно поменять выходной формат для совместимости с light-backend
                        status, m, dataForBackend=execBackend.add(uniqueId, dataIn, request)
                        if not status:
                           self._logger(1, 'Error in notifBackend.add(): %s'%m)
                     else:
                        status, _, _=self._callDispatcher(uniqueId, dataIn, request)
                  else:
                     # simple request
                     execBackend=self.execBackend[dispatcher['dispatcherBackendId']] if dispatcher['dispatcherBackendId'] in self.execBackend else None
                     if execBackend:
                        if hasattr(execBackend, 'check'):
                           # full-backend with 'add' and 'check'
                           status, m, dataForBackend=execBackend.add(uniqueId, dataIn, request)
                           if not status:
                              self._logger(1, 'Error in dispatcherBackend.add(): %s'%m)
                              result='Error in dispatcherBackend.add(): %s'%m
                           else:
                              status, params, result=execBackend.check(uniqueId, dataForBackend)
                        else:
                           # light-backend with 'add' only
                           status, params, result=execBackend.add(uniqueId, dataIn, request)
                           if not status:
                              self._logger(1, 'Error in dispatcherBackend.add(): %s'%result)
                              result='Error in dispatcherBackend.add(): %s'%result
                     else:
                        status, params, result=self._callDispatcher(uniqueId, dataIn, request)
                     if status:
                        if self.__settings['magicVarForDispatcher'] in params:
                           # get additional headers and cookies
                           magicVar=dict(params[self.__settings['magicVarForDispatcher']])
                           if magicVar['headersOut']:
                              outHeaders.update(magicVar['headersOut'])
                           if magicVar['cookiesOut']:
                              outCookies+=magicVar['cookiesOut']
                           if self.__settings['allowCompress'] and magicVar['allowCompress'] is False:
                              allowCompress=False
                           elif self.__settings['allowCompress'] is False and magicVar['allowCompress']: allowCompress=True
                           mimeType=str(magicVar['mimeType'])  #avoid unicode
                        out.append({"id":dataIn['id'], "data":result})
                     else:
                        error.append({"code": -32603, "message": result, "id":dataIn['id']})
         # prepare output for response
         if error: self._logger(4, 'ERRORS:', error)
         self._logger(4, 'OUT:', out)
         if len(error):
            if isDict(error):  #error of parsing
               dataRaw['result'].append(error)
               dataRaw['rpcError']=[error['code']]
               dataOut=self._prepResponse(error, isError=True)
            elif len(dataInList)>1:  #error for batch request
               dataRaw['result']+=error
               dataRaw['rpcError']=[]
               for d in error:
                  dataRaw['result'].append(d)
                  if d['code'] not in dataRaw['rpcError']:
                     dataRaw['rpcError'].append(d['code'])
                  dataOut.append(self._prepResponse(d, isError=True))
            else:  #error for simple request
               dataRaw['result'].append(error[0])
               dataOut=self._prepResponse(error[0], isError=True)
               dataRaw['rpcError']=[error[0]['code']]
         if len(out):
            dataRaw['result']+=out
            if len(dataInList)>1:  #response for batch request
               for d in out:
                  dataOut.append(self._prepResponse(d, isError=False))
            else:  #response for simple request
               dataOut=self._prepResponse(out[0], isError=False)
         if not isFake:
            dataOut=self._serializeJSON(dataOut)
      elif request_method=='GET':  #JSONP fallback
         out=None
         self._logger(4, 'REQUEST:', request_fileName, request_args)
         jsonpCB=request_args.get('jsonp', False)
         jsonpCB='%s(%%s);'%(jsonpCB) if jsonpCB else '%s;'
         if request_fileName not in self.routes[request_path]:  #call of unknown method
            out={"error":{"code": -32601, "message": "Method not found"}}
         elif not self.routes[request_path][request_fileName]['allowJSONP']:  #fallback to JSONP denied
            self._logger(2, 'JSONP_DENIED:', request_path, request_fileName)
            return (403, {}, 'JSONP_DENIED', None)
         else:  #process correct request
            if 'jsonp' in request_args: del request_args['jsonp']
            # generate unique id
            uniqueId='%s--%s--%s--%s--%i--%i'%(request_fileName, request_ip, self._sha1(self._serializeJSON(request_args)), getms(), random.random()*sys.maxint, random.random()*sys.maxint)
            # <id> passed like for normal request
            dataIn={'method':request_fileName, 'params':request_args, 'id':uniqueId}
            # select dispatcher
            dispatcher=self.routes[request_path][dataIn['method']]
            # select backend for executing
            execBackend=self.execBackend[dispatcher['dispatcherBackendId']] if dispatcher['dispatcherBackendId'] in self.execBackend else None
            if execBackend:
               if hasattr(execBackend, 'check'):
                  # full backend with 'add' and 'check'
                  status, m, dataForBackend=execBackend.add(uniqueId, dataIn, request, isJSONP=jsonpCB)
                  if not status:
                     self._logger(1, 'Error in dispatcherBackend.add(): %s'%m)
                     result='Error in dispatcherBackend.add(): %s'%m
                  else:
                     status, params, result=execBackend.check(uniqueId, dataForBackend)
               else:
                  # light backend with 'add' only
                  status, params, result=execBackend.add(uniqueId, dataIn, request, isJSONP=jsonpCB)
                  if not status:
                     self._logger(1, 'Error in dispatcherBackend.add(): %s'%result)
                     result='Error in dispatcherBackend.add(): %s'%result
            else:
               status, params, result=self._callDispatcher(uniqueId, dataIn, request, isJSONP=jsonpCB)
            if status:
               if self.__settings['magicVarForDispatcher'] in params:  #get additional headers and cookies
                  magicVar=dict(params[self.__settings['magicVarForDispatcher']])
                  if magicVar['headersOut']:
                     outHeaders.update(magicVar['headersOut'])
                  if magicVar['cookiesOut']:
                     outCookies+=magicVar['cookiesOut']
                  if self.__settings['allowCompress'] and magicVar['allowCompress'] is False: allowCompress=False
                  elif self.__settings['allowCompress'] is False and magicVar['allowCompress']: allowCompress=True
                  mimeType=str(magicVar['mimeType'])
                  jsonpCB=magicVar['jsonp']
               out=result
            else:
               out={"error":{"code": -32603, "message": result}}
               dataRaw['rpcError']=[-32603]
         dataRaw['result'].append(out)
         # prepare output for response
         self._logger(4, 'OUT:', out)
         out=self._serializeJSON(out)
         dataOut=jsonpCB%(out)
      self._logger(4, 'RESPONSE:', dataOut)
      mimeType=mimeType or self._calcMimeType(request)
      allowCompress=not isFake and allowCompress and len(dataOut)>=self.__settings['compressMinSize'] and 'gzip' in request['headers'].get('Accept-Encoding', '').lower()
      dataRaw['mimeType']=mimeType
      dataRaw['allowCompress']=allowCompress
      dataRaw['isFake']=isFake
      dataRaw['outHeaders']=outHeaders
      dataRaw['outCookies']=outCookies
      if isDict(outHeaders):
         if 'Content-Type' not in outHeaders: outHeaders['Content-Type']=mimeType
         outHeaders=outHeaders.items()
      else:  #for future use, now only dict supported
         outHeaders.append(('Content-Type', mimeType))
      if outCookies:
         # set cookies
         cookies=Cookie.SimpleCookie()
         for c in outCookies:
            if not isDict(c) or 'name' not in c or 'value' not in c: continue
            cookies[c['name']]=c['value']
            cookies[c['name']]['expires']=c.get('expires', 2147483647)
            cookies[c['name']]['path']=c.get('domain', '*')
            outHeaders.append(('Set-Cookie', cookies[c['name']].OutputString()))
      if allowCompress:
         # with compression
         mytime=getms()
         try:
            outHeaders, dataOut=self._compressResponse(outHeaders, dataOut)
         except Exception, e:
            self._logger(1, "Can't compress response:", e)
         self._logger(4, 'COMPRESSION TIME:', round(getms()-mytime, 1))
      return (200, outHeaders, dataOut, dataRaw)

   def serveForever(self, restartOn=False, sleep=10):
      """
      This method is wrapper above <server>.start().
      It implement logic, when this method block executing of source, placed below.

      :Example:

      server=flaskJSONRPCServer(["127.0.0.1", "8080"])
      print "before serveForever"
      server.serveForever()
      print "after serveForever" # you never see this message, while server runned

      :param bool restart:
      :param int sleep:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if not restartOn and not self.__settings['controlGC']: self.start(joinLoop=True)
      else:
         if restartOn:
            restartOn=restartOn if isArray(restartOn) else [restartOn]
         self.start(joinLoop=False)
         try:
            while True:
               self._sleep(sleep)
               if self.__settings['controlGC']: self._controlGC() # call GC manually
               if not restartOn: continue
               for cb in restartOn:
                  if not cb: continue
                  elif isFunction(cb) and cb(self) is not True: continue
                  elif cb=='checkFileDescriptor' and not self._checkFileDescriptor(multiply=1.25): continue
                  self._logger(3, 'Restarting server..')
                  self.restart(joinLoop=False)
                  break
         except KeyboardInterrupt: self.exited=True

   def _startExecBackends(self):
      """
      This merhod run all execute backends of server.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # start execBackends
      for _id, bck in self.execBackend.iteritems():
         if hasattr(bck, 'start'): bck.start(self)

   def getWSGI(self):
      """
      This method return WSGI-app of server.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # return self.flaskApp.wsgi_app
      return self._requestHandler

   def _registerServBackend(self, servBackend):
      """
      This merhod register new serving backend in server, backend will be start when <server>.start() called.

      :param str|obj servBackend: registered backend name or obj.
      :return: unique identification.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # get _id of backend and prepare
      _id=None
      if isString(servBackend): #registered serv-backend
         if servBackend not in servBackendCollection.servBackendMap:
            self._throw('Unknown Serv-backend "%s"'%servBackend)
         servBackend=servBackendCollection.servBackendMap[servBackend]()
         _id=getattr(servBackend, '_id', None)
      elif isDict(servBackend):
         _id=servBackend.get('_id', None)
         servBackend=magicDict(servBackend)
      elif isInstance(servBackend):
         _id=getattr(servBackend, '_id', None)
      else:
         self._throw('Unsupported Serv-backend type "%s"'%type(servBackend))
      # try to use servBackend
      if not _id:
         self._throw('No "_id" in Serv-backend "%s"'%servBackend)
      if not hasattr(servBackend, 'start'):
         self._throw('No "start" method in Serv-backend "%s"'%servBackend)
      self.servBackend=servBackend
      return _id

   def _patchWithGevent(self):
      """
      Patching current process for compatible with gevent.
      """
      try:
         self._tryGevent()
      except Exception:
         self._throw('You switch server to GEVENT mode, but gevent not founded. For switching to DEV mode (without GEVENT) please pass <gevent>=False to constructor')
      # check what patches supports installed gevent version
      monkeyPatchSupported, _, _, _=inspect.getargspec(geventMonkey.patch_all)
      monkeyPatchArgs_default={'socket':False, 'dns':False, 'time':False, 'select':False, 'thread':False, 'os':True, 'ssl':False, 'httplib':False, 'subprocess':True, 'sys':False, 'aggressive':True, 'Event':False, 'builtins':True, 'signal':True}
      monkeyPatchArgs={}
      for k, v in monkeyPatchArgs_default.iteritems():
         if k in monkeyPatchSupported: monkeyPatchArgs[k]=v
      # monkey patching
      geventMonkey.patch_all(**monkeyPatchArgs)
      self._importAll(forceDelete=True, scope=globals())
      self._logger(3, 'Process patched with gevent')

   def start(self, joinLoop=False):
      """
      This method start all execute backends of server, then start serving backend (werkzeug or pywsgi for now).
      If <joinLoop> is True, current thread join serving-thread.

      :param bool joinLoop:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # freeze settings
      self.__settings=dict(self.settings)
      self.settings._magicDictCold__freeze()
      # start execBackends
      self._startExecBackends()
      if self.settings.allowCompress and not(self.settings.experimental and experimentalPack.use_moreAsync and '_compressGZIP' in experimentalPack.moreAsync_methods):
         self._logger(2, 'Included compression is slow')
      if self.settings.blocking:
         self._logger(2, 'Server work in blocking mode')
      if self.settings.gevent:
         self._patchWithGevent()
      # select serving backend
      if not self.servBackend:
         servBackend=self.settings.servBackend
         if servBackend=='auto':
            if self.settings.fakeListener: servBackend='fake'
            elif self.settings.gevent: servBackend='pywsgi'
            else: servBackend='wsgiex'
         _id=self._registerServBackend(servBackend)
      # checking compatibility
      if self.settings.fakeListener and not getattr(self.servBackend, '_supportNoListener', False):
         self._throw('Serving without listeners not supported with selected Serv-backend "%s"'%_id)
      if self.settings.gevent and not getattr(self.servBackend, '_supportGevent', False):
         self._throw('Using Gevent not supported with selected Serv-backend "%s"'%_id)
      if not self.settings.gevent and not getattr(self.servBackend, '_supportNative', False):
         self._throw('Working without Gevent not supported with selected Serv-backend "%s"'%_id)
      if any(self.settings.socketPath) and not getattr(self.servBackend, '_supportRawSocket', False):
         self._throw('Serving on raw-socket not supported with selected Serv-backend "%s"'%_id)
      # run serving backend
      self.started=True
      if not self.settings.postprocess['byStatus']:
         # for fast checking, if no any postprocess WSGI
         self.__settings['postprocess']=None
      self._logger(3, 'Server "%s" running with "%s" serv-backend..'%(self.name, _id))
      self._server=[]
      wsgi=self.getWSGI()
      for i in xrange(len(self.settings.ip)):
         # if passed only UDS path, create listener for it
         if self.settings.socketPath[i] and not self.settings.socket[i]:
            self.settings.socket[i]=self._initListenerUDS(self.settings.socketPath[i])
         # select bindAdress
         bindAdress=self.settings.socket[i] if self.settings.socket[i] else (self.settings.ip[i], self.settings.port[i])
         # wrapping WSGI for detecting adress
         if self.settings.socket[i]:
            s=(True, self.settings.socketPath[i], self.settings.socket[i])
         else:
            s=(False, self.settings.ip[i], self.settings.port[i])
         def wsgiWrapped(environ, start_response, __flaskJSONRPCServer_binded=s, __wsgi=wsgi):
            environ['flaskJSONRPCServer_binded']=__flaskJSONRPCServer_binded
            return __wsgi(environ, start_response)
         # start
         if getattr(self.servBackend, '_supportMultiple', False) and len(self.settings.ip)>1:
            self.servBackend.startMultiple(bindAdress, wsgiWrapped, self, joinLoop=joinLoop, isLast=(i+1==len(self.settings.ip)))
         else:
            self.servBackend.start(bindAdress, wsgiWrapped, self, joinLoop=(joinLoop and i+1==len(self.settings.ip)))

   def _stopExecBackends(self, timeout=20, processingDispatcherCountMax=0):
      """
      This merhod stop all execute backends of server.
      For more info see <server>._waitProcessingDispatchers().

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=getms()
      for _id, bck in self.execBackend.iteritems():
         if hasattr(bck, 'stop'):
            bck.stop(self, timeout=timeout-(getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)

   def _waitProcessingDispatchers(self, timeout=20, processingDispatcherCountMax=0):
      """
      This method try to wait (for <timeout> seconds), while currently runed dispatchers will be done.
      If <processingDispatcherCountMax> is not 0, this check skip this nuber of runned dispatchers.

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=getms()
      if processingDispatcherCountMax is not False:
         while self.processingDispatcherCount>processingDispatcherCountMax:
            if timeout and getms()-mytime>=timeout*1000:
               self._logger(2, 'Warning: So long wait for completing dispatchers(%s)'%(self.processingDispatcherCount))
               break
            self._sleep(self.__settings['sleepTime_checkProcessingCount'])

   def stop(self, timeout=20, processingDispatcherCountMax=0):
      """
      This method stop all execute backends of server, then stop serving backend (werkzeug or gevent.pywsgi for now). For more info see <server>._waitProcessingDispatchers().
      Dont call this method from dispatchers!

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if not hasattr(self.servBackend, 'stop'):
         self._throw('Stopping not provided by Serv-backend "%s"'%self.servBackend)
      self._deepLock()
      mytime=getms()
      self._waitProcessingDispatchers(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop execBackends
      self._stopExecBackends(timeout=timeout-(getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)
      withError=[]
      # stop serving backend
      for i, s in enumerate(self._server):
         try:
            self.servBackend.stop(s, i, self, timeout=timeout-(getms()-mytime)/1000.0)
         except Exception, e: withError.append(e)
      # un-freeze settings
      self.__settings=self.settings
      self.settings._magicDictCold__unfreeze()
      self.started=False
      # process happened errors
      if withError:
         self._deepUnlock()
         self._throw('\n'.join(withError))
      self._logger(3, 'SERVER STOPPED')
      self._logger(0, 'INFO: Ignore all errors about "Unhandled exception in thread..."')
      self.processingRequestCount=0
      self._deepUnlock()

   def restart(self, timeout=20, processingDispatcherCountMax=0, joinLoop=False):
      """
      This method call <server>.stop() and then <server>.start().
      For more info see <server>._waitProcessingDispatchers().

      :param int timeout:
      :param int processingDispatcherCountMax:
      :param bool joinLoop:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self.stop(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      self.start(joinLoop=joinLoop)

   # def createSSLTunnel(self, port_https, port_http, sslCert='', sslKey='', stunnel_configPath='/home/sslCert/', stunnel_exec='stunnel4', stunnel_configSample=None, stunnel_sslAllow='all', stunnel_sslOptions='-NO_SSLv2 -NO_SSLv3', stunnel_logLevel=4, stunnel_logFile='/home/python/logs/stunnel_%s.log'):
   #    import atexit, subprocess
   #    print 'Creating tunnel (localhost:%s --> localhost:%s)..'%(port_https, port_http)
   #    configSample=self._fileGet(stunnel_configSample) if stunnel_configSample else """
   #    debug = %(logLevel)s
   #    output = /dev/null
   #    foreground = yes
   #    socket = l:TCP_NODELAY=1
   #    socket = r:TCP_NODELAY=1

   #    [myservice_%(name)s]
   #    sslVersion = %(sslAllow)s
   #    %(sslOptions)s
   #    cert = %(sslCert)s
   #    key = %(sslKey)s
   #    accept  = %(portHttps)s
   #    connect = %(portHttp)s
   #    TIMEOUTclose = 10
   #    TIMEOUTbusy     = 30
   #    TIMEOUTconnect  = 10
   #    TIMEOUTidle = 10
   #    sessionCacheTimeout = 60
   #    """
   #    name=os.path.splitext(os.path.basename(sys.argv[0]))[0]
   #    stunnel_sslOptions='\n'.join(['options = '+s for s in stunnel_sslOptions.split(' ') if s])
   #    config={'name':name, 'logLevel':stunnel_logLevel, 'sslAllow':stunnel_sslAllow, 'sslOptions':stunnel_sslOptions, 'sslCert':sslCert, 'sslKey':sslKey, 'portHttps':port_https, 'portHttp':port_http}
   #    config=configSample%config
   #    configPath=stunnel_configPath+('stunnel_%s.conf'%name)
   #    logPath=stunnel_logFile%name
   #    self._fileWrite(configPath, config)
   #    stunnel=subprocess.Popen([stunnel_exec, configPath], stderr=open(logPath, "w"))
   #    self._sleep(1)
   #    if stunnel.poll(): #error
   #       s=self._fileGet(logPath)
   #       s='[!] '+self._strGet(s, '[!]', '')
   #       print '!!! ERROR creating tunnel\n', s
   #       return False
   #    def closeSSLTunnel():
   #       try: os.system('pkill -f "%s %s"'%(stunnel_exec, configPath))
   #       except: pass
   #    atexit.register(closeSSLTunnel)
   #    # def checkSSLTunnel():
   #    #    badPatterns=['Connection rejected: too many clients']
   #    #    while True:
   #    #       self._sleep(3)
   #    #       #! Здесь нужно проверять лог на наличие критических ошибок
   #    #       stunnelLog=self._fileGet(logPath)
   #    # thread_checkSSLTunnel=threading.Thread(target=checkSSLTunnel).start()
   #    return stunnel

"""REQUEST-RESPONSE SAMPLES
--> {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}
<-- {"jsonrpc": "2.0", "result": 19, "id": 1}

--> {"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}
<-- {"jsonrpc": "2.0", "result": 19, "id": 3}

--> {"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}
--> {"jsonrpc": "2.0", "method": "foobar"}

--> {"jsonrpc": "2.0", "method": "foobar", "id": "1"}
<-- {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}

--> {"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]
<-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}

--> {"jsonrpc": "2.0", "method": 1, "params": "bar"}
<-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}

--> [1,2,3]
<-- [
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    ]

--> [
      {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
      {"jsonrpc": "2.0", "method"
    ]
<-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}

--> [
      {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
      {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
      {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
      {"foo": "boo"},
      {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
      {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
    ]
<-- [
      {"jsonrpc": "2.0", "result": 7, "id": "1"},
      {"jsonrpc": "2.0", "result": 19, "id": "2"},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "5"},
      {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
    ]
"""
