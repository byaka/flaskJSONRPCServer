#!/usr/bin/env python
# -*- coding: utf-8 -*-

import httplib, sys, os, time, collections, random
from virtVar import virtVar
import gmultiprocessing

__all__=['PY_V', 'magicDict', 'magicDictCold', 'dict2magic', 'gmultiprocessing', 'virtVar', 'deque2', 'UnixHTTPConnection', 'console', 'prepDataForLogger', 'getms', 'randomEx', 'randomEx_default_soLong']
__all__+=['jsonBackendWrapper', 'filelikeWrapper']
__all__+=['isFunction', 'isInstance', 'isModule', 'isClass', 'isModuleBuiltin', 'isTuple', 'isArray', 'isDict', 'isString', 'isNum', 'isInt']

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

class magicDict(dict):
   """
   Get and set values like in Javascript (dict.<key>).
   """
   def __getattr__(self, k):
      if k[:2]=='__': raise AttributeError(k) #for support PICKLE protocol and correct isFunction() check
      return self.__getitem__(k)

   # __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__
   __reduce__=dict.__reduce__

class magicDictCold(magicDict):
   """
   Extended magicDict, that allow freezing.
   """
   def __getattr__(self, k):
      if k=='__frozen': return object.__getattribute__(self, '__frozen')
      return magicDict.__getattr__(self, k)

   def __freeze(self): object.__setattr__(self, '__frozen', True)

   def __unfreeze(self): object.__setattr__(self, '__frozen', False)

   def __setattr__(self, k, v):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      magicDict.__setattr__(self, k, v)

   def __setitem__(self, k, v):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      magicDict.__setitem__(self, k, v)

   def __delattr__(self, k):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      magicDict.__delattr__(self, k)

   def __delitem__(self, k):
      if getattr(self, '__frozen', None): raise RuntimeError('Frozen')
      magicDict.__delitem__(self, k)

def dict2magic(o, recursive=False):
   if recursive:
      if isArray(o):
         for i, _ in enumerate(o): o[i]=dict2magic(o[i], recursive=True)
      elif isDict(o):
         for i in o: o[i]=dict2magic(o[i], recursive=True)
         o=magicDict(o)
   elif isDict(o): o=magicDict(o)
   return o

consoleColor=magicDict({
   'header':'\033[95m',
   'okBlue':'\033[94m',
   'okGreen':'\033[92m',
   'ok':'\033[92m',
   'warning':'\033[93m',
   'fail':'\033[91m',
   'end':'\033[0m',
   'bold':'\033[1m',
   'underline':'\033[4m',
   'clearLast':'\033[F\033[K'
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

global console
console=magicDict({
   'clear':consoleClear,
   'inTerm':consoleIsTerminal,
   'color':consoleColor
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
   s=pref+str(int(random.random()*mult))+suf
   while(s in vals):
      s=pref+str(int(random.random()*mult))+suf
      # defence frome freeze
      if (getms()-mytime)/1000.0>soLong:
         mytime=getms()
         if isFunction(cbSoLong):
            mult=cbSoLong(mult, vals, pref, suf)
            if mult is not None: continue
         return None
   return s

#========================================
import decimal
from types import InstanceType, ModuleType, ClassType, TypeType

def isFunction(o): return hasattr(o, '__call__')

def isInstance(o): return isinstance(o, (InstanceType))

def isClass(o): return isinstance(o, (type, ClassType, TypeType))

def isModule(o): return isinstance(o, (ModuleType))

def isModuleBuiltin(o): return isModule(o) and getattr(o, '__name__', '') in sys.builtin_module_names

def isTuple(o): return isinstance(o, (tuple))

def isArray(o): return isinstance(o, (list))

def isDict(o): return isinstance(o, (dict))

def isString(o): return isinstance(o, (str, unicode))

def isNum(var):
   return (var is not True) and (var is not False) and isinstance(var, (int, float, long, complex, decimal.Decimal))

def isInt(var):
   return (var is not True) and (var is not False) and isinstance(var, int)
#========================================

if __name__=='__main__':
   d=magicDictCold()
   d['test1']='1'
   d.test2='2'
   print '~', d.keys(), d.test1, d.test2, d['test1'], d['test2']

   d._magicDictCold__freeze()
   try: d['test22']=22
   except RuntimeError: print 'Forzen!'
   try: d.test11=11
   except RuntimeError: print 'Forzen!'
   try: del d['test2']
   except RuntimeError: print 'Forzen!'
   try: del d.test1
   except RuntimeError: print 'Forzen!'
   print '~', d.keys(), d.test1, d.test2, d['test1'], d['test2']

   d._magicDictCold__unfreeze()
   try: d['test22']=22
   except RuntimeError: print 'Forzen!'
   try: d.test11=11
   except RuntimeError: print 'Forzen!'
   try: del d['test2']
   except RuntimeError: print 'Forzen!'
   try: del d.test1
   except RuntimeError: print 'Forzen!'
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
