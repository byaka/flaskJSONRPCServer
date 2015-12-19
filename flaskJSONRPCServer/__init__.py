#!/usr/bin/env python
# -*- coding: utf-8 -*-
__ver_major__ = 0
__ver_minor__ = 5
__ver_patch__ = 2
__ver_sub__ = "with_parallel_executing"
__version__ = "%d.%d.%d%s" % (__ver_major__, __ver_minor__, __ver_patch__, __ver_sub__)
"""
:authors: Jhon Byaka
:copyright: Copyright 2015, Buber
:license: Apache License 2.0

:license:

   Copyright 2015 Buber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
import sys, inspect, decimal, random, json, datetime, time, resource, os, zipfile, imp, urllib2, hashlib, httplib
from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType
Flask=None
request=None
Response=None

class UnixHTTPConnection(httplib.HTTPConnection):
   """
   This class adds support for unix-domain sockets to Python's httplib package.
   Thx to Erik van Zijst.
   https://bitbucket.org/evzijst/uhttplib/overview
   """
   def __init__(self, path, host='localhost', port=None, strict=None, timeout=None, socketClass=None):
      httplib.HTTPConnection.__init__(self, host, port=port, strict=strict, timeout=timeout)
      self.path=path
      if socketClass: self.socketClass=socketClass
      else:
         import socket
         self.socketClass=socket

   def connect(self):
      sock=self.socketClass.socket(self.socketClass.AF_UNIX, self.socketClass.SOCK_STREAM)
      sock.connect(self.path)
      self.sock=sock

class magicDict(dict):
   """Get and set values like in Javascript (dict.<key>)"""
   __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__

class flaskJSONRPCServer:
   """
      :param list ipAndPort: List or sequence, containing IP and PORT.
      :param bool blocking: Disable unblocking backend (also known as one-threaded).
      :param bool|dict cors: Add CORS headers to output (Access-Control-Allow-*). If dict, can contain values for <origin> and <method>.
      :param bool gevent: Use Gevent as a backend instead of Werkzeug.
      :param bool debug: Allow log messages from backend.
      :param bool log: Allow log messages about activity of flaskJSONRPCServer.
      :param bool fallback: Automatically accept and process JSONP requests.
      :param bool allowCompress: Allowing compression of output.
      :param list ssl: List or sequence, containing KEY and CERT.
      :param list(int,int) tweakDescriptors: List containing SOFT and HARD limits for descriptors.
      :param int compressMinSize: Max length of output in bytes that was not compressed.
      :param str|obj jsonBackend: Select JSON-backend for json.loads() and json.dumps(). If this parameter 'str' type, it will be imported.  If this parameter 'obj' type, it must contain methods loads() and dumps().
      :param str|dict|func notifBackend: Select Notif-backend for processing notify-requests. Lib include blocking backend ('simple') and non-blocking backend ('threadPool'). ThreadPool backend automatically switching to coroutines if gevent used. If this parameter 'dict' type, it must contain 'add' key as function. This function be called on notify-request. Optionally it can contain 'init' key as function and be called when server starting. If this parameter 'func' type, it will used like 'add'.
   """

   def __init__(self, bindAdress, blocking=False, cors=False, gevent=False, debug=False, log=True, fallback=True, allowCompress=False, ssl=False, tweakDescriptors=(65536, 65536), compressMinSize=1024, jsonBackend='simplejson', notifBackend='simple', dispatcherBackend='simple', auth=None):
      self.consoleColor=magicDict({'header':'\033[95m', 'okblue':'\033[94m', 'okgreen':'\033[92m', 'warning':'\033[93m', 'fail':'\033[91m', 'end':'\033[0m', 'bold':'\033[1m', 'underline':'\033[4m'})
      # Flask imported here for avoiding error in setup.py if Flask not installed yet
      global Flask, request, Response
      from flask import Flask, request, Response
      self._tweakLimit(tweakDescriptors)
      self.flaskAppName='_flaskJSONRPCServer:%s_'%(int(random.random()*99999))
      self.version=__version__
      if len(bindAdress)!=2: self._throw('Wrong "bindAdress" parametr')
      isSocket=str(type(bindAdress[1])) in ["<class 'socket._socketobject'>", "<class 'gevent.socket.socket'>"]
      self.settings=magicDict({
         'ip':bindAdress[0] if not isSocket else None,
         'port':bindAdress[1] if not isSocket else None,
         'socketPath':bindAdress[0] if isSocket else None,
         'socket':bindAdress[1] if isSocket else None,
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
         'antifreeze_batchMaxTime':2*1000,
         'antifreeze_batchSleep':1,
         'antifreeze_batchBreak':False,
         'auth':auth
      })
      self.setts=self.settings # backward compatible
      self.locked=False
      self._werkzeugStopToken=''
      self.deepLocked=False
      self.processingRequestCount=0
      self.processingDispatcherCount=0
      self.flaskApp=Flask(self.flaskAppName)
      self.pathsDef=['/<path>/', '/<path>', '/<path>/<method>/', '/<path>/<method>']
      self.routes={}
      self._registerServerUrl(dict([[s, self._requestHandler] for s in self.pathsDef]))
      self.fixJSON=self._fixJSON
      # select JSON-backend
      self.jsonBackend=json
      if self._isString(jsonBackend):
         try: self.jsonBackend=__import__(jsonBackend)
         except: self._logger('Cant import JSON-backend "%s", used standart'%(jsonBackend))
      elif jsonBackend: self.jsonBackend=jsonBackend
      # check JSON-backend
      try: self.jsonBackend.loads(self.jsonBackend.dumps([]))
      except Exception, e: self._throw('Unsupported JSONBackend %s: %s'%(jsonBackend, e))
      self.execBackend={}
      # select Dispatcher-backend
      self.defaultDispatcherBackendId=self._registerExecBackend(dispatcherBackend, notif=False)
      # select Notif-backend
      self.defaultNotifBackendId=self._registerExecBackend(notifBackend, notif=True)
      # prepare speedStats
      self.speedStats={}
      self.speedStatsMax={}
      self.connPerMinute=magicDict({'nowMinute':0, 'count':0, 'oldCount':0, 'maxCount':0, 'minCount':0})

   def _registerExecBackend(self, execBackend, notif):
      # check if execBackend._id passed. If true, not needed to initialize it
      if execBackend in self.execBackend: return execBackend
      # get _id of backend and prepare
      _id=None
      if execBackend in execBackendMap: #backend with non-blocking executing
         execBackend=execBackendMap[execBackend](notif)
         _id=getattr(execBackend, '_id', None)
      elif execBackend=='simple': #backend with blocking executing (like standart requests)
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

   def _getServerUrl(self):
      res=[str(s) for s in self.flaskApp.url_map.iter_rules()]
      return res

   def _registerServerUrl(self, urlMap, methods=['GET', 'OPTIONS', 'POST']):
      urlNow=self._getServerUrl()
      for s, h in urlMap.items():
         if s in urlNow: continue
         self.flaskApp.add_url_rule(rule=s, view_func=h, methods=methods, strict_slashes=False)

   def _import(self, modules, scope=None, forceDelete=True):
      """ replace existed imported module and monke_putch if needed """
      # if scope is None: scope=globals()
      #! Add checking with "monkey.is_module_patched()""
      for k, v in modules.items(): #delete existed
         if k in globals(): del globals()[k]
         if scope is not None and k in scope: del scope[k]
         if forceDelete and k in sys.modules: del sys.modules[k] # this allow unpatch monkey_patched libs
      if self.setts.gevent: #patching
         from gevent import monkey
         for k, v in modules.items():
            if not v: continue
            v=v if self._isArray(v) else [v]
            if hasattr(monkey, v[0]): getattr(monkey, v[0])(**(v[1] if len(v)>1 else {}))
      for k, v in modules.items(): #add to scope
         m=__import__(k)
         globals()[k]=m
         if scope is not None: scope[k]=m
      return scope

   def _importThreading(self, scope=None, forceDelete=True):
      modules={
         'threading':None,
         'thread':['patch_thread', {'threading':True}], #'_threading_local':True, 'Event':False', logging':True, 'existing_locks':True
         'time':'patch_time'
      }
      return self._import(modules, scope=scope, forceDelete=forceDelete)

   def _importSocket(self, scope=None, forceDelete=True):
      modules={
         'socket':['patch_socket', {'dns':True, 'aggressive':True}],
         'ssl':'patch_ssl'
      }
      return self._import(modules, scope=scope, forceDelete=forceDelete)

   def _importAll(self, scope=None, forceDelete=True):
      self._importThreading(scope=scope, forceDelete=forceDelete)
      self._importSocket(scope=scope, forceDelete=forceDelete)

   def _tweakLimit(self, descriptors=(65536, 65536)):
      """ Tweak ulimit for more file descriptors """
      if descriptors:
         try: #for Linux
            if resource.getrlimit(resource.RLIMIT_NOFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_NOFILE, descriptors)
         except: pass
         try: #for BSD
            if resource.getrlimit(resource.RLIMIT_OFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_OFILE, descriptors)
         except: pass

   def _countFileDescriptor(self):
      mytime=self._getms()
      pid=os.getpid()
      try:
         c=len([s for s in os.listdir('/proc/%s/fd'%pid)])
         self._speedStatsAdd('countFileDescriptor', self._getms()-mytime)
         return c
      except Exception, e:
         self._speedStatsAdd('countFileDescriptor', self._getms()-mytime)
         self._logger("Can't count File Descriptor for PID %s: %s"%(pid, e))
         return None

   def _checkFileDescriptor(self, multiply=1.0):
      limit=None
      try: limit=resource.getrlimit(resource.RLIMIT_NOFILE)[0] #for Linux
      except: pass
      try: limit=resource.getrlimit(resource.RLIMIT_OFILE)[0] #for BSD
      except: pass
      if limit is None:
         self._logger("Can't get File Descriptor Limit")
         return None
      c=self._countFileDescriptor()
      if c is None: return None
      return (c*multiply>=limit)

   def _getms(self):
      return time.time()*1000.0

   def _isFunction(self, o): return hasattr(o, '__call__')

   def _isInstance(self, o): return isinstance(o, (InstanceType))

   def _isArray(self, o): return isinstance(o, (list))

   def _isDict(self, o): return isinstance(o, (dict))

   def _isString(self, o): return isinstance(o, (str, unicode))

   def _isNum(self, var): return isinstance(var, (int, float, long, complex, decimal.Decimal))

   def _fileGet(self, fName, method='r'):
      """ Get content from file,using $method and if file is ZIP, read file $method in this archive """
      fName=fName.encode('cp1251')
      if not os.path.isfile(fName): return None
      if zipfile.is_zipfile(fName):
         c=zipfile.ZipFile(fName, method)
         try: s=c.read(method)
         except Exception, e:
            self._logger('Error fileGet', fName, ',', method, e)
            s=None
         try: c.close()
         except: pass
      else:
         try:
            with open(fName, method) as f: s=f.read()
         except Exception, e:
            self._logger('Error fileGet', fName, ',', method, e)
            s=None
      return s

   def _fileWrite(self, fName, text, mode='w'):
      if not self._isString(text): text=repr(text)
      with open(fName, mode) as f: f.write(text)

   def _strGet(self, text, pref='', suf='', index=0, default=None):
      """ Return pattern by format pref+pattenr+suf """
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
      #wrapper for sha1
      try:
         try: c=hashlib.sha1(text)
         except UnicodeEncodeError: c=hashlib.sha1(text.encode('utf8'))
         return c.hexdigest()
      except Exception, e:
         self._logger('ERROR in _sha1():', e)
         return str(random.randint(99999, 9999999))

   def _sha256(self, text):
      #wrapper for sha256
      try:
         try: c=hashlib.sha256(text)
         except UnicodeEncodeError: c=hashlib.sha256(text.encode('utf8'))
         return c.hexdigest()
      except Exception, e:
         self._logger('ERROR in _sha256():', e)
         return str(random.randint(99999, 9999999))

   def _throw(self, data):
      raise ValueError(data)

   def _sleep(self, s):
      if str(type(time.sleep))=="<type 'builtin_function_or_method'>" and self.setts.gevent:
         # if gevent=True, we need patched 'sleep()' method
         self._importThreading()
      elif str(type(time.sleep))=="<type 'function'>" and not self.setts.gevent:
         # if gevent=False, we need original 'sleep()' method
         self._importThreading(forceDelete=True)
      time.sleep(s)

   def _getScriptPath(self, full=False):
      if full:
         return os.path.realpath(sys.argv[0])
      else:
         return os.path.dirname(os.path.realpath(sys.argv[0]))

   def _getScriptName(self, withExt=False):
      if withExt: return os.path.basename(sys.argv[0])
      else: return os.path.splitext(os.path.basename(sys.argv[0]))[0]

   def _thread(self, target, args=None, kwargs=None, forceNative=False):
      if forceNative: #force using NATIVE python threads, insted of coroutines
         import gevent
         t=gevent._threading.start_new_thread(target, tuple(args or []), kwargs or {})
      else:
         self._importThreading()
         t=threading.Thread(target=target, args=args or [], kwargs=kwargs or {})
         t.start()
      return t

   def _importGlobalsFromParent(self, scope=None, typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType]):
      """
      This function import global attrs from parent module (main program) to given scope.
      Imported attrs can be filtered by type.
      Source based on http://stackoverflow.com/a/9493520/5360266
      """
      scope=scope if scope is not None else globals()
      main=sys.argv[0]
      try:
         for stk in reversed(inspect.stack()):
            # find frame of parent by module's path
            if main!=stk[1]: continue
            m=inspect.getmodule(stk[0])
            for k in dir(m):
               # check type if needed
               if typeOf is None or isinstance(getattr(m, k), tuple(typeOf)): scope[k]=getattr(m, k)
            break
      except Exception, e:
         self._throw("Cant import parent's globals: %s"%e)

   def _speedStatsAdd(self, name, val):
      if name not in self.speedStats: self.speedStats[name]=[]
      if name not in self.speedStatsMax: self.speedStatsMax[name]=0
      self.speedStats[name].append(val)
      if val>self.speedStatsMax[name]: self.speedStatsMax[name]=val
      if len(self.speedStats[name])>99999:
         self.speedStats[name]=[self.speedStatsMax[name]]

   def registerInstance(self, dispatcher, path='', fallback=None, dispatcherBackend=None, notifBackend=None):
      """Create dispatcher for methods of given class's instance.

      *If methods has attribute _alias(List or String), it used as aliases of name.*

      :param instance dispatcher: Class's instance.
      :param str path: Optional string that contain path-prefix.
      """
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
      """Create dispatcher for given function.

      *If methods has attribute _alias(List or String), it used as aliases of name.*

      :param func dispatcher: Link to function.
      :param str path: Optional string that contain path-prefix.
      """
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
      path=path or '/'
      path=path if path.startswith('/') else '/'+path
      path=path if path.endswith('/') else path+'/'
      return path

   def _parseJSON(self, data):
      mytime=self._getms()
      s=self.jsonBackend.loads(data)
      self._speedStatsAdd('parseJSON', self._getms()-mytime)
      return s

   def _parseRequest(self, data):
      try:
         mytime=self._getms()
         tArr1=self._parseJSON(data)
         tArr2=[]
         tArr1=tArr1 if self._isArray(tArr1) else [tArr1] #support for batch requests
         for r in tArr1:
            tArr2.append({'jsonrpc':r.get('jsonrpc', None), 'method':r.get('method', None), 'params':r.get('params', None), 'id':r.get('id', None)})
         self._speedStatsAdd('parseRequest', self._getms()-mytime)
         return True, tArr2
      except Exception, e:
         self._logger('Error parseRequest', e)
         return False, e

   def _prepResponse(self, data, isError=False):
      id=data.get('id', None)
      if 'id' in data: del data['id']
      if isError:
         s={"jsonrpc": "2.0", "error": data, "id": id}
      elif id:
         s={"jsonrpc": "2.0", "result": data['data'], "id": id}
      return s

   def _fixJSON(self, o):
      if isinstance(o, decimal.Decimal): return str(o) #fix Decimal conversion
      elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)): return o.isoformat() #fix DateTime conversion
      # elif self._isNum(o) and o>2**31: return str(o) #? fix LONG

   def _serializeJSON(self, data):
      def _fixJSON(o):
         if self._isFunction(self.fixJSON): return self.fixJSON(o)
      mytime=self._getms()
      s=self.jsonBackend.dumps(data, indent=None, separators=(',',':'), ensure_ascii=True, sort_keys=True, default=_fixJSON)
      self._speedStatsAdd('serializeJSON', self._getms()-mytime)
      return s

   def _getErrorInfo(self):
      tArr=inspect.trace()[-1]
      fileName=tArr[1]
      lineNo=tArr[2]
      exc_obj=sys.exc_info()[1]
      s='%s:%s > %s'%(fileName, lineNo, exc_obj)
      sys.exc_clear()
      return s

   def stats(self, inMS=False):
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

   def _logger(self, *args):
      if not self.setts.log: return
      for i in xrange(len(args)):
         s=args[i]
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
      if dispatcher is None: self.locked=True #global lock
      else: #local lock
         if self._isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'): dispatcher.__func__.__locked=True
            else: dispatcher.__locked=True

   def unlock(self, dispatcher=None, exclusive=False):
      #exclusive=True unlock dispatcher also if global lock=True
      if dispatcher is None: self.locked=False #global lock
      else: #local lock
         if self._isFunction(dispatcher):
            if hasattr(dispatcher, '__func__'): dispatcher.__func__.__locked=False if exclusive else None
            else: dispatcher.__locked=False if exclusive else None

   def wait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      sleepMethod=sleepMethod or self._sleep
      if dispatcher is None: #global lock
         while self.locked:
            if returnStatus: return True
            sleepMethod(self.setts.sleepTime_waitLock) #global lock
      else: #local and global lock
         if self._isFunction(dispatcher):
            while True:
               s=getattr(dispatcher, '__locked', None)
               if s is False: break #exclusive unlock
               elif not s and not self.locked: break
               if returnStatus: return True
               sleepMethod(self.setts.sleepTime_waitLock)
      if returnStatus: return False

   def _deepLock(self):
      self.deepLocked=True

   def _deepUnlock(self):
      self.deepLocked=False

   def _deepWait(self):
      while self.deepLocked: self._sleep(self.setts.sleepTime_waitDeepLock)

   def _reload(self, api, clearOld=False, timeout=60, processingDispatcherCountMax=0, safely=True):
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
            self._logger(msg)
            self._logger('Server is reloaded in safe-mode, so all dispatchers was restored. But if you overloaded some globals in callback, they can not be restored!')
         else: self._throw(msg)
      # start execBackends
      self._startExecBackends()
      self._deepUnlock()

   def reload(self, api, clearOld=False, timeout=60, processingDispatcherCountMax=0, safely=True):
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
         name=o.get('dispatcherName', None)
         # start importing new code
         if scriptPath and dispatcherName and self._isString(dispatcherName):
            if exclusiveModule:
               module=imp.load_source(scriptName, scriptPath)
            else:
               if '%s_%s'%(scriptName, scriptPath) not in mArr:
                  mArr['%s_%s'%(scriptName, scriptPath)]={'module':imp.load_source(scriptName, scriptPath), 'dArr':{}}
               module=mArr['%s_%s'%(scriptName, scriptPath)]['module']
            if exclusiveDispatcher or '%s_%s'%(scriptName, scriptPath) not in mArr:
               dispatcher=getattr(module, dispatcherName)
            else:
               if dispatcherName not in mArr['%s_%s'%(scriptName, scriptPath)]['dArr']:
                  mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]=getattr(module, dispatcherName)
                  if isInstance:
                     mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]=mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]()
               dispatcher=mArr['%s_%s'%(scriptName, scriptPath)]['dArr'][dispatcherName]
         elif name and self._isFunction(dispatcherName):
            dispatcher=dispatcherName
            module=dispatcher
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
               for n in dir(dispatcher):
                  link=getattr(dispatcher, n)
                  if not self._isFunction(link): continue
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

   def _callDispatcher(self, path, data, request, isJSONP=False, nativeThread=None, overload=None):
      try:
         self.processingDispatcherCount+=1
         if not nativeThread:
            sleepMethod=self._sleep
         else:
            #import native time.sleep() for native threads
            from gevent import monkey
            sleepMethod=monkey.get_original('time', 'sleep')
         params={}
         dispatcher=self.routes[path][data['method']].link
         _args, _, _, _=inspect.getargspec(dispatcher)
         _args=[s for i, s in enumerate(_args) if not(i==0 and s=='self')]
         if self._isDict(data['params']): params=data['params']
         elif self._isArray(data['params']): #convert *args to **kwargs
            for i, v in enumerate(data['params']): params[_args[i]]=v
         if '_connection' in _args: #add connection info if needed
            params['_connection']={
               'headers':dict([h for h in request.headers]) if not self._isDict(request.headers) else request.headers,
               'cookies':request.cookies,
               'ip':request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
               'cookiesOut':[],
               'headersOut':{},
               'jsonp':isJSONP,
               'allowCompress':self.setts.allowCompress,
               'server':self,
               'call':magicDict({
                  'lock':lambda: self.lock(dispatcher=dispatcher),
                  'unlock':lambda exclusive=False: self.unlock(dispatcher=dispatcher, exclusive=exclusive),
                  'wait':lambda returnStatus=False: self.wait(dispatcher=dispatcher, sleepMethod=sleepMethod, returnStatus=returnStatus),
                  'sleep':sleepMethod,
               }),
               'nativeThread':nativeThread if nativeThread is not None else not(self.setts.gevent),
               'notify':not('id' in data),
               'dispatcher':dispatcher,
               'path':path,
               'dispatcherName':data['method']
            }
            # overload _connection
            if self._isDict(overload):
               for k, v in overload.items(): params['_connection'][k]=v
            elif self._isFunction(overload):
               params['_connection']=overload(params['_connection'])
            params['_connection']=magicDict(params['_connection'])
         #locking
         self.wait(dispatcher=dispatcher, sleepMethod=sleepMethod)
         #call dispatcher
         mytime=self._getms()
         result=dispatcher(**params)
         self._speedStatsAdd('callDispatcher', self._getms()-mytime)
         self.processingDispatcherCount-=1
         return True, params, result
      except Exception:
         self.processingDispatcherCount-=1
         return False, params, self._getErrorInfo()

   def _compress(self, resp):
      # provide compression of response
      mytime=self._getms()
      from cStringIO import StringIO
      import gzip
      resp.direct_passthrough=False
      gzip_buffer=StringIO()
      gzip_file=gzip.GzipFile(mode='wb', fileobj=gzip_buffer)
      gzip_file.write(resp.data)
      gzip_file.close()
      resp.data=gzip_buffer.getvalue()
      resp.headers['Content-Encoding']='gzip'
      resp.headers['Vary']='Accept-Encoding'
      resp.headers['Content-Length']=len(resp.data)
      self._speedStatsAdd('compressResponse', self._getms()-mytime)
      return resp

   def _copyRequestContext(self, request):
      r=magicDict({'headers':dict([h for h in request.headers]), 'cookies':request.cookies, 'environ':request.environ, 'remote_addr':request.remote_addr, 'method':request.method, 'url':request.url, 'data':request.data, 'form':request.form, 'args':request.args})
      return r

   def _requestHandler(self, path, method=None):
      # DeepLock
      self._deepWait()
      # calculate connections per second
      nowMinute=int(time.time())/60
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
      path=self._formatPath(path)
      if path not in self.routes:
         self._logger('UNKNOWN_PATH:', path)
         return Response(status=404)
      # start processing request
      self.processingRequestCount+=1
      error=[]
      out=[]
      outHeaders={}
      outCookies=[]
      dataOut=[]
      mytime=self._getms()
      allowCompress=self.setts.allowCompress
      self._logger('RAW_REQUEST:', request.url, request.method, request.get_data())
      if self._isFunction(self.settings.auth):
         if self.settings.auth(self, path, self._copyRequestContext(request), method) is not True:
            self.processingRequestCount-=1
            self._speedStatsAdd('generateResponse', self._getms()-mytime)
            self._logger('ACCESS_DENIED:', request.url, request.method, request.get_data())
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
         self._logger('REQUEST_TYPE == OPTIONS')
      elif request.method=='POST': #JSONRPC
         data=request.get_data()
         self._logger('REQUEST:', data)
         status, dataInList=self._parseRequest(data)
         if not status: #error of parsing
            error={"code": -32700, "message": "Parse error"}
         else:
            procTime=self._getms()
            for dataIn in dataInList:
               # protect from freezes at long batch-requests
               if self.setts.antifreeze_batchMaxTime and self._getms()-procTime>=self.setts.antifreeze_batchMaxTime:
                  if self.setts.antifreeze_batchBreak: break
                  else: self._sleep(self.setts.antifreeze_batchSleep)
                  procTime=self._getms()
               # process dispatcher for request
               if not(dataIn['jsonrpc']) or not(dataIn['method']) or (dataIn['params'] and not(self._isDict(dataIn['params'])) and not(self._isArray(dataIn['params']))): #syntax error in request
                  error.append({"code": -32600, "message": "Invalid Request"})
               elif dataIn['method'] not in self.routes[path]: #call of uncknown method
                  error.append({"code": -32601, "message": "Method not found", "id":dataIn['id']})
               else: #process correct request
                  # generate unique id
                  uniqueId='--'.join([dataIn['method'], str(dataIn['id']), str(random.randint(0, 999999)), str(random.randint(0, 999999)), str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr) or ''), self._sha1(request.get_data()), str(self._getms())])
                  # select dispatcher
                  dispatcher=self.routes[path][dataIn['method']]
                  # select backend for executing
                  if not dataIn['id']: #notification request
                     execBackend=self.execBackend.get(dispatcher.notifBackendId, None)
                     if hasattr(execBackend, 'add'):
                        # copy request's context
                        status, m=execBackend.add(uniqueId, path, dataIn, self._copyRequestContext(request))
                        if not status: self._logger('Error in notifBackend.add(): %s'%m)
                     else:
                        status, params, result=self._callDispatcher(path, dataIn, request)
                  else: #simple request
                     execBackend=self.execBackend.get(dispatcher.dispatcherBackendId, None)
                     if execBackend and hasattr(execBackend, 'add') and hasattr(execBackend, 'check'):
                        # copy request's context
                        status, m=execBackend.add(uniqueId, path, dataIn, self._copyRequestContext(request))
                        if not status: result='Error in dispatcherBackend.add(): %s'%m
                        else: status, params, result=execBackend.check(uniqueId)
                     else:
                        status, params, result=self._callDispatcher(path, dataIn, request)
                     if status:
                        if '_connection' in params: #get additional headers and cookies
                           outHeaders.update(params['_connection'].headersOut)
                           outCookies+=params['_connection'].cookiesOut
                           if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                           elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
                        out.append({"id":dataIn['id'], "data":result})
                     else:
                        error.append({"code": 500, "message": result, "id":dataIn['id']})
         # prepare output for response
         self._logger('ERRORS:', error)
         self._logger('OUT:', out)
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
         self._logger('REQUEST:', method, request.args)
         jsonpCB=request.args.get('jsonp', False)
         jsonpCB='%s(%%s);'%(jsonpCB) if jsonpCB else '%s;'
         if not method or method not in self.routes[path]: #call of uncknown method
            out.append({'jsonpCB':jsonpCB, 'data':{"error":{"code": -32601, "message": "Method not found"}}})
         elif not self.routes[path][method].allowJSONP: #fallback to JSONP denied
            self._logger('JSONP_DENIED:', path, method)
            self.processingRequestCount-=1
            return Response(status=403)
         else: #process correct request
            params=dict([(k, v) for k, v in request.args.items()])
            if 'jsonp' in params: del params['jsonp']
            dataIn={'method':method, 'params':params}
            # generate unique id
            uniqueId='--'.join([dataIn['method'], str(random.randint(0, 999999)), str(random.randint(0, 999999)), str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr) or ''), self._sha1(request.get_data()), str(self._getms())])
            # select dispatcher
            dispatcher=self.routes[path][dataIn['method']]
            # select backend for executing
            execBackend=self.execBackend.get(dispatcher.dispatcherBackendId, None)
            if execBackend and hasattr(execBackend, 'add') and hasattr(execBackend, 'check'):
               # copy request's context
               status, m=execBackend.add(uniqueId, path, dataIn, self._copyRequestContext(request), isJSONP=jsonpCB)
               if not status: result='Error in dispatcherBackend.add(): %s'%m
               else: status, params, result=execBackend.check(uniqueId)
            else:
               status, params, result=self._callDispatcher(path, dataIn, request, isJSONP=jsonpCB)
            if status:
               if '_connection' in params: #get additional headers and cookies
                  outHeaders.update(params['_connection'].headersOut)
                  outCookies+=params['_connection'].cookiesOut
                  jsonpCB=params['_connection'].jsonp
                  if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                  elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
               out.append({'jsonpCB':jsonpCB, 'data':result})
            else:
               out.append({'jsonpCB':jsonpCB, 'data':result})
         # prepare output for response
         self._logger('ERRORS:', error)
         self._logger('OUT:', out)
         if len(out): #response for simple request
            dataOut=self._serializeJSON(out[0]['data'])
            dataOut=out[0]['jsonpCB']%(dataOut)
      self._logger('RESPONSE:', dataOut)
      resp=Response(response=dataOut, status=200, mimetype=('text/javascript' if request.method=='GET' else 'application/json'))
      for hk, hv in outHeaders.items(): resp.headers[hk]=hv
      for c in outCookies:
         try: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647), domain=c.get('domain', '*'))
         except: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647))
      self._logger('GENERATE_TIME:', round(self._getms()-mytime, 1))
      self._speedStatsAdd('generateResponse', self._getms()-mytime)
      self.processingRequestCount-=1
      if resp.status_code!=200 or len(resp.data)<self.setts.compressMinSize or not allowCompress or 'gzip' not in request.headers.get('Accept-Encoding', '').lower():
         # without compression
         return resp
      # with compression
      mytime=self._getms()
      resp=self._compress(resp)
      self._logger('COMPRESSION TIME:', round(self._getms()-mytime, 1))
      return resp

   def serveForever(self, restartOn=False, sleep=10):
      if not restartOn: self.start(joinLoop=True)
      else:
         restartOn=restartOn if self._isArray(restartOn) else [restartOn]
         self.start(joinLoop=False)
         while True:
            self._sleep(sleep)
            for cb in restartOn:
               if self._isFunction(cb) and cb(self) is not True: continue
               elif cb=='checkFileDescriptor' and not self._checkFileDescriptor(multiply=1.25): continue
               self.restart()
               break

   def _startExecBackends(self):
      # start execBackends
      for _id, bck in self.execBackend.items():
         if hasattr(bck, 'start'): bck.start(self)

   def start(self, joinLoop=False):
      """ Start server's loop """
      # start execBackends
      self._startExecBackends()
      # reset flask routing (it useful when somebody change self.flaskApp)
      self._registerServerUrl(dict([[s, self._requestHandler] for s in self.pathsDef]))
      if self.setts.gevent:
         self._logger('SERVER RUNNING AS GEVENT..')
         try: import gevent
         except ImportError: self._throw('gevent backend not found')
         self._importAll()
         gevent.monkey.patch_all(sys=False, os=False, thread=False, time=False, ssl=False, socket=False) #! "os" may cause some problems with multiprocessing. but better get original objects in execBackend
         from gevent.pywsgi import WSGIServer
         from gevent.pool import Pool
         self._serverPool=Pool(None)
         bindAdress=(self.setts.ip, self.setts.port) if not self.setts.socket else self.setts.socket
         if self.setts.ssl:
            from gevent import ssl
            # from functools import wraps
            # def sslwrap(func):
            #    @wraps(func)
            #    def bar(*args, **kw):
            #       kw['ssl_version']=ssl.PROTOCOL_TLSv1
            #       return func(*args, **kw)
            #    return bar
            # ssl.wrap_socket=sslwrap(ssl.wrap_socket)
            self._server=WSGIServer(bindAdress, self.flaskApp, log=('default' if self.setts.debug else False), spawn=self._serverPool, keyfile=self.setts.ssl[0], certfile=self.setts.ssl[1], ssl_version=ssl.PROTOCOL_TLSv1_2) #ssl.PROTOCOL_SSLv23
         else:
            self._server=WSGIServer(bindAdress, self.flaskApp, log=('default' if self.setts.debug else False), spawn=self._serverPool)
         if joinLoop: self._server.serve_forever()
         else: self._server.start()
      else:
         self._logger('SERVER RUNNING..')
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
         self._server=self._thread(self.flaskApp.run, kwargs={'host':self.setts.ip, 'port':self.setts.port, 'ssl_context':sslContext, 'debug':self.setts.debug, 'threaded':not(self.setts.blocking)})
         if joinLoop: self._server.join()

   def _werkzeugStop(self):
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
      # stop execBackends
      mytime=self._getms()
      for _id, bck in self.execBackend.items():
         if hasattr(bck, 'stop'):
            bck.stop(self, timeout=timeout-(self._getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)

   def _waitProcessingDispatchers(self, timeout=20, processingDispatcherCountMax=0):
      mytime=self._getms()
      if processingDispatcherCountMax is not False:
         while self.processingDispatcherCount>processingDispatcherCountMax:
            if timeout and self._getms()-mytime>=timeout*1000:
               self._logger('Warning: So long wait for completing dispatchers(%s)'%(self.processingDispatcherCount))
               break
            self._sleep(self.setts.sleepTime_checkProcessingCount)

   def stop(self, timeout=20, processingDispatcherCountMax=0):
      self._deepLock()
      mytime=self._getms()
      self._waitProcessingDispatchers(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop execBackends
      self._stopExecBackends(timeout=timeout-(self._getms()-mytime)/1000.0, processingDispatcherCountMax=processingDispatcherCountMax)
      # stop server's backend
      if self.setts.gevent:
         try: self._server.stop(timeout=timeout-(self._getms()-mytime)/1000.0)
         except Exception, e:
            self._deepUnlock()
            self._throw(e)
      else:
         self._werkzeugStopToken=str(int(random.random()*999999))
         #! all other methods (test_client() and test_request_context()) not "return werkzeug.server.shutdown" in request.environ
         try:
            r=urllib2.urlopen('http://%s:%s/_werkzeugStop/?token=%s'%(self.setts.ip, self.setts.port, self._werkzeugStopToken)).read()
         except Exception, e: r=''
         if r:
            self._deepUnlock()
            self._throw(r)
      self._logger('SERVER STOPPED')
      self.processingRequestCount=0
      self._deepUnlock()

   def restart(self, timeout=20, processingDispatcherCountMax=0, werkzeugTimeout=3):
      self.stop(timeout=timeout, processingDispatcherCountMax=processingDispatcherCountMax)
      if not self.setts.gevent: #! Without this werkzeug throw "adress already in use"
         self._sleep(werkzeugTimeout)
      self.start()

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

class execBackend_threaded:
   def __init__(self, poolSize=5, sleepTime_emptyQueue=0.02, sleepTime_cicleWait=0.02, id='execBackend_threaded', forceNative=False):
      self.settings=magicDict({
         'poolSize':poolSize,
         'sleepTime_emptyQueue':sleepTime_emptyQueue,
         'sleepTime_cicleWait':sleepTime_cicleWait,
         'forceNative':forceNative
      })
      from collections import deque
      self.queue=deque()
      self._poolSize=0
      self._id=id
      if forceNative: self._id+='Native'
      self._mainCicleThread=None

   def start(self, server):
      if self._mainCicleThread: return
      if self.settings.forceNative and server.setts.gevent:
         server._logger('Warning: notifBackend forced to use Native Threads')
      self._parentServer=server
      self._mainCicleThread=server._thread(self.mainCicle)

   def mainCicle(self):
      #main cicle for processing notifs. Run on strating backend
      while True:
         self._parentServer._deepWait()
         self._parentServer._sleep(self.settings.sleepTime_cicleWait)
         if not len(self.queue): continue
         tArr1=self.queue.popleft()
         mytime=self._parentServer._getms()
         while self._poolSize>=self.settings.poolSize:
            self._parentServer._sleep(self.settings.sleepTime_emptyQueue)
         self._poolSize+=1
         self._parentServer._speedStatsAdd('notifBackend_wait', self._parentServer._getms()-mytime)
         isForceNative=self.settings.forceNative and self._parentServer.setts.gevent
         self._parentServer._thread(self.childExecute, args=[tArr1, isForceNative or not(self._parentServer.setts.gevent)], forceNative=isForceNative)

   def childExecute(self, p, nativeThread=False):
      status, params, result=self._parentServer._callDispatcher(p['path'], p['dataIn'], p['request'], nativeThread=nativeThread, isJSONP=p.get('isJSONP', False))
      if not status:
         self._parentServer._logger('ERROR in notifBackend._callDispatcher():', result)
         print '!!! ERROR_processing', result
      self._poolSize-=1

   def add(self, uniqueId, path, dataIn, request, isJSONP=False):
      #callback for adding notif to queue
      try:
         self.queue.append({'uniqueId':uniqueId, 'isJSONP':isJSONP, 'path':path, 'dataIn':dataIn, 'request':request, 'mytime':self._parentServer._getms()})
         return True, len(self.queue)
      except Exception, e:
         print '!!! ERROR _notifBackend_threadPool_add', e
         return None, str(e)

   def stats(self, inMS=False):
      r={
         '%s_queue'%self._id:len(self.queue)
      }
      return r

class execBackend_parallelWithSocket:
   def __init__(self, poolSize=1, importGlobalsFromParent=True, parentGlobals=None, sleepTime_resultCheck=0.1, sleepTime_emptyQueue=0.2, sleepTime_waitLock=0.75, sleepTime_lazyRequest=1*60*1000, sleepTime_checkPoolStopping=0.3, allowThreads=False, id='execBackend_parallelWithSocket', socketPath=None, saveResult=True):
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
         'saveResult':saveResult
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

   def start(self, server):
      if self._server: return
      # generate socket-file
      if not self.socketPath:
         self.socketPath='%s/.%s.%s.sock'%(server._getScriptPath(), server._getScriptName(withExt=False), self._id)
      if os.path.exists(self.socketPath): os.remove(self.socketPath)
      # generate access token
      self.token='--'.join([str(int(random.random()*999999)) for i in xrange(10)])
      # start processesPool
      """
      if this block after starting new API, server has really strange problems with "doubled" variables and etc.
      But if this code before "self._server.start()", all work fine.
      I not understand why this happened and i spend more then two days for debugging.
      """
      import multiprocessing
      for i in xrange(self.settings.poolSize): # multiprocessing.cpu_count()
         p=multiprocessing.Process(target=self.childCicle, args=(server, ))
         p.start()
         self._pool.append(p)
      # import parent's globals if needed
      if self.settings.importGlobalsFromParent:
         server._importGlobalsFromParent(scope=self.parentGlobals)
      # create api on unix-socket
      self._parentServer=server
      server._importAll(forceDelete=True) #IMPORTANT! without this child hangs on socket operations
      listener=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      listener.bind(self.socketPath)
      listener.listen(1)
      self._server=flaskJSONRPCServer([self.socketPath, listener], blocking=False, cors=False, gevent=server.setts.gevent, debug=False, log=False, fallback=False, allowCompress=False, jsonBackend='simplejson', tweakDescriptors=None, notifBackend='simple', dispatcherBackend='simple')
      self._server.setts.antifreeze_batchMaxTime=1*1000
      self._server.setts.antifreeze_batchBreak=False
      self._server.setts.antifreeze_batchSleep=2
      self._server.registerFunction(self.api_queueGet, path='/queue', name='get')
      self._server.registerFunction(self.api_queueResult, path='/queue', name='result')
      self._server.registerFunction(self.api_parentCopyGlobals, path='/parent', name='copyGlobals')
      self._server.registerFunction(self.api_parentEval, path='/parent', name='eval')
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

   def sendRequest(self, path, method, params=[], notif=False):
      mytime=self._server._getms()
      if self._server._isArray(method): #always like notify-batch
         data=[{'jsonrpc': '2.0', 'method': v['method'], 'params':v['params']} for v in method]
      else:
         data={'jsonrpc': '2.0', 'method': method, 'params':params}
         if not notif: #like notif
            data['id']=int(random.random()*999999)
      try: data=self._server._serializeJSON(data) #IMPORTANT! _server, not _parentServer, or it will be cycled
      except Exception, e:
         self._parentServer._throw('Cant serialize JSON: %s'%(e))
      _conn=self._conn if self._conn is not None else UnixHTTPConnection(self.socketPath)
      for i in xrange(10):
         try:
            _conn.request('POST', path, data, {'Token':self.token})
            if self._conn is not None: self._conn=_conn
            break
         except Exception: pass
         self._parentServer._sleep(1)
         _conn=UnixHTTPConnection(self.socketPath)
      else: self._parentServer._throw('Cant connect to backend-API:'%self.socketPath)
      resp=_conn.getresponse()
      data2=resp.read()
      if notif or self._server._isArray(method): return
      data2=self._server._parseJSON(data2) #IMPORTANT! _server, not _parentServer, or it will be cycled
      if method!='speedStatsAdd':
         self._parentServer._speedStatsAdd(method, self._server._getms()-mytime)
      if not self._server._isDict(data2): return None
      elif data2.get('error', None):
         self._parentServer._throw('Error %s: %s'%(data2['error']['code'], data2['error']['message']))
      return data2.get('result', None)

   def childCicle(self, parentServer):
      self._server=flaskJSONRPCServer(['', ''], gevent=parentServer.setts.gevent) #we need this dummy for some methods from it
      self._parentServer=parentServer
      self._conn=None
      self._lazyRequest={}
      self._lazyRequestLatTime=None
      if not self.settings.allowThreads: parentServer.setts.gevent=False
      parentServer._importAll(forceDelete=True)
      if not self.settings.allowThreads: #! in gevent we can't use same socket for read and write
         self._conn=UnixHTTPConnection(self.socketPath)
      # overload some methods in parentServer
      parentServer.stats=lambda inMS=False: self.sendRequest('/parent', 'stats', [inMS])
      parentServer.lock=lambda dispatcher=None: self.sendRequest('/parent', 'lock', [(None if dispatcher is None else dispatcher._id)])
      parentServer.unlock=lambda dispatcher=None, exclusive=False: self.sendRequest('/parent', 'unlock', [(None if dispatcher is None else dispatcher._id), exclusive])
      parentServer.wait=self.childWait
      parentServer._speedStatsAdd=self.childSpeedStatsAdd
      self.childDisableNotImplemented()
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
         parentServer._sleep(self.settings.sleepTime_emptyQueue)

   def childSendLazyRequest(self):
      if self._lazyRequestLatTime is None: self._lazyRequestLatTime=self._server._getms()
      if self._lazyRequestLatTime is not True and self._server._getms()-self._lazyRequestLatTime<self.settings.sleepTime_lazyRequest: return
      for path, v in self._lazyRequest.items():
         if not len(v): continue
         self._lazyRequest[path]=v[self.settings.lazyRequestChunk:]
         self.sendRequest(path, v[:self.settings.lazyRequestChunk])
         if len(v)>self.settings.lazyRequestChunk:
            self._lazyRequestLatTime=True #shedule to next call
            return
      self._lazyRequestLatTime=self._server._getms()

   def childCallDispatcher(self, p):
      self._server._logger('Processing with backend "parallelWithSocket": %s()'%(p['dataIn']['method']))
      p['request']=magicDict(p['request']) # _callDispatcher() work with this like object, not dict
      status, params, result=self._parentServer._callDispatcher(p['path'], p['dataIn'], p['request'], overload=self.childConnectionOverload, nativeThread=self.settings.allowThreads and not(self._parentServer.setts.gevent), isJSONP=p.get('isJSONP', False))
      if not self.settings.saveResult: return
      self.sendRequest('/queue', 'result', [p['uniqueId'], status, params, result])

   def childWait(self, dispatcher=None, sleepMethod=None, returnStatus=False):
      # parentServer.wait() is more complicated, becose it must check lock-status in parent, but suspend child
      sleepMethod=sleepMethod or self._parentServer._sleep
      while self.sendRequest('/parent', 'wait', [(None if dispatcher is None else dispatcher._id)]):
         if returnStatus: return True
         sleepMethod(self.settings.sleepTime_waitLock)
      if returnStatus: return False

   def childSpeedStatsAdd(self, name, val):
      if '/parent' not in self._lazyRequest: self._lazyRequest['/parent']=[]
      self._lazyRequest['/parent'].append({'method':'speedStatsAdd', 'params':['execBackend_%s'%name, val]})

   def childConnectionOverload(self, _connection):
      # some overloads in _callDispatcher()._connection
      _connection['parallelType']='parallelWithSocket'
      _connection['parallelPoolSize']=self.settings.poolSize
      _connection['call']['eval']=lambda code, scope=None, async=False: self.sendRequest('/parent', 'eval', [code, scope, False], notif=async)
      _connection['call']['execute']=lambda code, scope=None, async=False: self.sendRequest('/parent', 'eval', [code, scope, True], notif=async)
      _connection['call']['copyGlobals']=lambda what=None: self.sendRequest('/parent', 'copyGlobals', [what])
      return _connection

   def childDisableNotImplemented(self):
      # disable none-implemented methods in parentServer
      whiteList=['_callDispatcher', '_checkFileDescriptor', '_compress', '_copyRequestContext', '_countFileDescriptor', '_fileGet', '_fileWrite', '_fixJSON', '_getErrorInfo', '_getms', '_import', '_importAll', '_importSocket', '_importThreading', '_isArray', '_isDict', '_isFunction', '_isInstance', '_isNum', '_isString', '_logger', '_parseJSON', '_serializeJSON', '_sha1', '_sha256', '_sleep', '_speedStatsAdd', '_strGet', '_thread', '_throw', '_tweakLimit', 'fixJSON', 'lock', 'stats', 'unlock', 'wait']
      for name in dir(self._parentServer):
         if not self._parentServer._isFunction(getattr(self._parentServer, name)): continue
         if name not in whiteList:
            s='Method "%s" not implemented in parallel backend'%(name)
            setattr(self._parentServer, name, lambda *args, **kwargs: self._parentServer._throw(s))

   def api_queueGet(self, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      # get task
      if self._forceStop: return '__stop__'
      elif not len(self.queue): return None
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
         self._parentServer._throw('Access denied') # tokens not match
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
         s=compile(code, '<string>', 'exec' if isExec else 'eval')
         res=eval(s, self.parentGlobals if scope is None else scope)
      except Exception, e:
         self._server._throw('Cant execute code: %s'%(e))
      return res

   def api_parentCopyGlobals(self, what=None, _connection=None):
      if _connection.headers.get('Token', '__2')!=getattr(self, 'token', '__1'):
         self._parentServer._throw('Access denied') # tokens not match
      scope={}
      typeOf=[IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, DictType, ListType, TupleType]
      self._parentServer._importGlobalsFromParent(scope=scope, typeOf=typeOf)
      if what is None: return scope
      else:
         what=what if self._server._isArray(what) else [what]
         return dict([(name, scope.get(name, None)) for name in what])

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
      elif not self._parentServer._isDict(dispatcherId) or 'path' not in dispatcherId or 'name' not in dispatcherId:
         self._parentServer._throw('Wrong dispatcherId: %s'%dispatcherId)
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
      self._parentServer._speedStatsAdd('execBackend_wait', self._parentServer._getms()-mytime)
      tArr=self.result[uniqueId]
      del self.result[uniqueId]
      return tArr[0], tArr[1], tArr[2] # status, params, result

   def stats(self, inMS=False):
      r={
         '%s_queue'%self._id:len(self.queue),
         '%s_api'%self._id:self._server.stats(inMS=inMS)
      }
      return r

# declaring map of exec-backends
execBackendMap={
   'parallelWithSocket':lambda notif: execBackend_parallelWithSocket(saveResult=not(notif)),
   'threaded':lambda notif: execBackend_threaded(),
   'threadedNative':lambda notif: execBackend_threaded(forceNative=True)
}
# backward compatible
execBackendMap['threadPool']=execBackendMap['threaded']
execBackendMap['threadPoolNative']=execBackendMap['threadedNative']

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
