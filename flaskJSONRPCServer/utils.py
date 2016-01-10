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
