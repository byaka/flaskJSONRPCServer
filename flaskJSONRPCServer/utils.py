#!/usr/bin/env python
# -*- coding: utf-8 -*-

import httplib, sys, os, time, collections, random, inspect, traceback, code
from virtVar import virtVar
import gmultiprocessing

__all__=['PY_V', 'magicDict', 'magicDictCold', 'MagicDict', 'MagicDictCold', 'dict2magic', 'gmultiprocessing', 'rpcSender', 'virtVar', 'deque2', 'UnixHTTPConnection', 'console', 'prepDataForLogger', 'getms', 'randomEx', 'randomEx_default_soLong', 'strGet', 'getScriptName', 'getScriptPath', 'checkPath', 'getErrorInfo', 'formatPath', 'calcMimeType', 'bind']
__all__+=['jsonBackendWrapper', 'filelikeWrapper']
__all__+=['isGen', 'isGenerator', 'isFunc', 'isFunction', 'isIter', 'isIterable', 'isClass', 'isInstance', 'isModule', 'isModuleBuiltin', 'isString', 'isStr', 'isBool', 'isNum', 'isFloat', 'isInt', 'isArray', 'isList', 'isTuple', 'isDict', 'isObject', 'isSet']

global PY_V
PY_V=float(sys.version[:3])

if PY_V<2.7:
   class deque2(collections.deque):
      """
      This class add support of <maxlen> for old deque in python2.6.
      Thx to Muhammad Alkarouri.
      http://stackoverflow.com/a/4020363
      """
      def __init__(self, iterable=(), maxlen=None):
         collections.deque.__init__(self, iterable, maxlen)
         self._maxlen=maxlen

      @property
      def maxlen(self):
         return self._maxlen
else:
   deque2=collections.deque

class UnixHTTPConnection(httplib.HTTPConnection):
   """
   This class adds support for unix-domain sockets to Python's httplib package.
   Thx to Erik van Zijst.
   https://bitbucket.org/evzijst/uhttplib/overview
   """
   def __init__(self, path, strict=None, timeout=None, socketClass=None):
      httplib.HTTPConnection.__init__(self, 'localhost', strict=strict, timeout=timeout)
      self.path=path
      if socketClass: self.socketClass=socketClass
      else:
         import socket
         self.socketClass=socket

   def connect(self):
      sock=self.socketClass.socket(self.socketClass.AF_UNIX, self.socketClass.SOCK_STREAM)
      sock.connect(self.path)
      self.sock=sock

