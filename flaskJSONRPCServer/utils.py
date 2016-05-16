#!/usr/bin/env python
# -*- coding: utf-8 -*-

import httplib
from virtVar import virtVar
import gmultiprocessing
import collections

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

if __name__=='__main__':
   v1=virtVar('test')
   v2=virtVar(0.3)
   v3=virtVar(['test1', 'test2', 'test3', 'test4'])
   print '+'*30
   print v1, v2, v3
   print repr(v1), repr(v2), repr(v3)
   print v3[1:3]
   print v2+1, v2-1, v2*1, v2/1
