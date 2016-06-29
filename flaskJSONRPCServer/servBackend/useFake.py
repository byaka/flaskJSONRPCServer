"""
This module provide fake Serving backend, that not listen any socket.
"""

from ..utils import *

class servBackend:
   """

   """
   _id='fake'
   _supportRawSocket=False
   _supportGevent=True
   _supportNative=True
   _supportMultiple=False
   _supportNoListener=True

   def __init__(self, id=None):
      #init settings and _id
      self.settings=magicDict({})
      self._id=id or self._id

   # def create(self, bind_addr, wsgiApp, log=True, sslArgs=None, backlog=1000, threaded=True):
   #    from werkzeug.serving import make_server as werkzeug
   #    if not log:
   #       import logging
   #       log=logging.getLogger('werkzeug')
   #       log.setLevel(logging.ERROR)
   #    sslContext=None
   #    if sslArgs:
   #       import ssl
   #       sslContext=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2) #SSL.Context(SSL.SSLv23_METHOD)
   #       sslContext.load_cert_chain(sslArgs[1], sslArgs[0])
   #    server=werkzeug(bind_addr[0], bind_addr[1], wsgiApp, threaded=threaded, ssl_context=sslContext)
   #    return server

   def start(self, bindAdress, wsgiApp, server, joinLoop):
      if not hasattr(server, '_server'): server._server=[]
      server._server.append('fake_server')
      if joinLoop:
         try:
            while True: server._sleep(1000)
         except KeyboardInterrupt: pass

   def stop(self, serverInstance, serverIndex, server, timeout=5):
      pass
