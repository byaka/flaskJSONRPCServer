#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains dispatcher-execution backend for flaskJSONRPCServer, that use threads (native or greenlets).

"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from utils import *
else:
   import sys, os
   from ..utils import *

class execBackend:
   """
   :param str id:
   :param bool forceNative:
   :param bool saveResult:
   :param float|False sleepBeforeExecute:
   """

   def __init__(self, id='execBackend_threaded', forceNative=False, saveResult=True, sleepBeforeExecute=0.001):
      self.settings={
         'forceNative':forceNative,
         'saveResult':saveResult,
         'sleepBeforeExecute':sleepBeforeExecute
      }
      self._id=id
      if forceNative: self._id+='Native'

   def start(self, server):
      if self.settings['forceNative'] and server.setts.gevent:
         server._logger(2, 'NotifBackend forced to use Native Threads')
      self._parentServer=server

   def childExecute(self, uniqueId, data, request, isJSONP, forceNative=False):
      s=self.settings['sleepBeforeExecute']
      if isNum(s):  #sleep thread for allowing server to send responce
         self._parentServer._sleep(s, forceNative=forceNative)
      status, params, result=self._parentServer._callDispatcher(uniqueId, data, request, isJSONP=isJSONP, nativeThread=forceNative)
      if not status:
         self._parentServer._logger(1, 'Error in execBackend_threaded._callDispatcher():', result)
      return status, params, result

   def add(self, uniqueId, data, request, isJSONP=False):
      #callback for adding notif to queue
      forceNative=self.settings['forceNative']
      if self.settings['saveResult']:
         # we need to return results
         try:
            status, params, result=self._parentServer.callAsync(childExecute, args=[uniqueId, data, request, isJSONP, forceNative], useGevent=not(forceNative))
            return status, params, result
         except Exception, e:
            print '!!! Error _notifBackend_threadPool_add', e
            return False, str(e), None
      else:
         # results not needed
         try:
            self._parentServer._thread(childExecute, args=[uniqueId, data, request, isJSONP, forceNative], forceNative=forceNative)
            return True, None, None
         except Exception, e:
            print '!!! Error _notifBackend_threadPool_add', e
            return False, str(e), None

   def stats(self, inMS=False, history=10):
      #! нужно собирать статистику
      r={}
      return r