class rpcSender(object):

   def __init__(self, server, constructRequest=None, parseResponse=None, compress=None, compressMinSize=300*1024, uncompress=None, uncompressHeader=None, updateHeaders=None, sendRequest=None, keepSocketClass=True, protocolDefault='tcp'):
      self._server=server
      self._constructRequest=constructRequest or self.__constructRequest_jsonrpc
      self._parseResponse=parseResponse or self.__parseResponse_jsonrpc
      self._compress=False if compress is False else (compress or self.__compressRequest_gzip)
      self._uncompress=False if uncompress is False else (uncompress or self.__uncompressResponse_gzip)
      self._uncompressHeader=False if uncompressHeader is False else (uncompressHeader or {'Accept-Encoding':'gzip'})
      self._updateHeaders=updateHeaders
      self._sendRequest=sendRequest or self.__sendRequest_rpcHttpPost
      self.settings={
         'compressMinSize':compressMinSize,
         'connectionAttemptLimit':10,
         'connectionAttemptSleepTime':1,
         'addSpeedStats':True,
         'protocolDefault':protocolDefault,
         'timeout':300,
         'redirectErrorsToLog':1,  # set log-level for errors
      }
      self._sockClass=self._server._socketClass() if keepSocketClass else None

   # def _error(self, data):
   #    if isFunction(self.settings['redirectErrorsToLog']):
   #       self.settings['redirectErrorsToLog'](data)
   #    elif self.settings['redirectErrorsToLog'] is not False:
   #       self._server._logger((self.settings['redirectErrorsToLog'] if isInt(self.settings['redirectErrorsToLog']) else 1), data)
   #    else:
   #       self._server._throw(data)

   def __constructRequest_jsonrpc(self, stack):
      oneRequest=True
      waitResults={}
      dataRaw=[]
      if isinstance(stack, (tuple, list)) and len(stack):
         if not isinstance(stack[0], (tuple, list)): stack=(stack, )
         else: oneRequest=False
         for i, s in enumerate(stack):
            if len(s)==3 and s[2]:
               dataRaw.append({'jsonrpc': '2.0', 'method': s[0], 'params':s[1]})
            else:
               rid=randomEx(vals=waitResults)
               waitResults[rid]=i
               dataRaw.append({'jsonrpc': '2.0', 'method': s[0], 'params':s[1], 'id':rid})
         if oneRequest: dataRaw=dataRaw[0]
      else:
         self._server._throw('Incorrect <stack> format for <rpcSender>')
      try:
         data=self._server._serializeJSON(dataRaw)
      except Exception, e:
         self._server._throw('<rpcSender> cant serialize JSON: %s'%(e))
      return data, dataRaw, oneRequest, waitResults

   def __parseResponse_jsonrpc(self, data):
      try:
         data=self._server._parseJSON(data)
      except Exception, e:
         self._server._throw('<rpcSender> cant parse JSON: %s'%(e))
      return data

   def __compressRequest_gzip(self, data, headers):
      if sys.getsizeof(data)>=self.settings['compressMinSize']:
         data=self._server._compressGZIP(data)
         headers['Content-Encoding']='gzip'
      return data

   def __uncompressResponse_gzip(self, data, headers):
      if headers.get('content-encoding', None)=='gzip':
         try:
            data=self._server._uncompressGZIP(data)
         except Exception, e:
            self._server._throw('<rpcSender> cant uncompress data: %s'%(e))
      return data

   def __selectProtocol_rpcHttp(self, p, api, sockClass):
      if p=='uds':
         return UnixHTTPConnection(api, timeout=self.settings['timeout'], socketClass=sockClass)
      elif p=='tcp':
         return httplib.HTTPConnection(api, timeout=self.settings['timeout'])
      else:
         self._server._throw('<rpcSender> dont know this protocol "%s"'%(p))

   def __extractProtocol_rpcHttp(self, api):
      p=self.settings['protocolDefault']
      if '@' in api:
         tArr=api.split('@', 1)
         api=tArr[0]
         if len(tArr)==2 and tArr[1]: p=tArr[1]
      return p, api

   def __sendRequest_rpcHttpPost(self, api, path, data, headers):
      sockClass=self._sockClass or self._server._socketClass()
      protocol, api=self.__extractProtocol_rpcHttp(api)
      conn=None
      err=None
      i=0
      while True:
         if self.settings['connectionAttemptLimit'] and i>=self.settings['connectionAttemptLimit']:
            self._server._throw('<rpcSender> cant connect to API "%s": %s'%(api, err))
         try:
            conn=self.__selectProtocol_rpcHttp(protocol, api, sockClass)
            conn.request('POST', path, data, headers)
            break
         except Exception:
            err=getErrorInfo()
            if self.settings['connectionAttemptSleepTime']:
               self._server._sleep(self.settings['connectionAttemptSleepTime'])
         i+=1
      resp=conn.getresponse()
      data=resp.read()
      # construct headers
      headersOut={}
      for k, v in resp.getheaders():
         k=k.lower()
         if k in headersOut:
            vOld=headersOut[k]
            if isArray(vOld): vOld.append(v)
            else: headersOut[k]=[vOld, v]
         else: headersOut[k]=v
      return data, headersOut

   def __call__(self, api, path, stack):
      mytime=getms()
      # prepare request
      data, dataRaw, oneRequest, waitResults=self._constructRequest(stack)
      headers={}
      if self._updateHeaders:
         self._updateHeaders(headers)
      if self._uncompressHeader:
         headers.update(self._uncompressHeader)
      if self._compress:
         data=self._compress(data, headers)
      # send request and recive response
      data, headersOut=self._sendRequest(api, path, data, headers)
      if not waitResults:
         if self.settings['addSpeedStats']:
            if oneRequest and dataRaw['method']!='speedStatsAdd':
               self._server._speedStatsAdd('remote-'+dataRaw['method'], getms()-mytime)
            #! пока неподдерживается запись статистики для мульти-запросов
         return
      # decoding
      if self._uncompress:
         data=self._uncompress(data, headersOut)
      data=self._parseResponse(data)
      # return results
      if self.settings['addSpeedStats']:
         if oneRequest and dataRaw['method']!='speedStatsAdd':
            self._server._speedStatsAdd('remote-'+dataRaw['method'], getms()-mytime)
         #! пока неподдерживается запись статистики для мульти-запросов
      if oneRequest:
         if 'error' in data:
            self._server._throw('Error %s: %s'%(data['error']['code'], data['error']['message']))
         else:
            return data['result']
      else:
         results=range(len(waitResults))
         for d in data:
            if 'error' in d:
               self._server._throw('Error %s: %s'%(d['error']['code'], d['error']['message']))
            else:
               results[waitResults[d['id']]]=d['result']
         return results

   def ex(self, api, path, stack, cb=None, cbData=None, redirectErrorsToLog=None):
      """
      Расширенная обертка над обычным rpc вызовом.

      Поддерживает мульти-запросы сразу на несколько серверов, вызывает их в отдельных потоках (гринлетах).
      Если <cb> задан, он будет вызван для каждого запроса по завершении. Формат вызова (currentApi, result, error, <cbData>). Можно задать <cb> равным False, тогда он вызван не будет. Управление родительскому потоку передастся сразу, без ожидания завершения.
      В противном случае произойдет ожидание выполнения всех запросов и их результаты вернутся в виде массива.
      """
      if redirectErrorsToLog is None:
         redirectErrorsToLog=self.settings['redirectErrorsToLog']
      oneRequest=not isinstance(api, (tuple, list))
      api=api if not oneRequest else (api,)
      _callAsync=self._server.callAsync
      _sleep=self._server._sleep
      _sendRequest=self.__call__
      if not cb and cb is not False:
         # start all requests and get checkers
         res=range(len(api))
         checkerMap=[]
         for i, apiOne in enumerate(api):
            checkerMap.append((i, _callAsync(_sendRequest, args=(apiOne, path, stack), forceNative=False, returnChecker=True, wait=False)))
         # now waiting for completion
         c=len(res)
         while c>0:
            for i, checker in checkerMap:
               _sleep(0.01)
               s, r, e=checker()
               if not s: continue
               if e: self._server._throw(e)  #! при ошибке последующие ответы теряются
               c-=1
               res[i]=r
         return res[0] if oneRequest else res
      else:
         # start all requests and pass cb
         if cb:
            def tFunc_cb(res, err, p):
               p[0](p[1], res, err, p[2])
         else:
            tFunc_cb=None
         for apiOne in api:
            _callAsync(_sendRequest, args=(apiOne, path, stack), forceNative=False, wait=False, cb=tFunc_cb, cbData=(cb, apiOne, cbData), redirectErrorsToLog=redirectErrorsToLog)

