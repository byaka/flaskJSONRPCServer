#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains dispatcher-execution backend for flaskJSONRPCServer.

"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from __init__ import experimentalPack
   from utils import *
else:
   import sys, os
   from ..__init__ import experimentalPack
   from ..utils import *

class execBackend:
   """
   :param int poolSiza:
   :param float sleepTime_emptyQueue:
   :param float sleepTime_cicleWait:
   :param str id:
   :param bool forceNative:
   """

   def __init__(self, poolSize=5, sleepTime_emptyQueue=0.02, sleepTime_cicleWait=0.02, id='execBackend_threaded', forceNative=False):
      self.settings={
         'poolSize':poolSize,
         'sleepTime_emptyQueue':sleepTime_emptyQueue,
         'sleepTime_cicleWait':sleepTime_cicleWait,
         'forceNative':forceNative
      }
      self.queue=deque2()
      self._poolSize=0
      self._id=id
      if forceNative: self._id+='Native'
      self._mainCicleThread=None

   def start(self, server):
      if self._mainCicleThread: return
      if self.settings['forceNative'] and server.setts.gevent:
         server._logger('Warning: notifBackend forced to use Native Threads')
      self._parentServer=server
      self._mainCicleThread=server._thread(self.mainCicle)

   def mainCicle(self):
      #main cicle for processing notifs. Run on starting backend
      while True:
         self._parentServer._deepWait()
         self._parentServer._sleep(self.settings['sleepTime_cicleWait'])
         if not len(self.queue): continue
         tArr1=self.queue.popleft()
         mytime=self._parentServer._getms()
         while self._poolSize>=self.settings['poolSize']:
            self._parentServer._sleep(self.settings['sleepTime_emptyQueue'])
         self._poolSize+=1
         self._parentServer._speedStatsAdd('notifBackend_wait', self._parentServer._getms()-mytime)
         isForceNative=self.settings['forceNative'] and self._parentServer.__settings['gevent']
         self._parentServer._thread(self.childExecute, args=[tArr1, isForceNative or not(self._parentServer.__settings['gevent'])], forceNative=isForceNative)

   def childExecute(self, p, nativeThread=False):
      status, params, result=self._parentServer._callDispatcher(p['uniqueId'], p['dataIn'], p['request'], nativeThread=nativeThread, isJSONP=p.get('isJSONP', False))
      if not status:
         self._parentServer._logger(1, 'ERROR in notifBackend._callDispatcher():', result)
      self._poolSize-=1

   def add(self, uniqueId, dataIn, request, isJSONP=False):
      #callback for adding notif to queue
      try:
         self.queue.append({'uniqueId':uniqueId, 'isJSONP':isJSONP, 'dataIn':dataIn, 'request':request, 'mytime':self._parentServer._getms()})
         return True, len(self.queue), None
      except Exception, e:
         print '!!! ERROR _notifBackend_threadPool_add', e
         return False, str(e), None

   # def check(self, uniqueId, _):
   #    pass

   def stats(self, inMS=False):
      r={
         '%s_queue'%self._id:len(self.queue)
      }
      return r
