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

   def start(self, bindAdress, wsgiApp, server, joinLoop):
      if not hasattr(server, '_server'): server._server=[]
      server._server.append('fake_server')
      if joinLoop:
         try:
            while True: server._sleep(1000)
         except KeyboardInterrupt: pass

   def stop(self, serverInstance, serverIndex, server, timeout=5):
      pass