class jsonBackendWrapper(object):
   """
   Class for wrapping new json-backend. Faster than magicDict.
   """
   if PY_V<2.7:
      # by some unknown reason, in python>2.6 slots slightly slower
      __slots__=('dumps', 'loads')

   def __init__(self, dumps, loads):
      self.dumps=dumps
      self.loads=loads

class filelikeWrapper(object):
   """
   Class for wrapping function to file-like object (used by flaskJSONRPCServer.postprocess.postprocessWsgi).
   """
   if PY_V<2.7:
      # by some unknown reason, in python>2.6 slots slightly slower
      __slots__=('read', 'readable', 'readline')

   def __init__(self, read):
      self.read=read

   def readable(self):
      return True

   def readline(self):
      return self.read()

class MagicDict(dict):
   """
   Get and set values like in Javascript (dict.<key>).
   """
   def __getattr__(self, k):
      if k[:2]=='__': raise AttributeError(k)  #for support PICKLE protocol and correct isFunction() check
      return self.__getitem__(k)

   # __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__
   __reduce__=dict.__reduce__
magicDict=MagicDict

class MagicDictCold(MagicDict):
   """
   Extended MagicDict, that allow freezing.
   """
   def __getattr__(self, k):
      if k=='__frozen': return object.__getattribute__(self, '__frozen')
      return MagicDict.__getattr__(self, k)

   def __freeze(self):
      object.__setattr__(self, '__frozen', True)

   def __unfreeze(self):
      object.__setattr__(self, '__frozen', False)

   def __setattr__(self, k, v):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      MagicDict.__setattr__(self, k, v)

   def __setitem__(self, k, v):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      MagicDict.__setitem__(self, k, v)

   def __delattr__(self, k):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      MagicDict.__delattr__(self, k)

   def __delitem__(self, k):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      MagicDict.__delitem__(self, k)
