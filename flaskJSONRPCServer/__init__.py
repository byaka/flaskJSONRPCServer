#!/usr/bin/env python
# -*- coding: utf-8 -*-

__ver_major__ = 0
__ver_minor__ = 9
__ver_patch__ = 2
__ver_sub__ = ""
__version__ = "%d.%d.%d" % (__ver_major__, __ver_minor__, __ver_patch__)
"""
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

import sys, inspect, decimal, random, json, datetime, time, os, zipfile, imp, urllib2, hashlib, threading, gc
from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType
from cStringIO import StringIO
from gzip import GzipFile
Flask=None
request=None
Response=None
gevent=None
geventMonkey=None

from utils import magicDict, virtVar, deque2

import execBackend as execBackendCollection

try:
   import experimental as experimentalPack
   experimentalPack.initGlobal(globals())
except ImportError, e:
   print 'EXPERIMENTAL package not loaded:', e

class flaskJSONRPCServer:
   """
   Main class of server.

   :param list ipAndPort: List or sequence, containing IP and PORT or SOCKET_PATH and SOCKET.
   :param bool multipleAdress: If True, <ipAndPort> must be list, containing different <ipAndPort>. All of them will be binded to this server.
   :param bool blocking: Disable async mode and switch server to blocking mode(also known as one-threaded).
   :param bool|dict cors: Add CORS headers to output (Access-Control-Allow-*). If 'dict', can contain values for <origin> and <method>.
   :param bool gevent: Use Gevent's PyWSGI insted of Flask's Werkzeug.
   :param bool debug: Allow log messages from WSGI-backend.
   :param int|bool log: Set log-level or disable log messages about activity of flaskJSONRPCServer. If it's <int>, set log-level. 1 is error, 2 is warning, 3 is info, 4 is debug.
   :param bool fallback: Automatically accept and process JSONP requests.
   :param bool allowCompress: Allowing compression of output.
   :param list ssl: List or sequence, containing KEY and CERT. If passed, WSGI-backend will be switched to SSL protocol.
   :param list(int,int) tweakDescriptors: List containing new soft and hard limits of file-descriptors for current process.
   :param int compressMinSize: Max length of output in bytes that was not compressed.
   :param str|obj jsonBackend: Select JSON-backend for json.loads() and json.dumps(). If this parameter 'str' type, module with passed name will be imported.  If this parameter 'obj' type, it must contain methods loads() and dumps().
   :param str|dict|func notifBackend: Select default dispatcher-exec-backend for processing notify-requests. Lib include some prepared backends. Variable <execBackendCollection.execBackendMap> contained all of them. If this parameter 'dict' type, it must contain 'add' key as function, that will be called on every notify-request and recive all data about request. Optionally it can contain 'start' and 'stop' keys as functions (it will be called when server starting or stopping) and '_id' key, containing unique identificator. If this parameter 'func' type, it will used like 'add'.
   :param str|dict|func dispatcherBackend: Select default dispatcher-exec-backend for processing regular requests. Lib include some prepared backends. Variable <execBackendCollection.execBackendMap> contained all of them. If this parameter 'dict' type, it must contain 'add' key as function, that will be called on every notify-request and recive all data about request. Also it must contain 'check' function, that will be called for waiting result of processed requests. Optionally it can contain 'start' and 'stop' keys as functions (it will be called when server starting or stopping) and '_id' key, containing unique identificator. If this parameter 'func' type, it will used like 'add'.
   :param func auth: This function will be called on every request to server 9before processing it) and must return status as 'bool' type.
   :param bool experimental: If 'True', server will be patched with 'experimental' package.
   :param bool controlGC: If 'True', server will control GarbageCollector and manually call 'gc.collect()' (by default every 60 minutes or 300k requests or 50k dispatcher's calls).
   :param str magicVarForDispatcher: Name for variable, that can be passed to every dispatcher and will contain many useful data and methods. For more info see <server>.aboutMagicVarForDispatcher.
   :param str name: Optional name of server. Also used as flaskAppName. If not passed, it will be generated automatically.
   """

   def __init__(self, bindAdress, multipleAdress=False, blocking=False, cors=False, gevent=False, debug=False, log=3, fallback=True, allowCompress=False, ssl=False, tweakDescriptors=(65536, 65536), compressMinSize=2*1024*1024, jsonBackend='simplejson', notifBackend='simple', dispatcherBackend='simple', auth=None, experimental=False, controlGC=True, magicVarForDispatcher='_connection', name=None):
      self.consoleColor=magicDict({'header':'\033[95m', 'okblue':'\033[94m', 'okgreen':'\033[92m', 'warning':'\033[93m', 'fail':'\033[91m', 'end':'\033[0m', 'bold':'\033[1m', 'underline':'\033[4m'})
      # Flask imported here for avoiding error in setup.py if Flask not installed yet
      global Flask, request, Response
      from flask import Flask, request, Response
      self._tweakLimit(tweakDescriptors)
      self.name=name or self._randomEx(9999999, pref='flaskJSONRPCServer<', suf='>')
      self.flaskAppName=self.name
      self.version=__version__
      self.settings=magicDict({
         'multipleAdress':multipleAdress,
         'ip':[],
         'port':[],
         'socketPath':[],
         'socket':[],
         'blocking':blocking,
         'fallback_JSONP':fallback,
         'CORS':cors,
         'gevent':gevent,
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
         'controlGC_everySeconds':60*60, #every 60 minutes
         'controlGC_everyRequestCount':300*1000, #every 300k requests
         'controlGC_everyDispatcherCount':50*1000, #every 50k dispatcher's calls
         'magicVarForDispatcher':magicVarForDispatcher
      })
      # set adress
      bindAdress=bindAdress if multipleAdress else [bindAdress]
      for bind in bindAdress:
         if len(bind)!=2: self._throw('Wrong "bindAdress" parametr', bind)
         isSocket=str(type(bind[1])) in ["<class 'socket._socketobject'>", "<class 'gevent.socket.socket'>", "<class 'gevent._socket2.socket'>"]
         tArr={
            'ip':bind[0] if not isSocket else None,
            'port':bind[1] if not isSocket else None,
            'socketPath':bind[0] if isSocket else None,
            'socket':bind[1] if isSocket else None
         }
         for k, v in tArr.items():
            self.settings[k].append(v)
      # other
      self.setts=self.settings # backward compatible
      self.locked=False
      self._pid=os.getpid()
      self._parentModule=None
      self._findParentModule()
      self._werkzeugStopToken=''
      self._reloadBackup={}
      self._gcStats=magicDict({'lastTime':0, 'processedRequestCount':0, 'processedDispatcherCount':0})
      self.deepLocked=False
      self.processingRequestCount=0
      self.processingDispatcherCount=0
      self.flaskApp=Flask(self.flaskAppName)
      self.pathsDef=['/<path>/', '/<path>', '/<path>/<method>/', '/<path>/<method>']
      self.routes={}
      self.fixJSON=self._fixJSON
      # prepare speedStats
      self.speedStats={}
      self.speedStatsMax={}
      self.connPerMinute=magicDict({
         'nowMinute':0, 'count':0, 'oldCount':0, 'maxCount':0, 'minCount':0,
         'history1':deque2([], 9999),
         'history2':{'minute':deque2([], 9999), 'count':deque2([], 9999)}
      })
      # register URLs
      self._registerServerUrl(dict([[s, self._requestHandler] for s in self.pathsDef]))
      # select JSON-backend
      self.jsonBackend=json
      if self._isString(jsonBackend):
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
      if self._isFunction(locals().get('_patchServer', None)): locals()['_patchServer'](self)
      # check JSON-backend
      try:
         testVal_o={'test1':[1]}
         testVal_c=self._parseJSON(self._serializeJSON(testVal_o))
         if testVal_o!=testVal_c:
            self._throw('values not match (%s, %s)'%(testVal_o, testVal_c))
      except Exception, e: self._throw('Unsupported JSONBackend %s: %s'%(jsonBackend, e))
      # enable GC manual control
      if self.settings.controlGC: self._controlGC()

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
      if execBackend in execBackendCollection.execBackendMap: #custom exec-backend
         execBackend=execBackendCollection.execBackendMap[execBackend](notif)
         _id=getattr(execBackend, '_id', None)
      elif execBackend=='simple': #without exec-backend
         _id='simple'
         execBackend=None
      elif self._isDict(execBackend):
         _id=execBackend.get('_id', None)
         execBackend=magicDict(execBackend)
      elif self._isInstance(execBackend):
         _id=getattr(execBackend, '_id', None)
      else: self._throw('Unknow Exec-backend type: %s'%type(execBackend))
      # try to add execBackend
      if not _id: self._throw('No _id in Exec-backend')
      if execBackend and _id not in self.execBackend: # add execBackend to map if not exist
         self.execBackend[_id]=execBackend
      return _id

   def _getServerUrl(self, *args):
      """
      This method return server's urls.

      :return list:  ['/static/<path:filename>', '/<path>/<method>/', '/<path>/<method>', '/<path>/', '/<path>'].
      """
      res=[str(s) for s in self.flaskApp.url_map.iter_rules()]
      return res

   def _registerServerUrl(self, urlMap, methods=None):
      """
      This method register new url on server for specific http-methods.

      :param dict urlMap: Map of urls and functions(handlers).
      :return:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if methods is None: methods=['GET', 'OPTIONS', 'POST']
      urlNow=self._getServerUrl()
      for s, h in urlMap.items():
         if s in urlNow: continue
         self.flaskApp.add_url_rule(rule=s, view_func=h, methods=methods, strict_slashes=False)

   def _tryGevent(self):
      global gevent, geventMonkey
      if gevent and geventMonkey: return False
      try:
         import gevent
         from gevent import monkey as geventMonkey
         return True
      except ImportError: self._throw('gevent not found')

   def _import(self, modules, scope=None, forceDelete=True):
      """
      This methodReplace existed imported module and monke_putch if needed.
      """
      #! Add checking with "monkey.is_module_patched()"
      #delete existed
      for k, v in modules.items():
         if k in globals(): del globals()[k]
         if scope is not None and k in scope: del scope[k]
         if forceDelete and k in sys.modules: del sys.modules[k] # this allow unpatch monkey_patched libs
      # apply patchs
      if self.setts.gevent:
         self._tryGevent()
         for k, v in modules.items():
            if not v: continue
            v=v if self._isArray(v) else [v]
            patchName=v[0]
            if not hasattr(geventMonkey, patchName):
               self._logger(2, 'Warning: unknown patch "%s"'%patchName)
               continue
            patch=getattr(geventMonkey, patchName)
            patchSupported, _, _, _=inspect.getargspec(patch)
            patchArgs_default=v[1] if len(v)>1 else {}
            patchArgs={}
            for k, v in patchArgs_default.items():
               if k in patchSupported: patchArgs[k]=v
            patch(**patchArgs)
      #add to scope
      for k, v in modules.items():
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
      This method import (or patch) module <socket> to scope.

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
         try: #for Linux
            if resource.getrlimit(resource.RLIMIT_NOFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_NOFILE, descriptors)
         except: pass
         try: #for BSD
            if resource.getrlimit(resource.RLIMIT_OFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_OFILE, descriptors)
         except: pass

   def _countFileDescriptor(self, pid=None):
      """
      This method return number of used file descriptors by process.

      :param int|str pid: Process ID if None then pid is ID of current proccess.
      :return int:
      """
      mytime=self._getms()
      pid=os.getpid() if pid is None else pid
      try:
         c=len([s for s in os.listdir('/proc/%s/fd'%pid)])
         self._speedStatsAdd('countFileDescriptor', self._getms()-mytime)
         return c
      except Exception, e:
         self._speedStatsAdd('countFileDescriptor', self._getms()-mytime)
         self._logger(2, "Can't count File Descriptor for PID %s: %s"%(pid, e))
         return None

   def _countMemory(self, pid=None):
      """
      This method return used memory by process in kilobytes.

      :param int pid: Process ID if None then pid is ID of current proccess.
      :return dict:  {'peak': 'max used memory', 'now': 'current used memory'}
      """
      mytime=self._getms()
      pid=os.getpid() if pid is None else pid
      data=None
      res=magicDict({})
      try:
         data=open('/proc/%s/status'%pid)
         for s in data:
            parts=s.split()
            key=parts[0][2:-1].lower()
            if key=='peak': res['peak']=int(parts[1])
            elif key=='rss': res['now']=int(parts[1])
      except Exception, e:
         self._logger(2, "Can't count memory for PID %s: %s"%(pid, e))
         res=None
      finally:
         if data is not None: data.close()
      self._speedStatsAdd('countMemory', self._getms()-mytime)
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
      try:
         limit=resource.getrlimit(resource.RLIMIT_NOFILE)[0] #for Linux
      except: pass
      try:
         limit=resource.getrlimit(resource.RLIMIT_OFILE)[0] #for BSD
      except: pass
      if limit is None:
         self._logger(2, "Can't get File Descriptor Limit")
         return None
      c=self._countFileDescriptor()
      if c is None: return None
      return (c*multiply>=limit)

   def _inChild(self):
      """
      This methotd  retur True if used in  Child proccess or return False if used in Parent.

      :return bool:
      """
      return self._pid!=os.getpid()

   def _getms(self, inMS=True):
      """
      This method return curent(unix timestamp) time in millisecond or second.

      :param bool inMS: If True in millisecond, else in seconds.
      :retrun int:
      """
      if inMS: return time.time()*1000.0
      else: return int(time.time())

   def _isFunction(self, o): return hasattr(o, '__call__')

   def _isInstance(self, o): return isinstance(o, (InstanceType))

   def _isModule(self, o): return isinstance(o, (ModuleType))

   def _isTuple(self, o): return isinstance(o, (tuple))

   def _isArray(self, o): return isinstance(o, (list))

   def _isDict(self, o): return isinstance(o, (dict))

   def _isString(self, o): return isinstance(o, (str, unicode))

   def _isNum(self, var): return isinstance(var, (int, float, long, complex, decimal.Decimal))

   def _fileGet(self, fName, method='r'):
      """
      This method open file and read content in mode <method>, if file is archive then open it and find file with name <method>.

      :param str fName: Path to file.
      :param str method: Read-mode or file name.
      :return str:
      """
      fName=fName.encode('cp1251')
      if not os.path.isfile(fName): return None
      if zipfile.is_zipfile(fName):
         c=zipfile.ZipFile(fName, method)
         try: s=c.read(method)
         except Exception, e:
            self._logger(1, 'Error fileGet', fName, ',', method, e)
            s=None
         try: c.close()
         except: pass
      else:
         try:
            with open(fName, method) as f: s=f.read()
         except Exception, e:
            self._logger(1, 'Error fileGet', fName, ',', method, e)
            s=None
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
      if not self._isString(text): text=repr(text)
      with open(fName, mode) as f: f.write(text)

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

   def _sha1(self, text):
      """
      This method generate hash with sha1.
      Length of symbols = 40.

      :param str text:
      :return str:
      """
      mytime=self._getms()
      try:
         try: c=hashlib.sha1(text)
         except UnicodeEncodeError: c=hashlib.sha1(text.encode('utf8'))
         s=c.hexdigest()
         self._speedStatsAdd('sha1', self._getms()-mytime)
         return s
      except Exception, e:
         self._speedStatsAdd('sha1', self._getms()-mytime)
         self._logger(1, 'ERROR in _sha1():', e)
         return str(random.randint(99999, 9999999))

   def _sha256(self, text):
      """
      This method generate hash with sha1.
      Length of symbols = 64.

      :param str text:
      :return str:
      """
      mytime=self._getms()
      try:
         try: c=hashlib.sha256(text)
         except UnicodeEncodeError: c=hashlib.sha256(text.encode('utf8'))
         s=c.hexdigest()
         self._speedStatsAdd('sha256', self._getms()-mytime)
         return s
      except Exception, e:
         self._speedStatsAdd('sha256', self._getms()-mytime)
         self._logger(1, 'ERROR in _sha256():', e)
         return str(random.randint(99999, 9999999))

   def _randomEx(self, mult=262144, vals=None, pref='', suf='', soLong=3, cbSoLong=lambda s: s*2):
      """
      This method generate random value from 0 to <mult> and add prefix and suffix.
      Also has protection against the repeating values and against recurrence (long generation).

      :param int mult:
      :param list vals: Blacklist of generated data.
      :param str pref: Prefix.
      :param str suf: Suffix.
      :param int soLong: Max time in seconds for generating.
      :param func cbSoLong: This function will called if generating so long. It can return new <mult>. If return None, generating will be aborted.
      :return str: None if some problems or aborted.
      """
      if vals is None: vals=[]
      s=pref+str(int(random.random()*mult))+suf
      mytime=self._getms(False)
      while(s in vals):
         s=pref+str(int(random.random()*mult))+suf
         if self._getms(False)-mytime>soLong: #защита от бесконечного цикла
            mytime=self._getms(False)
            self._logger(2, 'randomEx: generating value so long!')
            if self._isFunction(cbSoLong):
               mult=cbSoLong(mult, vals, pref, suf)
               if mult is None: return None
            else: return None
      return s

   def _throw(self, data):
      """
      This method throw exception of class <ValueError:data>.

      :param str data: Info about error.
      """
      raise ValueError(data)

   def _thread(self, target, args=None, kwargs=None, forceNative=False):
      """
      This method is wrapper above threading.Thread() or gevent.spawn(). Method swithing automatically, if <forceNative> is False. If it's True, always use unpatched threading.Thread().

      :param func target:
      :param bool forceNative:
      """
      args=args or []
      kwargs=kwargs or {}
      if not self.settings.gevent:
         t=threading.Thread(target=target, args=args, kwargs=kwargs)
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

   def _sleep(self, s, forceNative=False):
      """
      This method is wrapper above time.sleep() or gevent.sleep(). Method swithing automatically, if <forceNative> is False. If it's True, always use unpatched time.sleep().

      :param int s: Delay in milliseconds.
      :param bool forceNative:
      """
      if not self.settings.gevent:
         _sleep=time.sleep
      else:
         self._tryGevent()
         if forceNative:
            _sleep=geventMonkey.get_original('time', 'sleep')
         else:
            _sleep=gevent.sleep
      _sleep(s)

   def _getScriptPath(self, full=False, real=True):
      """
      This method receives a way to a script. If <full> is False return only path, else return path and file name.

      :param bool full:
      :retunr str:
      """
      if full:
         return os.path.realpath(sys.argv[0]) if real else sys.argv[0]
      else:
         return os.path.dirname(os.path.realpath(sys.argv[0]) if real else sys.argv[0])

   def _getScriptName(self, withExt=False):
      """
      This method return name of current script. If <withExt> is True return name with extention.

      :param bool withExt:
      :return str:
      """
      if withExt: return os.path.basename(sys.argv[0])
      else: return os.path.splitext(os.path.basename(sys.argv[0]))[0]

   def _findParentModule(self):
      """
      This method find parent module and pass him to attr <_parentModule> of server.
      """
      m=None
      mainPath=self._getScriptPath(True, False)
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
         mytime=self._getms()
         scope=scope if scope is not None else {}
         if not self._isFunction(typeOf):
            typeOf=None if typeOf is None else tuple(typeOf)
         if filterByName is None:
            tArr1=dir(self._parentModule)
         elif filterByNameReversed: #exclude specific names
            tArr1=filterByName if self._isArray(filterByName) else [filterByName]
            tArr1=[k for k in dir(self._parentModule) if k not in tArr1]
         else: #include only specific names
            tArr1=filterByName if self._isArray(filterByName) else [filterByName]
         for k in tArr1:
            v=getattr(self._parentModule, k)
            # check type if needed or use callback
            if typeOf is None: pass
            elif self._isFunction(typeOf) and not typeOf(k, v): continue
            elif not isinstance(v, typeOf): continue
            # importing
            scope[k]=v
         self._speedStatsAdd('importGlobalsFromParent', self._getms()-mytime)
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
      if not self._isDict(scope):
         self._throw("Incorrect scope type: %s"%type(scope))
      if typeOf is True: # check by standart types
         typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, FunctionType]
      try:
         mytime=self._getms()
         if not self._isFunction(typeOf):
            typeOf=None if typeOf is None else tuple(typeOf)
         if filterByName is None:
            tArr1=scope.keys()
         elif filterByNameReversed: #exclude specific names
            tArr1=filterByName if self._isArray(filterByName) else [filterByName]
            tArr1=[k for k in scope.keys() if k not in tArr1]
         else: #include only specific names
            tArr1=filterByName if self._isArray(filterByName) else [filterByName]
         for k in tArr1:
            v=scope.get(k, None)
            # check type if needed or use callback
            if typeOf is None: pass
            elif self._isFunction(typeOf) and not typeOf(k, v): continue
            elif not isinstance(v, typeOf): continue
            # merging
            setattr(self._parentModule, k, v)
         self._speedStatsAdd('mergeGlobalsToParent', self._getms()-mytime)
         return scope
      except Exception, e:
         self._throw("Cant merge parent's globals: %s"%e)

   def _speedStatsAdd(self, name, val):
      """
      This methos write stats about passed <name>.

      :param str name:
      :param float val: time in milliseconds, that will be writed to stats.
      """
      names=name if self._isArray(name) else [name]
      vals=val if self._isArray(val) else [val]
      if len(names)!=len(vals):
         self._throw('Wrong length')
      for i, name in enumerate(names):
         val=vals[i]
         if name not in self.speedStats: self.speedStats[name]=[]
         if name not in self.speedStatsMax: self.speedStatsMax[name]=0
         self.speedStats[name].append(val)
         if val>self.speedStatsMax[name]: self.speedStatsMax[name]=val
         if len(self.speedStats[name])>99999:
            self.speedStats[name]=[self.speedStatsMax[name]]

   def registerInstance(self, dispatcher, path='', fallback=None, dispatcherBackend=None, notifBackend=None):
      """
      This method Create dispatcher for methods of given class's instance.
      If methods has attribute _alias(List or String), it used as aliases of name.

      :param instance dispatcher: Class's instance.
      :param str path: Optional string that contain path-prefix.
      :param bool|string fallback: Switch JSONP-mode fot this dispatchers.
      :param str|obj dispatcherBackend: Set specific backend for this dispatchers.
      :param str|obj notifBackend: Set specific backend for this dispatchers.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if not self._isInstance(dispatcher): self._throw('Bad dispatcher type: %s'%type(dispatcher))
      fallback=self.setts.fallback_JSONP if fallback is None else fallback
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
         if self._isFunction(link):
            self.routes[path][name]=magicDict({'allowJSONP':fallback, 'link':link, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId})
            link.__func__._id={'path':path, 'name':name} #save path for dispatcher in routes
            if hasattr(link, '_alias'):
               tArr1=link._alias if self._isArray(link._alias) else [link._alias]
               for alias in tArr1:
                  if self._isString(alias):
                     self.routes[path][alias]=magicDict({'allowJSONP':fallback, 'link':link, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId})

   def registerFunction(self, dispatcher, path='', fallback=None, name=None, dispatcherBackend=None, notifBackend=None):
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
      if not self._isFunction(dispatcher): self._throw('Bad dispatcher type: %s'%type(dispatcher))
      fallback=self.setts.fallback_JSONP if fallback is None else fallback
      name=name or dispatcher.__name__
      path=self._formatPath(path)
      if path not in self.routes: self.routes[path]={}
      # select Dispatcher-backend
      if dispatcherBackend is None: dBckId=self.defaultDispatcherBackendId
      else: dBckId=self._registerExecBackend(dispatcherBackend, notif=False)
      # select Notif-backend
      if notifBackend is None: nBckId=self.defaultNotifBackendId
      else: nBckId=self._registerExecBackend(notifBackend, notif=True)
      # add dispatcher to routes
      self.routes[path][name]=magicDict({'allowJSONP':fallback, 'link':dispatcher, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId})
      if hasattr(dispatcher, '__func__'):
         dispatcher.__func__._id={'path':path, 'name':name} #save path for dispatcher in routes
      else:
         dispatcher._id={'path':path, 'name':name} #save path for dispatcher in routes
      if hasattr(dispatcher, '_alias'):
         tArr1=dispatcher._alias if self._isArray(dispatcher._alias) else [dispatcher._alias]
         for alias in tArr1:
            if self._isString(alias):
               self.routes[path][alias]=magicDict({'allowJSONP':fallback, 'link':dispatcher, 'dispatcherBackendId':dBckId, 'notifBackendId':nBckId})

   def _formatPath(self, path=''):
      """
      This method format path and add trailing slash.

      :params str path:
      :return str:
      """
      path=path or '/'
      path=path if path.startswith('/') else '/'+path
      path=path if path.endswith('/') else path+'/'
      return path

   def _parseJSON(self, data):
      """
      This method parse JSON-data to native object.

      :param str data:
      :return native:
      """
      mytime=self._getms()
      s=self.jsonBackend.loads(data)
      self._speedStatsAdd('parseJSON', self._getms()-mytime)
      return s

   def _parseRequest(self, data):
      """
      This method parse reguest's data and validate.

      :param str data:
      :return set(bool, list): First argument is validation status.
      """
      try:
         mytime=self._getms()
         tArr1=self._parseJSON(data)
         tArr2=[]
         tArr1=tArr1 if self._isArray(tArr1) else [tArr1] #support for batch requests
         for r in tArr1:
            correctId=None
            if 'id' in r:
               # if in request exists key "id" but it's "null", we process him like correct request, not notify-request
               correctId=0 if r['id'] is None else r['id']
            tArr2.append({'jsonrpc':r.get('jsonrpc', None), 'method':r.get('method', None), 'params':r.get('params', None), 'id':correctId})
         self._speedStatsAdd('parseRequest', self._getms()-mytime)
         return True, tArr2
      except Exception, e:
         self._speedStatsAdd('parseRequest', self._getms()-mytime)
         self._logger(1, 'Error parseRequest', e)
         return False, e

   def _prepResponse(self, data, isError=False):
      """
      This method prepare data for responce.

      :param dict data:
      :param bool isError: Switch response's format.
      :return dict:
      """
      id=data.get('id', None)
      if 'id' in data: del data['id']
      if isError:
         s={"jsonrpc": "2.0", "error": data, "id": id}
      elif id:
         s={"jsonrpc": "2.0", "result": data['data'], "id": id}
      return s

   def _fixJSON(self, o):
      """
      This method can be called by JSON-backend and process special types.
      """
      if isinstance(o, decimal.Decimal): return str(o) #fix Decimal conversion
      elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)): return o.isoformat() #fix DateTime conversion
      # elif self._isNum(o) and o>2**31: return str(o) #? fix LONG

   def _serializeJSON(self, data):
      """
      This method convert native python object to JSON.

      :param native data:
      :return str:
      """
      def _fixJSON(o):
         if self._isFunction(self.fixJSON): return self.fixJSON(o)
      mytime=self._getms()
      s=self.jsonBackend.dumps(data, indent=None, separators=(',',':'), ensure_ascii=True, sort_keys=False, default=_fixJSON)
      self._speedStatsAdd('serializeJSON', self._getms()-mytime)
      return s

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

   def stats(self, inMS=False):
      """
      This method return statistics of server.

      :param bool inMS: If True, all speed-stats will be in milliseconds, else in seconds.
      :return dict: Collected perfomance stats
      """
      res={'connPerSec_now':round(self.connPerMinute.count/60.0, 2), 'connPerSec_old':round(self.connPerMinute.oldCount/60.0, 2), 'connPerSec_max':round(self.connPerMinute.maxCount/60.0, 2), 'speedStats':{}, 'processingRequestCount':self.processingRequestCount, 'processingDispatcherCount':self.processingDispatcherCount}
      #calculate speed stats
      for k, v in self.speedStats.items():
         v1=max(v)
         v2=sum(v)/float(len(v))
         res['speedStats'][k+'_max']=round(v1/1000.0, 1) if not inMS else round(v1, 1)
         res['speedStats'][k+'_average']=round(v2/1000.0, 1) if not inMS else round(v2, 1)
      #get backend's stats
      for _id, backend in self.execBackend.items():
         if hasattr(backend, 'stats'): r=backend.stats(inMS=inMS)
         elif 'stats' in backend: r=backend['stats'](inMS=inMS)
         else: continue
         res.update(r)
      return res

   def _loggerPrep(self, level, args):
      """
      This method convert <args> to list and also implements fallback for messages without <level>.
      """
      if not self._isNum(level): # fallback
         if args:
            args=list(args)
            if level is not None: args.insert(0, level)
         else: args=[level] if level is not None else []
         level=None
      if not args: args=[]
      elif not self._isArray(args): args=list(args)
      return level, args

   def _logger(self, level, *args):
      """
      This method is wrapper for logger. First parametr <level> is optional, if it not setted, message is interpreted as "critical" and will be shown also if logging disabled.

      :param int level: Info-level of message. 0 is critical (and visible always), 1 is error, 2 is warning, 3 is info, 4 is debug. If is not number, it passed as first part of message.
      """
      level, args=self._loggerPrep(level, args)
      if level!=0 and level is not None: # critical or fallback msg
         if not self.setts.log: return
         elif self.setts.log is True: pass
         elif level>self.setts.log: return
      levelPrefix=['', 'ERROR:', 'WARNING:', 'INFO:', 'DEBUG:']
      for i in xrange(len(args)):
         s=args[i]
         # auto-prefix
         if not i and level and level<5:
            s2=levelPrefix[level]
            if not self._isString(s) or not s.startswith(s2): sys.stdout.write(s2+' ')
         # try to printing
         try: sys.stdout.write(s)
         except:
            try:
               s=self._serializeJSON(s)
               try:
                  sys.stdout.write(s if s else '')
               except UnicodeEncodeError:
                  sys.stdout.write(s.encode('utf8') if s else '')
            except Exception, e: sys.stdout.write('<UNPRINTABLE DATA> %s'%e)
         if i<len(args)-1: sys.stdout.write(' ')
      try: sys.stdout.write('\n')
      except Exception, e: sys.stdout.write('<UNPRINTABLE DATA> %s'%e)

   def lock(self, dispatcher=None):
      """
      This method locking server or specific dispatcher.

      :param func dispatcher:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      if dispatcher is None: self.locked=True #global lock
      else: #local lock
         if self._isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'):
               setattr(dispatcher.__func__, '__locked', True)
            else:
               setattr(dispatcher, '__locked', True)

   def unlock(self, dispatcher=None, exclusive=False):
      """
      This method unlocking server or specific dispatcher.
      If all server locked, you can unlock specific dispatcher by pass <exclusive> to True.

      :param func dispatcher:
      :param bool exclusive:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      #exclusive=True unlock dispatcher also if global lock=True
      if dispatcher is None: self.locked=False #global lock
      else: #local lock
         if self._isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'):
               setattr(dispatcher.__func__, '__locked', False if exclusive else None)
            else:
               setattr(dispatcher, '__locked', False if exclusive else None)

   def wait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      """
      This method wait while server (or specific <dispatcher>) locked or return locking status.
      If <returnStatus> is True, method only return locking status.
      If <returnStatus> is False, method cyclically call <sleepMethod> until server or <dispatcher> locked. If <sleepMethod> not passed, it will be automatically selected.

      :param func dispatcher:
      :param func sleepMethod:
      :param bool returnStatus:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=self._getms()
      sleepMethod=sleepMethod or self._sleep
      if dispatcher is None: #global lock
         while self.locked:
            if returnStatus:
               self._speedStatsAdd('wait', self._getms()-mytime)
               return True
            sleepMethod(self.setts.sleepTime_waitLock) #global lock
      else: #local and global lock
         if self._isFunction(dispatcher):
            while True:
               if hasattr(dispatcher, '__func__'):
                  locked=getattr(dispatcher.__func__, '__locked', None)
               else:
                  locked=getattr(dispatcher, '__locked', None)
               if locked is False: break #exclusive unlock
               elif not locked and not self.locked: break
               if returnStatus:
                  self._speedStatsAdd('wait', self._getms()-mytime)
                  return True
               sleepMethod(self.setts.sleepTime_waitLock)
      self._speedStatsAdd('wait', self._getms()-mytime)
      if returnStatus: return False

   def _deepLock(self):
      """
      This method locks the server completely, the server doesn't process requests.
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
         self._sleep(self.setts.sleepTime_waitDeepLock)

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
      mytime=self._getms()
      self._waitProcessingDispatchers(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop execBackends
      self._stopExecBackends(timeout=timeout-(self._getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)
      # reloading
      oldRoutes=self.routes
      if clearOld: self.routes={}
      api=api if self._isArray(api) else [api]
      try:
         for o in api:
            if not self._isDict(o): continue
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
         msg='ERROR on <server>._reload(): %s'%e
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
      api2=api if self._isArray(api) else [api]
      mArr={}
      api=[]
      for o in api2:
         if not self._isDict(o): continue
         scriptPath=o.get('scriptPath', self._getScriptPath(True))
         scriptName=o.get('scriptName', '')
         dispatcherName=o.get('dispatcher', '')
         isInstance=o.get('isInstance', False)
         exclusiveModule=o.get('exclusiveModule', False)
         exclusiveDispatcher=o.get('exclusiveDispatcher', False)
         overload=o.get('overload', None)
         path=o.get('path', '')
         name=o.get('name', o.get('dispatcherName', None))
         # start importing new code
         if scriptPath and dispatcherName and self._isString(dispatcherName):
            # passed path to module and name of dispatcher
            if exclusiveModule:
               module=imp.load_source(scriptName, scriptPath)
            else:
               if '%s_%s'%(scriptName, scriptPath) not in mArr:
                  mArr['%s_%s'%(scriptName, scriptPath)]={'module':imp.load_source(scriptName, scriptPath), 'dArr':{}}
                  if scriptPath==self._getScriptPath(True) or scriptPath==self._getScriptPath(True, False):
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
         elif name and self._isFunction(dispatcherName):
            # passed function as new (or existed) dispatcher
            dispatcher=dispatcherName
            module=dispatcherName
         else:
            self._throw('Incorrect data for "reload()"')
         # overloading with passed objects or via callback
         overload=overload if self._isArray(overload) else [overload]
         for oo in overload:
            if not oo: continue
            elif self._isDict(oo):
               for k, v in oo.items(): setattr(module, k, v)
            elif self._isFunction(oo): oo(self, module, dispatcher)
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
                     if not self._isFunction(link): continue
                     if n not in self.routes[p]: continue
                     d=self.routes[p][n]
                     break
               if d:
                  if allowJSONP is None: allowJSONP=d.allowJSONP
                  if dispatcherBackend is None: dispatcherBackend=d.dispatcherBackendId
                  if notifBackend is None: notifBackend=d.notifBackendId
         else:
            n=(name or dispatcherName)
            p=self._formatPath(path)
            if p in self.routes and n in self.routes[p]:
               if allowJSONP is None: allowJSONP=self.routes[p][n].allowJSONP
               if dispatcherBackend is None: dispatcherBackend=self.routes[p][n].dispatcherBackendId
               if notifBackend is None: notifBackend=self.routes[p][n].notifBackendId
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

   def _callDispatcher(self, uniqueId, path, data, request, isJSONP=False, nativeThread=None, overload=None):
      """
      This method call dispatcher, requested by client.

      :param str uniqueId: Unique ID of current request.
      :param str path: Server's path, that client used for sending request.
      :param list|dict data: Request's params.
      :param dict request: Reuest's and Enveronment's variables of WSGI or another backend.
      :param bool|str isJSONP:
      :param bool nativeThread:
      :param dict|func overload: Overload <_connection> param.
      """
      try:
         self.processingDispatcherCount+=1
         self._gcStats.processedDispatcherCount+=1
         _sleep=lambda s, forceNative=nativeThread: self._sleep(s, forceNative=forceNative)
         params={}
         dispatcher=self.routes[path][data['method']].link
         _args, _, _, _=inspect.getargspec(dispatcher)
         _args=[s for i, s in enumerate(_args) if not(i==0 and s=='self')]
         if self._isDict(data['params']): params=data['params']
         elif self._isArray(data['params']): #convert *args to **kwargs
            for i, v in enumerate(data['params']): params[_args[i]]=v
         magicVarForDispatcher=self.settings.magicVarForDispatcher
         if magicVarForDispatcher in _args: #add connection info if needed
            params[magicVarForDispatcher]={
               'headers':dict([h for h in request.headers]) if not self._isDict(request.headers) else request.headers,
               'cookies':request.cookies,
               'ip':request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
               'cookiesOut':[],
               'headersOut':{},
               'uniqueId':uniqueId,
               'jsonp':isJSONP,
               'mimeType':self._calcMimeType(request),
               'allowCompress':self.setts.allowCompress,
               'server':self,
               'servedBy':request.servedBy,
               'call':magicDict({
                  'lock':lambda: self.lock(dispatcher=dispatcher),
                  'unlock':lambda exclusive=False: self.unlock(dispatcher=dispatcher, exclusive=exclusive),
                  'wait':lambda returnStatus=False: self.wait(dispatcher=dispatcher, sleepMethod=_sleep, returnStatus=returnStatus),
                  'sleep':_sleep,
                  'log':self._logger
               }),
               'nativeThread':nativeThread if nativeThread is not None else not(self.setts.gevent),
               'notify':data['id'] is None,
               'dispatcher':dispatcher,
               'path':path,
               'dispatcherName':data['method']
            }
            # overload _connection
            if self._isDict(overload):
               for k, v in overload.items(): params[magicVarForDispatcher][k]=v
            elif self._isFunction(overload):
               params[magicVarForDispatcher]=overload(params[magicVarForDispatcher])
            params[magicVarForDispatcher]=magicDict(params[magicVarForDispatcher])
         #locking
         self.wait(dispatcher=dispatcher, sleepMethod=_sleep)
         #call dispatcher
         mytime=self._getms()
         result=dispatcher(**params)
         self._speedStatsAdd('callDispatcher', self._getms()-mytime)
         self.processingDispatcherCount-=1
         if self.settings.controlGC: self._controlGC() # call GC manually
         return True, params, result
      except Exception:
         self.processingDispatcherCount-=1
         if self.settings.controlGC: self._controlGC() # call GC manually
         return False, params, self._getErrorInfo()

   def _controlGC(self, force=False):
      """
      This method collects garbage if one off specific conditions is True or if <force> is True.

      :param bool force:
      """
      if gc.isenabled() and self.settings.controlGC:
         gc.disable()
         self._logger(3, 'GC disabled by manual control')
         self._gcStats.lastTime=self._getms(False)
         self._gcStats.processedRequestCount=0
         self._gcStats.processedDispatcherCount=0
         if not force: return
      # check
      m1=self._countMemory()
      mytime=self._getms(False)
      if not force:
         if not self._gcStats.lastTime: return
         if mytime-self._gcStats.lastTime<self.settings.controlGC_everySeconds and \
            self._gcStats.processedRequestCount<self.settings.controlGC_everyRequestCount and \
            self._gcStats.processedDispatcherCount<self.settings.controlGC_everyDispatcherCount: return
      # collect garbage and reset stats
      mytime=self._getms()
      s=gc.collect()
      m2=self._countMemory()
      if s:
         self._logger(3, 'GC executed manually: collected %s objects, memore freed %smb, used %smb, peak %smb'%(s, round((m1.now-m2.now)/1024.0, 1), round(m2.now/1024.0, 1), round(m2.peak/1024.0, 1)))
      self._logger(4, 'GC executed manually: collected %s objects, memore freed %smb, used %smb, peak %smb'%(s, round((m1.now-m2.now)/1024.0, 1), round(m2.now/1024.0, 1), round(m2.peak/1024.0, 1)))
      self._speedStatsAdd('controlGC', self._getms()-mytime)
      self._gcStats.lastTime=self._getms(False)
      self._gcStats.processedRequestCount=0
      self._gcStats.processedDispatcherCount=0

   def _compressResponse(self, resp):
      """
      This method compress responce.

      :param Response() resp: Response object, prepared by WSGI backend.
      :return Response():
      """
      resp.direct_passthrough=False
      resp.data=self._compressGZIP(resp.data)
      resp.headers['Content-Encoding']='gzip'
      resp.headers['Vary']='Accept-Encoding'
      resp.headers['Content-Length']=len(resp.data)
      return resp

   def _compressGZIP(self, data):
      """
      This method compress input data with gzip.

      :param str data:
      :return str:
      """
      mytime=self._getms()
      gzip_buffer=StringIO()
      l=len(data)
      f=GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=3)
      f.write(data)
      f.close()
      res=gzip_buffer.getvalue()
      self._logger(4, '>> compression %s%%, original size %smb'%(round((1-len(res)/float(l))*100.0, 1), round(l/1024.0/1024.0, 2)))
      self._speedStatsAdd('compressResponse', self._getms()-mytime)
      return res

   def _uncompressGZIP(self, data):
      """
      This method uncompress input data with gzip.

      :param str data:
      :return str:
      """
      mytime=self._getms()
      gzip_buffer=StringIO(data)
      f=GzipFile('', 'r', 0, gzip_buffer)
      res=f.read()
      f.close()
      self._speedStatsAdd('uncompressResponse', self._getms()-mytime)
      return res

   def _copyRequestContext(self, request):
      """
      This method create full copy of <request> in <dict> format (returned <dict> will not be thread-local variable).

      :param Request() request:
      :return dict:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # prepare for pickle
      #! #57 It must be on TYPE-based, not NAME-based
      convWhitelist=['REQUEST_METHOD', 'PATH_INFO', 'SERVER_PROTOCOL', 'QUERY_STRING', 'REMOTE_ADDR', 'CONTENT_LENGTH', 'HTTP_USER_AGENT', 'SERVER_NAME', 'REMOTE_PORT', 'wsgi.url_scheme', 'SERVER_PORT', 'HTTP_HOST', 'CONTENT_TYPE', 'HTTP_ACCEPT_ENCODING', 'GATEWAY_INTERFACE']
      r=magicDict({
         'headers':dict([s for s in request.headers]),
         'cookies':request.cookies,
         'environ':dict([(k,v) for k,v in request.environ.items() if k in convWhitelist]),
         'remote_addr':request.remote_addr,
         'method':request.method,
         'url':request.url,
         'data':request.data,
         'form':request.form,
         'args':request.args
      })
      return r

   def _calcMimeType(self, request):
      """
      This method generate mime-type of response.

      :param Request() request:
      :return str:
      """
      s=('text/javascript' if request.method=='GET' else 'application/json')
      return s

   def _requestHandler(self, path, method=None):
      """
      This method is callback, that will be called by WSGI or another backend for every request.
      It implement error's handling of <server>._requestProcess() and some additional funtionality.

      :param str path:
      :param str method:
      :return Response():
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self.processingRequestCount+=1
      self._gcStats.processedRequestCount+=1
      # calculate connections per second
      nowMinute=int(time.time())/60
      #! добавить ведение истории в двух вариантах (self.connPerMinute.history1 и self.connPerMinute.history2) и сравнить их производительность
      if nowMinute!=self.connPerMinute.nowMinute:
         self.connPerMinute.nowMinute=nowMinute
         if self.connPerMinute.count:
            self.connPerMinute.oldCount=self.connPerMinute.count
         if self.connPerMinute.count>self.connPerMinute.maxCount:
            self.connPerMinute.maxCount=self.connPerMinute.count
         if self.connPerMinute.count<self.connPerMinute.minCount or not self.connPerMinute.minCount:
            self.connPerMinute.minCount=self.connPerMinute.count
         self.connPerMinute.count=0
      self.connPerMinute.count+=1
      # processing request
      try:
         res=self._requestProcess(path, method)
         if self.settings.controlGC: self._controlGC() # call GC manually
      except Exception:
         s=self._getErrorInfo()
         self._logger(1, 'ERROR processing request: %s'%(s))
         if self.settings.controlGC: self._controlGC() # call GC manually
         res=Response(status=500, response=s)
      self.processingRequestCount-=1
      return res

   def _requestProcess(self, path, method):
      """
      This method implement all logic of proccessing requests.

      :param str path:
      :param str method:
      :return Response():
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # DeepLock
      self._deepWait()
      path=self._formatPath(path)
      if path not in self.routes:
         self._logger(2, 'UNKNOWN_PATH:', path)
         return Response(status=404)
      # start processing request
      error=[]
      out=[]
      outHeaders={}
      outCookies=[]
      dataOut=[]
      mytime=self._getms()
      allowCompress=self.setts.allowCompress
      mimeType=self._calcMimeType(request)
      servedBy=request.__dict__['environ'].get('__flaskJSONRPCServer_binded', (None, None, None))
      self._logger(4, 'RAW_REQUEST:', request.url, request.method, request.get_data())
      if self._isFunction(self.settings.auth):
         if self.settings.auth(self, path, self._copyRequestContext(request), method) is not True:
            self._speedStatsAdd('generateResponse', self._getms()-mytime)
            self._logger(2, 'ACCESS_DENIED:', request.url, request.method, request.get_data())
            return Response(status=403)
      # CORS
      if self.setts.CORS:
         outHeaders.update({'Access-Control-Allow-Headers':'Origin, Authorization, X-Requested-With, Content-Type, Accept', 'Access-Control-Max-Age':'0', 'Access-Control-Allow-Methods':'GET, POST, OPTIONS'})
         if self._isDict(self.setts.CORS):
            outHeaders['Access-Control-Allow-Origin']=self.setts.CORS.get('origin', '*')
            outHeaders['Access-Control-Allow-Methods']=self.setts.CORS.get('methods', 'GET, POST, OPTIONS')
         else:
            outHeaders['Access-Control-Allow-Origin']='*'
      # Look at request's type
      if request.method=='OPTIONS':
         self._logger(4, 'REQUEST_TYPE == OPTIONS')
      elif request.method=='POST': #JSONRPC
         data=request.get_data()
         self._logger(4, 'REQUEST:', data)
         status, dataInList=self._parseRequest(data)
         if not status: #error of parsing
            error={"code": -32700, "message": "Parse error"}
         else:
            procTime=self._getms()
            for dataIn in dataInList:
               # protect from freezes at long batch-requests
               if self.setts.antifreeze_batchMaxTime and self._getms()-procTime>=self.setts.antifreeze_batchMaxTime:
                  self._logger(3, 'ANTIFREEZE_PROTECTION', len(dataInList), self._getms()-procTime)
                  if self.setts.antifreeze_batchBreak: break
                  else: self._sleep(self.setts.antifreeze_batchSleep)
                  procTime=self._getms()
               # try to process request
               if not(dataIn['jsonrpc']) or not(dataIn['method']) or (dataIn['params'] and not(self._isDict(dataIn['params'])) and not(self._isArray(dataIn['params']))): #syntax error in request
                  error.append({"code": -32600, "message": "Invalid Request"})
               elif dataIn['method'] not in self.routes[path]: #call of uncknown method
                  error.append({"code": -32601, "message": "Method not found", "id":dataIn['id']})
               else: #process correct request
                  # generate unique id
                  uniqueId='--'.join([dataIn['method'], str(dataIn['id']), str(random.randint(0, 999999)), str(random.randint(0, 999999)), str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr) or ''), self._sha1(request.get_data()), str(self._getms())])
                  # select dispatcher
                  dispatcher=self.routes[path][dataIn['method']]
                  # copy request's context
                  requestCopy=self._copyRequestContext(request)
                  requestCopy['servedBy']=servedBy
                  # select backend for executing
                  if dataIn['id'] is None: #notification request
                     execBackend=self.execBackend.get(dispatcher.notifBackendId, None)
                     if hasattr(execBackend, 'add'):
                        status, m=execBackend.add(uniqueId, path, dataIn, requestCopy)
                        if not status:
                           self._logger(1, 'Error in notifBackend.add(): %s'%m)
                     else:
                        status, params, result=self._callDispatcher(uniqueId, path, dataIn, requestCopy)
                  else: #simple request
                     execBackend=self.execBackend.get(dispatcher.dispatcherBackendId, None)
                     if execBackend and hasattr(execBackend, 'add') and hasattr(execBackend, 'check'):
                        # copy request's context
                        status, m=execBackend.add(uniqueId, path, dataIn, requestCopy)
                        if not status:
                           self._logger(1, 'Error in dispatcherBackend.add(): %s'%m)
                           result='Error in dispatcherBackend.add(): %s'%m
                        else:
                           status, params, result=execBackend.check(uniqueId)
                     else:
                        status, params, result=self._callDispatcher(uniqueId, path, dataIn, requestCopy)
                     if status:
                        if '_connection' in params: #get additional headers and cookies
                           outHeaders.update(params['_connection'].headersOut)
                           outCookies+=params['_connection'].cookiesOut
                           if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                           elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
                           mimeType=params['_connection'].mimeType
                        out.append({"id":dataIn['id'], "data":result})
                     else:
                        error.append({"code": 500, "message": result, "id":dataIn['id']})
         # prepare output for response
         self._logger(4, 'ERRORS:', error)
         self._logger(4, 'OUT:', out)
         if self._isDict(error): #error of parsing
            dataOut=self._prepResponse(error, isError=True)
         elif len(error) and len(dataInList)>1: #error for batch request
            for d in error: dataOut.append(self._prepResponse(d, isError=True))
         elif len(error): #error for simple request
            dataOut=self._prepResponse(error[0], isError=True)
         if len(out) and len(dataInList)>1: #response for batch request
            for d in out: dataOut.append(self._prepResponse(d, isError=False))
         elif len(out): #response for simple request
            dataOut=self._prepResponse(out[0], isError=False)
         dataOut=self._serializeJSON(dataOut)
      elif request.method=='GET': #JSONP fallback
         self._logger(4, 'REQUEST:', method, request.args)
         jsonpCB=request.args.get('jsonp', False)
         jsonpCB='%s(%%s);'%(jsonpCB) if jsonpCB else '%s;'
         if not method or method not in self.routes[path]: #call of uncknown method
            out.append({'jsonpCB':jsonpCB, 'data':{"error":{"code": -32601, "message": "Method not found"}}})
         elif not self.routes[path][method].allowJSONP: #fallback to JSONP denied
            self._logger(2, 'JSONP_DENIED:', path, method)
            return Response(status=403)
         else: #process correct request
            params=dict([(k, v) for k, v in request.args.items()])
            if 'jsonp' in params: del params['jsonp']
            dataIn={'method':method, 'params':params}
            # generate unique id
            uniqueId='--'.join([dataIn['method'], str(random.randint(0, 999999)), str(random.randint(0, 999999)), str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr) or ''), self._sha1(request.get_data()), str(self._getms())])
            # <id> passed like for normal request
            dataIn={'method':method, 'params':params, 'id':uniqueId}
            # select dispatcher
            dispatcher=self.routes[path][dataIn['method']]
            # copy request's context
            requestCopy=self._copyRequestContext(request)
            requestCopy['servedBy']=servedBy
            # select backend for executing
            execBackend=self.execBackend.get(dispatcher.dispatcherBackendId, None)
            if execBackend and hasattr(execBackend, 'add') and hasattr(execBackend, 'check'):
               status, m=execBackend.add(uniqueId, path, dataIn, requestCopy, isJSONP=jsonpCB)
               if not status:
                  self._logger(1, 'Error in dispatcherBackend.add(): %s'%m)
                  result='Error in dispatcherBackend.add(): %s'%m
               else:
                  status, params, result=execBackend.check(uniqueId)
            else:
               status, params, result=self._callDispatcher(uniqueId, path, dataIn, requestCopy, isJSONP=jsonpCB)
            if status:
               if '_connection' in params: #get additional headers and cookies
                  outHeaders.update(params['_connection'].headersOut)
                  outCookies+=params['_connection'].cookiesOut
                  jsonpCB=params['_connection'].jsonp
                  if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                  elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
                  mimeType=params['_connection'].mimeType
               out.append({'jsonpCB':jsonpCB, 'data':result})
            else:
               out.append({'jsonpCB':jsonpCB, 'data':result})
         # prepare output for response
         self._logger(4, 'ERRORS:', error)
         self._logger(4, 'OUT:', out)
         if len(out): #response for simple request
            dataOut=self._serializeJSON(out[0]['data'])
            dataOut=out[0]['jsonpCB']%(dataOut)
      self._logger(4, 'RESPONSE:', dataOut)
      resp=Response(response=dataOut, status=200, mimetype=mimeType)
      for hk, hv in outHeaders.items(): resp.headers[hk]=hv
      for c in outCookies:
         try: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647), domain=c.get('domain', '*'))
         except: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647))
      self._logger(4, 'GENERATE_TIME:', round(self._getms()-mytime, 1))
      self._speedStatsAdd('generateResponse', self._getms()-mytime)
      if resp.status_code!=200 or len(resp.data)<self.setts.compressMinSize or not allowCompress or 'gzip' not in request.headers.get('Accept-Encoding', '').lower():
         # without compression
         return resp
      # with compression
      mytime=self._getms()
      try: resp=self._compressResponse(resp)
      except Exception, e: print e
      self._logger(4, 'COMPRESSION TIME:', round(self._getms()-mytime, 1))
      return resp

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
      if not restartOn and not self.settings.controlGC: self.start(joinLoop=True)
      else:
         if restartOn:
            restartOn=restartOn if self._isArray(restartOn) else [restartOn]
         self.start(joinLoop=False)
         while True:
            self._sleep(sleep)
            if self.settings.controlGC: self._controlGC() # call GC manually
            if not restartOn: continue
            for cb in restartOn:
               if not cb: continue
               elif self._isFunction(cb) and cb(self) is not True: continue
               elif cb=='checkFileDescriptor' and not self._checkFileDescriptor(multiply=1.25): continue
               self.restart(joinLoop=False)
               break

   def _startExecBackends(self):
      """
      This merhod run all execute backends of server.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # start execBackends
      for _id, bck in self.execBackend.items():
         if hasattr(bck, 'start'): bck.start(self)

   def getWSGI(self):
      """
      This method return WSGI-app of server.
      """
      return self.flaskApp.wsgi_app

   def start(self, joinLoop=False):
      """
      This method start all execute backends of server, then start serving backend (werkzeug or pywsgi for now).
      If <joinLoop> is True, current thread join serving-thread.

      :param bool joinLoop:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      # start execBackends
      self._startExecBackends()
      # reset flask routing (it useful when somebody change self.flaskApp)
      self._registerServerUrl(dict([[s, self._requestHandler] for s in self.pathsDef]))
      if self.settings.allowCompress: self._logger(2, 'WARNING: included compression is slow')
      if self.setts.gevent:
         # serving with gevent's pywsgi
         if self.setts.blocking:
            self._logger(2, 'WARNING: blocking mode not implemented for gevent')
         self._tryGevent()
         self._logger(3, 'Server running as gevent..')
         # check what patches supports installed gevent version
         monkeyPatchSupported, _, _, _=inspect.getargspec(geventMonkey.patch_all)
         monkeyPatchArgs_default={'socket':False, 'dns':False, 'time':False, 'select':False, 'thread':False, 'os':True, 'ssl':False, 'httplib':False, 'subprocess':True, 'sys':False, 'aggressive':True, 'Event':False, 'builtins':True, 'signal':True}
         monkeyPatchArgs={}
         for k, v in monkeyPatchArgs_default.items():
            if k in monkeyPatchSupported: monkeyPatchArgs[k]=v
         # monkey patching
         geventMonkey.patch_all(**monkeyPatchArgs)
         self._importAll(forceDelete=True, scope=globals())
         # create server
         try:
            from gevent.pywsgi import WSGIServer
         except ImportError:
            self._throw('You switch server to GEVENT mode, but gevent not founded. For switching to DEV mode (without GEVENT) please pass <gevent>=False to constructor')
         from gevent.pool import Pool
         if self.setts.ssl: from gevent import ssl
         self._serverPool=[]
         self._server=[]
         wsgi=self.getWSGI()
         for i in xrange(len(self.setts.ip)):
            pool=Pool(None)
            self._serverPool.append(pool)
            bindAdress=self.setts.socket[i] if self.setts.socket[i] else (self.setts.ip[i], self.setts.port[i])
            logType=('default' if self.setts.debug else None)
            # wrapping WSGI for detecting adress
            if self.setts.socket[i]:
               __flaskJSONRPCServer_binded=(True, self.setts.socketPath[i], self.setts.socket[i])
            else:
               __flaskJSONRPCServer_binded=(False, self.setts.ip[i], self.setts.port[i])
            def wsgiWrapped(environ, start_response, __flaskJSONRPCServer_binded=__flaskJSONRPCServer_binded, __wsgi=wsgi):
               environ['__flaskJSONRPCServer_binded']=__flaskJSONRPCServer_binded
               return __wsgi(environ, start_response)
            # init wsgi backend
            if self.setts.ssl:
               # from functools import wraps
               # def sslwrap(func):
               #    @wraps(func)
               #    def bar(*args, **kw):
               #       kw['ssl_version']=ssl.PROTOCOL_TLSv1
               #       return func(*args, **kw)
               #    return bar
               # ssl.wrap_socket=sslwrap(ssl.wrap_socket)
               server=WSGIServer(bindAdress, wsgiWrapped, log=logType, spawn=pool, keyfile=self.setts.ssl[0], certfile=self.setts.ssl[1], ssl_version=ssl.PROTOCOL_TLSv1_2) #ssl.PROTOCOL_SSLv23
            else:
               server=WSGIServer(bindAdress, wsgiWrapped, log=logType, spawn=pool)
            self._server.append(server)
            # start wsgi backend
            if joinLoop and i+1==len(self.setts.ip): server.serve_forever()
            else: server.start()
      else:
         # serving with werkzeug
         if any(self.setts.socket):
            self._throw('Serving on raw-socket not supported without gevent')
         self._logger(4, 'SERVER RUNNING..')
         if not self.setts.debug:
            import logging
            log=logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
         sslContext=None
         if self.setts.ssl:
            import ssl
            sslContext=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2) #SSL.Context(SSL.SSLv23_METHOD)
            sslContext.load_cert_chain(self.setts.ssl[1], self.setts.ssl[0])
         self._registerServerUrl({'/_werkzeugStop/':self._werkzeugStop}, methods=['GET'])
         self._server=[]
         wsgi=self.getWSGI()
         from werkzeug.serving import run_simple as werkzeug_run
         for i in xrange(len(self.setts.ip)):
            # wrapping WSGI for detecting adress
            if self.setts.socket[i]:
               __flaskJSONRPCServer_binded=(True, self.setts.socketPath[i], self.setts.socket[i])
            else:
               __flaskJSONRPCServer_binded=(False, self.setts.ip[i], self.setts.port[i])
            def wsgiWrapped(environ, start_response, __flaskJSONRPCServer_binded=__flaskJSONRPCServer_binded, __wsgi=wsgi):
               environ['__flaskJSONRPCServer_binded']=__flaskJSONRPCServer_binded
               return __wsgi(environ, start_response)
            # init and start wsgi backend
            server=self._thread(werkzeug_run, args=[self.setts.ip[i], self.setts.port[i], wsgiWrapped], kwargs={'ssl_context':sslContext, 'use_debugger':self.setts.debug, 'threaded':not(self.setts.blocking), 'use_reloader':False})
            # server=self._thread(self.flaskApp.run, kwargs={'host':self.setts.ip[i], 'port':self.setts.port[i], 'ssl_context':sslContext, 'debug':self.setts.debug, 'threaded':not(self.setts.blocking)})
            self._server.append(server)
            if joinLoop and i+1==len(self.setts.ip): server.join()

   def _werkzeugStop(self):
      """
      This method implement hack for stopping flask's "werkzeug" WSGI backend.
      For more info see http://flask.pocoo.org/snippets/67/.

      :return str|None: Error message if some problems happened.
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      try:
         token1=request.args.get('token', '')
         token2=self._werkzeugStopToken
         self._werkzeugStopToken=''
         if not token2 or not token1 or token1!=token2: return 'Access denied'
         stop=request.environ.get('werkzeug.server.shutdown')
         if stop is None:
            return 'Cant find "werkzeug.server.shutdown"'
         else: stop()
      except Exception, e: return e

   def _stopExecBackends(self, timeout=20, processingDispatcherCountMax=0):
      """
      This merhod stop all execute backends of server.
      For more info see <server>._waitProcessingDispatchers().

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=self._getms()
      for _id, bck in self.execBackend.items():
         if hasattr(bck, 'stop'):
            bck.stop(self, timeout=timeout-(self._getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)

   def _waitProcessingDispatchers(self, timeout=20, processingDispatcherCountMax=0):
      """
      This method try to wait (for <timeout> seconds), while currently runed dispatchers will be done.
      If <processingDispatcherCountMax> is not 0, this check skip this nuber of runned dispatchers.

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      mytime=self._getms()
      if processingDispatcherCountMax is not False:
         while self.processingDispatcherCount>processingDispatcherCountMax:
            if timeout and self._getms()-mytime>=timeout*1000:
               self._logger(2, 'Warning: So long wait for completing dispatchers(%s)'%(self.processingDispatcherCount))
               break
            self._sleep(self.setts.sleepTime_checkProcessingCount)

   def stop(self, timeout=20, processingDispatcherCountMax=0):
      """
      This method stop all execute backends of server, then stop serving backend (werkzeug or gevent.pywsgi for now).
      For more info see <server>._waitProcessingDispatchers().

      :param int timeout:
      :param int processingDispatcherCountMax:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self._deepLock()
      mytime=self._getms()
      self._waitProcessingDispatchers(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop execBackends
      self._stopExecBackends(timeout=timeout-(self._getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)
      withError=[]
      # stop server's backend
      if self.setts.gevent:
         for s in self._server:
            try: s.stop(timeout=timeout-(self._getms()-mytime)/1000.0)
            except Exception, e: withError.append(e)
      else:
         for i in xrange(len(self._server)):
            self._werkzeugStopToken=self._randomEx(999999)
            #! all other methods, like "test_client()" and "test_request_context()", not has "return werkzeug.server.shutdown" in request.environ
            try:
               r=urllib2.urlopen('http://%s:%s/_werkzeugStop/?token=%s'%(self.setts.ip[i], self.setts.port[i], self._werkzeugStopToken)).read()
               if r: withError.append(r)
            except Exception, e: pass # error is normal in this case
      # check is errors happened
      if withError:
         self._deepUnlock()
         self._throw('\n'.join(withError))
      self._logger(3, 'SERVER STOPPED')
      if not self.setts.gevent:
         self._logger(0, 'INFO: Ignore all errors about "Unhandled exception in thread started by ..."\n')
      self.processingRequestCount=0
      self._deepUnlock()

   def restart(self, timeout=20, processingDispatcherCountMax=0, werkzeugTimeout=3, joinLoop=False):
      """
      This method call <server>.stop() and then <server>.start().
      For flask's "werkzeug" WSGI backend it wait for <werkzeugTimeout> seconds after <server>.stop() for avoiding error "adress already in use".
      For more info see <server>._waitProcessingDispatchers().

      :param int timeout:
      :param int processingDispatcherCountMax:
      :param int werkzeugTimeout:
      :param bool joinLoop:
      """
      if self._inChild():
         self._throw('This method "%s()" can be called only from <main> process'%sys._getframe().f_code.co_name)
      self.stop(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      if not self.setts.gevent: #! Without this werkzeug throw "adress already in use"
         self._sleep(werkzeugTimeout)
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
