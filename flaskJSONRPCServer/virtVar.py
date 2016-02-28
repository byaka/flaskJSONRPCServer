#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Обертка над стандартными типами данных.
Обертка отслеживает обращение к себе, и позволяет навесить колбек на него. Внутри колбека можно менять поведение обращения к переменной. За счет этого возможно реализовать меж-процессный или меж-серверный доступ к данным.
"""

from types import InstanceType, IntType, FloatType, LongType, ComplexType, NoneType, UnicodeType, StringType, BooleanType, LambdaType, DictType, ListType, TupleType, ModuleType, FunctionType

class virtVar(object):
   def __init__(self, obj, saveObj=True, cbGet=None, cbSet=None, cbDel=None):
      self._inited=False
      self._setts={'saveObj':saveObj}
      self._getattr_blacklist=['_setts', '_inited', '_cb']
      self._cb=magicDict({'get':cbGet, 'set':cbSet, 'del':cbDel})
      # self._cbGet=cbGet
      # self._cbSet=cbSet
      # self._cbDel=cbDel
      if saveObj:
         self._type=type(obj)
         self._val=obj
         if not self._cb.get: self._getattr_blacklist+=['_val', '_type']
      #! нужно рекурсивно поменять тип всех детей
      self._inited=True

   # вызывается, только если атрибут не найден
   # def __getattr__(self, key):
   #    print '!! getattr', key
   #    if self._cb.get: return self._cb.get(self, key)

   # вызываются при любом обращении к атрибутам класса
   def __setattr__(self, key, val):
      #кешируем системные атрибуты, а также обеспечиваем к ним быстрый доступ без дополнительных проверок
      _cache={}
      for k in ['_inited', '_getattr_blacklist', '_cb']:
         try: s=object.__getattribute__(self, k)
         except AttributeError: s=None
         if key==k:
            return object.__setattr__(self, key, val)
         else: _cache[k]=s
      #full checking
      print '!! setattr', key, val
      if not(_cache['_inited']) or (key in _cache['_whitemap']):
         #обьект еще не инициирован до конца, или атрибут занесен в черный лист
         return object.__setattr__(self, key, val)
      elif _cache['_cb'].set:
         return _cache['_cb'].set(self, key, val)
      else:
         #! нет коллбека, что делать в данной ситуации?
         pass

   def __delattr__(self, key):
      try: _inited=object.__getattribute__(self, '_inited')
      except AttributeError: _inited=False
      try: _whitemap=object.__getattribute__(self, '_getattr_blacklist')
      except AttributeError: _whitemap=[]
      if not(_inited) or (key in _whitemap):
         object.__delattr__(self, key)
         return
      print '!! detattr', key
      if self._cbDel: return self._cbDel(self, key)

   def __getattribute__(self, key):
      """вызывается при любом обращении к атрибутам"""
      #кешируем системные атрибуты, а также обеспечиваем к ним быстрый доступ без дополнительных проверок
      _cache={}
      for k in ['_inited', '_getattr_blacklist', '_cb']:
         try: s=object.__getattribute__(self, k)
         except AttributeError: s=None
         if key==k: return s
         else: _cache[k]=s
      #full checking
      if not(_cache['_inited']) or (key in _cache['_blacklist']):
         #обьект еще не инициирован до конца, или атрибут занесен в черный лист
         return object.__getattribute__(self, key)
      elif _cache['_cb'].get:
         #указан коллбек для обращения к атрибутам
         return _cache['_cb'].get(self, key)
      else:
         #! нет коллбека, что делать в данной ситуации?
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
   pass