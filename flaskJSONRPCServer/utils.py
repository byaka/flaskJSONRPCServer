#!/usr/bin/env python
# -*- coding: utf-8 -*-

import httplib

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
   def __getattr__(self, attr):
      if attr[:2]=='__': raise AttributeError #for support PICKLE protocol and correct _isFunction() check
      return self.get(attr, None)
   # __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__
   __reduce__=dict.__reduce__

from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType
class virtVar(object):
   def __init__(self, obj, saveObj=True, cbGet=None, cbSet=None, cbDel=None):
      self._inited=False
      self._setts={'saveObj':saveObj}
      self._getattrWhitemap=['_setts', '_inited', '_cbGet', '_cbSet', '_cbDel']
      self._cbGet=cbGet
      self._cbSet=cbSet
      self._cbDel=cbDel
      if saveObj:
         self._type=type(obj)
         self._val=obj
         if not self._cbGet: self._getattrWhitemap+=['_val', '_type']
      #! нужно рекурсивно поменять тип всех детей
      self._inited=True

   # вызывается, только если атрибут не найден
   # def __getattr__(self, key):
   #    print '!! getattr', key
   #    if self._cbGet: return self._cbGet(self, key)

   # вызываются при любом обращении к атрибутам класса
   def __setattr__(self, key, val):
      try: _inited=object.__getattribute__(self, '_inited')
      except AttributeError: _inited=False
      try: _whitemap=object.__getattribute__(self, '_getattrWhitemap')
      except AttributeError: _whitemap=[]
      if not(_inited) or (key in _whitemap):
         object.__setattr__(self, key, val)
         return
      print '!! setattr', key, val
      if self._cbSet: return self._cbSet(self, key, val)

   def __delattr__(self, key):
      try: _inited=object.__getattribute__(self, '_inited')
      except AttributeError: _inited=False
      try: _whitemap=object.__getattribute__(self, '_getattrWhitemap')
      except AttributeError: _whitemap=[]
      if not(_inited) or (key in _whitemap):
         object.__delattr__(self, key)
         return
      print '!! detattr', key
      if self._cbDel: return self._cbDel(self, key)

   def __getattribute__(self, key):
      #get vars
      try: _inited=object.__getattribute__(self, '_inited')
      except AttributeError: _inited=False
      if key=='_inited': return _inited #for fast access
      _whitemap=object.__getattribute__(self, '_getattrWhitemap')
      if key=='_getattrWhitemap': return _whitemap #for fast access
      _cbGet=object.__getattribute__(self, '_cbGet')
      if key=='_cbGet': return _cbGet #for fast access
      #full checking
      if not(_inited) or (key in _whitemap):
         return object.__getattribute__(self, key)
      elif _cbGet:
         return _cbGet(self, key)
      else:
         print '!! getattribute', key

   def __getitem__(self, key):
      return self._val[key]

   def __setitem__(self, key, val):
      self._val[key]=val

   def __delitem__(self, key):
      del self._val[key]

   def __iter__(self):
      return self._val.__iter__()

   def __reversed__(self):
      return self._val.__reversed__()

   def __contains__(self, item):
      return self._val.__contains__(item)

   def __repr__(self):
      return 'myVar(%s)'%repr(self._val)

   def __str__(self):
      return str(self._val)

   def __len__(self):
      return len(self._val)

   #== eq methods
   def __lt__(self, other): # <
      return self._val<other
   def __le__(self, other): # <=
      return self._val<=other
   def __eq__(self, other): # ==
      return self._va==other
   def __ne__(self, other): # !=
      return self._val!=other
   def __gt__(self, other): # >
      return self._val>other
   def __ge__(self, other): # >=
      return self._val>=other
   def __hash__(self):
      return self._val.__hash__()
   def __nonzero__(self):
      return not(not(self._val))

   #==numeric methods
   def __add__(self, other):
      return self._val.__add__(other)
   def __sub__(self, other):
      return self._val.__sub__(other)
   def __truediv__(self, other):
      return self._val.__truediv__(other)
   def __div__(self, other):
      return self._val.__div__(other)
   def __mul__(self, other):
      return self._val.__mul__(other)
   def __floordiv__(self, other):
      return self._val.__floordiv__(other)
   def __mod__(self, other):
      return self._val.__mod__(other)
   def __divmod__(self, other):
      return self._val.__divmod__(other)
   def __pow__(self, other, modulo=None):
      return self._val.__pow__(other, modulo)
   def __lshift__(self, other):
      return self._val.__lshift__(other)
   def __rshift__(self, other):
      return self._val.__rshift__(other)
   def __and__(self, other):
      return self._val.__and__(other)
   def __xor__(self, other):
      return self._val.__xor__(other)
   def __or__(self, other):
      return self._val.__or__(other)

   #==numeric in-place methods
   def __iadd__(self, other):
      self._val=self._val.__add__(other)
      return self
   def __isub__(self, other):
      self._val=self._val.__sub__(other)
      return self
   def __itruediv__(self, other):
      self._val=self._val.__truediv__(other)
      return self
   def __idiv__(self, other):
      self._val=self._val.__div__(other)
      return self
   def __imul__(self, other):
      self._val=self._val.__mul__(other)
      return self
   def __ifloordiv__(self, other):
      self._val=self._val.__floordiv__(other)
      return self
   def __imod__(self, other):
      self._val=self._val.__mod__(other)
      return self
   def __ipow__(self, other, modulo=None):
      self._val=self._val.__pow__(other, modulo)
      return self
   def __ilshift__(self, other):
      self._val=self._val.__lshift__(other)
      return self
   def __irshift__(self, other):
      self._val=self._val.__rshift__(other)
      return self
   def __iand__(self, other):
      self._val=self._val.__and__(other)
      return self
   def __ixor__(self, other):
      self._val=self._val.__xor__(other)
      return self
   def __ior__(self, other):
      self._val=self._val.__or__(other)
      return self

   #==numeric unary methods
   # def __neg__(self):
   #    return self._val.__()
   # def __pos__(self):
   #    return self._val.__()
   # def __abs__(self):
   #    return self._val.__()
   # def __invert__(self):
   #    return self._val.__()

if __name__=='__main__':
   v1=virtVar('test')
   v2=virtVar(0.3)
   v3=virtVar(['test1', 'test2', 'test3', 'test4'])
   print '+'*30
   print v1, v2, v3
   print repr(v1), repr(v2), repr(v3)
   print v3[1:3]
   print v2+1, v2-1, v2*1, v2/1
