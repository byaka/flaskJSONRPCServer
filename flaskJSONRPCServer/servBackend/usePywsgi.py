"""
This module provide Serving backend, that use <gevent.pywsgi>.
"""

from ..utils import magicDict

class servBackend:
   """

   """
   _id='pywsgi'
   _supportRawSocket=True
   _supportGevent=True
   _supportNative=False
   _supportMultiple=False

   def __init__(self, id=None):
      #check importing
      from gevent.pywsgi import WSGIServer
      from gevent.pool import Pool
      #init settings and _id
      self.settings=magicDict({})
      self._id=id or self._id

   def create(self, bind_addr, wsgiApp, log=True, sslArgs=None, backlog=1000):
      from gevent.pywsgi import WSGIServer
      from gevent.pool import Pool
      pool=Pool(None)
      if sslArgs:
         from gevent import ssl
         # from functools import wraps
         # def sslwrap(func):
         #    @wraps(func)
         #    def bar(*args, **kw):
         #       kw['ssl_version']=ssl.PROTOCOL_TLSv1
         #       return func(*args, **kw)
         #    return bar
         # ssl.wrap_socket=sslwrap(ssl.wrap_socket)
         server=WSGIServer(bind_addr, wsgiApp, log=('default' if log else None), spawn=pool, backlog=backlog, keyfile=sslArgs[0], certfile=sslArgs[1], ssl_version=ssl.PROTOCOL_TLSv1_2) #ssl.PROTOCOL_SSLv23
      else:
         server=WSGIServer(bind_addr, wsgiApp, log=('default' if log else None), spawn=pool, backlog=backlog)
      return server, pool

   def start(self, bindAdress, wsgiApp, server, joinLoop):
      if not hasattr(server, '_server'): server._server=[]
      if not hasattr(server, '_serverPool'): server._serverPool=[]
      if not server._isTuple(bindAdress) and not server._isArray(bindAdress): backlog=None
      else: backlog=server.setts.backlog
      s, p=self.create(bindAdress, wsgiApp, log=server.setts.debug, sslArgs=server.setts.ssl, backlog=backlog)
      server._server.append(s)
      server._serverPool.append(p)
      try:
         if joinLoop: s.serve_forever()
         else: s.start()
      except KeyboardInterrupt: pass

   def stop(self, serverInstance, serverIndex, server, timeout=5):
      serverInstance.stop(timeout=timeout)