magicDictCold=MagicDictCold

def dict2magic(o, recursive=False):
   if recursive:
      if isArray(o) or isDict(o) or isSet(o) or isTuple(o):
         for i in (o if isDict(o) else xrange(len(o))):
            o[i]=dict2magic(o[i], recursive=True)
         if isDict(o): o=MagicDict(o)
   elif isDict(o):
      o=MagicDict(o)
   return o

def bind(f, defaultsUpdate=None, globalsUpdate=None, name=None):
   """
   Returns new function, similar as <f>, but with redefined default keyword-arguments values and updated globals.

   It have similar use-cases like `functools.partial()`, but executing few times faster (with cost of longer initialisation) and also faster than original function, if you pass alot args.

   :param func f:
   :param str name:
   :param dict globalsUpdate: Update global-env for new function, but only for this function, so not modify real globals
   :param dict defaultsUpdate: Update default keyword-arguments
   """
   p={
      'name':name or f.func_name+'_BINDED',
      'code':f.func_code,
      'globals':f.func_globals,
      'argdefs':f.func_defaults,
      'closure':f.func_closure
   }
   if globalsUpdate:
      p['globals']=p['globals'].copy()
      p['globals'].update(globalsUpdate)
   if defaultsUpdate:
      _args=inspect.getargs(f.func_code)[0]
      _defsL=len(p['argdefs'])
      _offset=len(_args)-_defsL
      p['argdefs']=list(p['argdefs'])
      for i in xrange(_defsL):
         k=_args[i+_offset]
         if k in defaultsUpdate:
            p['argdefs'][i]=defaultsUpdate[k]
      p['argdefs']=tuple(p['argdefs'])
   f2=types.FunctionType(**p)
   f2.__dict__=f.__dict__
   f2.__module__=f.__module__
   f2.__doc__=f.__doc__
   if isinstance(f, types.MethodType):
      f2=types.MethodType(f2, f.im_self, f.im_class)
   return f2

consoleColor=magicDict({
   # predefined colors
   'fail':'\x1b[91m',
   'ok':'\x1b[92m',
   'warning':'\x1b[93m',
   'okblue':'\x1b[94m',
   'header':'\x1b[95m',
   # colors
   'black':'\x1b[30m',
   'red':'\x1b[31m',
   'green':'\x1b[32m',
   'yellow':'\x1b[33m',
   'blue':'\x1b[34m',
   'magenta':'\x1b[35m',
   'cyan':'\x1b[36m',
   'white':'\x1b[37m',
   # background colors
   'bgblack':'\x1b[40m',
   'bgred':'\x1b[41m',
   'bggreen':'\x1b[42m',
   'bgyellow':'\x1b[43m',
   'bgblue':'\x1b[44m',
   'bgmagenta':'\x1b[45m',
   'bgcyan':'\x1b[46m',
   'bgwhite':'\x1b[47m',
   # specials
   'light':'\x1b[2m',
   'bold':'\x1b[1m',
   'underline':'\x1b[4m',
   'clearLast':'\x1b[F\x1b[K',
   'end':'\x1b[0m'
})

