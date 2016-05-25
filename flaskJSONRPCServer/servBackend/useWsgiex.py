"""
This module provide Serving backend, that use <wsgiex>.
"""

from ..utils import magicDict

class servBackend:
   """

   """
   _id='wsgiex'
   _supportRawSocket=True
   _supportGevent=True
   _supportNative=True

   def __init__(self, spawnThreadFunc=None, killThreadFunc=None, sleepFunc=None, id=None):
      #check importing
      from wsgiex import ThreadedStreamServerEx, WSGIRequestHandlerEx, StreamServerEx, terminate_thread
      #init settings and _id
      self.settings=magicDict({
         'spawnThreadFunc':spawnThreadFunc,
         'killThreadFunc':killThreadFunc,
         'sleepFunc':sleepFunc
      })
      self._id=id or self._id

   def create(self, bind_addr, wsgiApp, log=True, sslArgs=None, threaded=True, useGevent=False, backlog=1000):
      from wsgiex import ThreadedStreamServerEx, WSGIRequestHandlerEx, StreamServerEx, terminate_thread
      if useGevent:
         try:
            import gevent
            import gevent.socket
            import gevent.select
            import gevent.event
         except ImportError:
            raise ImportError('Use pass <useGevent>=True to WSGIEX, but gevent not founded.')
      #configure server
      kwargs={
         'RequestHandlerClass':WSGIRequestHandlerEx,
         'bind_and_activate':True,
         'dispatcher':wsgiApp,
         'socketClass':gevent.socket if useGevent else None,
         'selectClass':gevent.select if useGevent else None,
         'eventClass':gevent.event.Event if useGevent else None,
         'ssl_args':sslArgs,
         'log':log,
         'request_queue_size':backlog
      }
      if threaded:
         servClass=ThreadedStreamServerEx
         tFunc0=lambda target, args=[], kwargs={}, daemon=None: gevent.spawn(target, *args, **kwargs)
         kwargs['spawnThreadFunc']=self.settings.spawnThreadFunc if self.settings.spawnThreadFunc else (tFunc0 if useGevent else None)
         kwargs['killThreadFunc']=self.settings.killThreadFunc if self.settings.killThreadFunc else (gevent.kill if useGevent else terminate_thread)
         kwargs['sleepFunc']=self.settings.sleepFunc if self.settings.sleepFunc else (gevent.sleep if useGevent else None)
      else:
         servClass=StreamServerEx
      #init server
      server=servClass(bind_addr, **kwargs)
      return server

   def start(self, bindAdress, wsgiApp, server, joinLoop):
      if not hasattr(server, '_server'): server._server=[]
      if not hasattr(server, '_serverThread'): server._serverThread=[]
      if not server._isTuple(bindAdress) and not server._isArray(bindAdress): backlog=None
      else: backlog=server.setts.backlog
      s=self.create(bindAdress, wsgiApp, log=server.setts.debug, threaded=True, useGevent=server.setts.gevent, sslArgs=server.setts.ssl, backlog=backlog)
      sThread=server._thread(s.serve_forever)
      server._server.append(s)
      server._serverThread.append(sThread)
      if joinLoop:
         try:
            while True: server._sleep(1000)
         except KeyboardInterrupt: pass

   def stop(self, serverInstance, serverIndex, server, timeout=5):
      serverInstance.stop(timeout=timeout)