def consoleClear():
   """
   Clear console outpur (linux,windows)
   """
   if sys.platform=='win32': os.system('cls')
   else: os.system('clear')

def consoleIsTerminal():
   """
   Check, is program runned in terminal or not.
   """
   return sys.stdout.isatty()

def consoleSize():
   if not sys.stdout.isatty():
      return INFINITY, INFINITY
   import fcntl, termios, struct
   h, w, hp, wp=struct.unpack('HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0)))
   return w, h

def consoleRepair():
   # https://stackoverflow.com/a/24780259/5360266
   os.system('stty sane')

def consoleInteract(local=None, msg=None):
   local=(local or {}).copy()
   def tFunc():
      raise SystemExit
   local['exit']=tFunc
   try:
      if msg is None:
         msg='-'*50
         msg+='\nInteractive session, for return back use `exit()`'
      code.interact(banner=msg, local=local)
   except SystemExit: pass

global console
console=magicDict({
   'interact':consoleInteract,
   'clear':consoleClear,
   'inTerm':consoleIsTerminal,
   'color':consoleColor,
   'repair':consoleRepair,
   'size':consoleSize,
   'width':lambda: consoleSize()[0],
   'height':lambda: consoleSize()[1],
})

def getms(inMS=True):
   """
   This method return curent(unix timestamp) time in millisecond or second.

   :param bool inMS: If True in millisecond, else in seconds.
   :retrun int:
   """
   if inMS: return time.time()*1000.0
   else: return int(time.time())

def prepDataForLogger(level, args):
   """
   This method convert <args> to list and also implements fallback for messages without <level>.
   """
   if not isNum(level): # fallback
      if args:
         args=list(args)
         if level is not None: args.insert(0, level)
      else: args=[level] if level is not None else []
      level=None
   if not args: args=[]
   elif not isArray(args): args=list(args)
   return level, args

def randomEx_default_soLong(mult, vals, pref, suf):
   print 'randomEx: generating value so long for (%s, %s, %s)'%(pref, mult, suf)
   if randomEx_default_soLong.sleepMethod:
      randomEx_default_soLong.sleepMethod(0.1)
   return mult*2
randomEx_default_soLong.sleepMethod=None

def randomEx(mult=None, vals=None, pref='', suf='', soLong=0.1, cbSoLong=None):
   """
   This method generate random value from 0 to <mult> and add prefix and suffix.
   Also has protection against the repeating values and against recurrence (long generation).

   :param int|None mult: If None, 'sys.maxint' will be used.
   :param list|dict|str vals: Blacklist of generated data.
   :param str pref: Prefix.
   :param str suf: Suffix.
   :param int soLong: Max time in seconds for generating.
   :param func cbSoLong: This function will called if generating so long. It can return new <mult>. If return None, generating will be aborted.
   :return str: None if some problems or aborted.
   """
   mult=mult or sys.maxint
   mytime=getms()
   if cbSoLong is None:
      cbSoLong=randomEx_default_soLong
   vals=vals or tuple()
   s=None
   toStr=isString(pref) and isString(suf)
   while not s or s in vals:
      s=int(random.random()*mult)
      if toStr:
         s=pref+str(s)+suf
      # defence frome freeze
      if (getms()-mytime)/1000.0>soLong:
         mytime=getms()
         if isFunction(cbSoLong):
            mult=cbSoLong(mult, vals, pref, suf)
            if mult is not None: continue
         return None
   return s

def strGet(text, pref='', suf='', index=0, default=None):
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

def getScriptPath(full=False, real=True, f=None):
   """
   This method return path of current script. If <full> is False return only path, else return path and file name.

   :param bool full:
   :return str:
   """
   f=f or sys.argv[0]
   if full:
      return os.path.realpath(f) if real else f
   else:
      return os.path.dirname(os.path.realpath(f) if real else f)

def getScriptName(withExt=False, f=None):
   """
   This method return name of current script. If <withExt> is True return name with extention.

   :param bool withExt:
   :return str:
   """
   f=f or sys.argv[0]
   if withExt:
      return os.path.basename(f)
   else:
      return os.path.splitext(os.path.basename(f))[0]

def checkPath(s):
   """
   This method try to validate given path in filesystem.
   """
   #! need more complicated realisation, see http://stackoverflow.com/a/34102855
   try:
      f=open(s, 'w')
      f.close()
      return True
   except Exception, e:
      return False

def getErrorInfo():
   """
   This method return info about last exception.

   :return str:
   """
   return traceback.format_exc()

   tArr=inspect.trace()[-1]
   fileName=tArr[1]
   lineNo=tArr[2]
   exc_obj=sys.exc_info()[1]
   s='%s:%s > %s'%(fileName, lineNo, exc_obj)
   sys.exc_clear()
   return s

def formatPath(path=''):
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

def calcMimeType(request):
   """
   This method generate mime-type of response by given <request>.

   :param dict request:
   :return str:
   """
   return 'text/javascript' if request['method']=='GET' else 'application/json'

#========================================
import decimal, types, collections

def isGenerator(var):
   return isinstance(var, (types.GeneratorType))
isGen=isGenerator

def isFunction(var):
   return hasattr(var, '__call__')
isFunc=isFunction

def isIterable(var):
   return isinstance(var, collections.Iterable)
isIter=isIterable

def isClass(var):
   return isinstance(var, (type, types.ClassType, types.TypeType))

def isInstance(var):
   #! work only with old-styled classes
   return isinstance(var, (types.InstanceType))

def isModule(var):
   return isinstance(var, (types.ModuleType))

def isModuleBuiltin(var):
   return isModule(var) and getattr(var, '__name__', '') in sys.builtin_module_names

def isString(var):
   return isinstance(var, (str, unicode))
isStr=isString

def isBool(var):
   return isinstance(var, (bool))

def isNum(var):
   return (var is not True) and (var is not False) and isinstance(var, (int, float, long, complex, decimal.Decimal))

def isFloat(var):
   return isinstance(var, (float, decimal.Decimal))

def isInt(var):
   return (var is not True) and (var is not False) and isinstance(var, int)

def isList(var):
   return isinstance(var, (list))
isArray=isList

def isTuple(var):
   return isinstance(var, (tuple))

def isDict(var):
   return isinstance(var, (dict))
isObject=isDict

def isSet(var):
   return isinstance(var, (set))
#========================================

if __name__=='__main__':
   d=magicDictCold()
   d['test1']='1'
   d.test2='2'
   print '~', d.keys(), d.test1, d.test2, d['test1'], d['test2']

   d._magicDictCold__freeze()
   try: d['test22']=22
   except RuntimeError: print 'Frozen!'
   try: d.test11=11
   except RuntimeError: print 'Frozen!'
   try: del d['test2']
   except RuntimeError: print 'Frozen!'
   try: del d.test1
   except RuntimeError: print 'Frozen!'
   print '~', d.keys(), d.test1, d.test2, d['test1'], d['test2']

   d._magicDictCold__unfreeze()
   try: d['test22']=22
   except RuntimeError: print 'Frozen!'
   try: d.test11=11
   except RuntimeError: print 'Frozen!'
   try: del d['test2']
   except RuntimeError: print 'Frozen!'
   try: del d.test1
   except RuntimeError: print 'Frozen!'
   print '~', d.keys(), d.test11, d.test22, d['test11'], d['test22']
   sys.exit(0)

   v1=virtVar('test')
   v2=virtVar(0.3)
   v3=virtVar(['test1', 'test2', 'test3', 'test4'])
   print '+'*30
   print v1, v2, v3
   print repr(v1), repr(v2), repr(v3)
   print v3[1:3]
   print v2+1, v2-1, v2*1, v2/1
