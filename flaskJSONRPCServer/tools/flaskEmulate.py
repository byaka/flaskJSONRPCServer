# -*- coding: utf-8 -*-
import sys, urlparse, inspect, json

from .. import flaskJSONRPCServer
from ..utils import MagicDictCold, bind, formatPath

class FlaskEmulate(object):
   """
   This simple class emulates Flask-like `route` decorator, thread-local read-only `request` variable for accessing `args`, `form` and `method` and basic `run()` method. Also it redirect POST-form requests to correct path like true jsonrpc calls.

   :Attention:

   It not completed and just `proof-of-concept` really.
   """

   _404_pattern='Not found, but known previous level: '
   _403_pattern='JSONP_DENIED'

   def __init__(self, server):
      self.server=server
      self.server.settings['fallback_JSONP']=False
      self.server.postprocessAdd('cb', self.form2jsonrpc, status=[404])
      self.server.postprocessAdd('cb', self.jsonp2jsonrpc, status=[403])

   def route(self, rule, **options):
      def decorator(f):
         need_args, _, _, _=inspect.getargspec(f)
         need_args=set(s for i, s in enumerate(need_args) if not(i==0 and (s=='self' or s=='cls')))
         def f_wrapped(_connection=None, **kwargs):
            request=MagicDictCold(_connection.request.copy())
            request.method='POST'
            if not request.params or request.params==[]:
               request.params={}
            request.form=request.args=request.params
            request._MagicDictCold__freeze()
            #! not supports positional args
            f_binded=bind(f, globalsUpdate={'request':request})
            if need_args:
               kwargs={k:v for k,v in kwargs.iteritems() if k in need_args}
               if '_connection' in need_args:
                  kwargs['_connection']=_connection
            #~ overhead of above code near 70mks
            r=f_binded(**kwargs) if need_args else f_binded()
            return r
         options.pop('endpoint', f.__name__)
         options.pop('methods')
         tArr=formatPath(rule)[1:-1].split('/')
         name=tArr[-1]
         path=formatPath('/'.join(tArr[:-1]))
         self.server.registerFunction(f_wrapped, path=path, name=name, fallback=False, **options)
         return f_wrapped
      return decorator

   def __simulateRequest(self, name, args, path, headers):
      resp_data, resp_headers=self.server.simulateRequest(name, args, path, headers)
      return (200, resp_data, resp_headers)

   def form2jsonrpc(self, request, server, controller):
      if self._404_pattern in controller.lastResponse[2]:
         try:
            data=server._loadPostData(request)
            args={k:v for k,v in urlparse.parse_qsl(data)}
            path=controller.lastResponse[2].split(self._404_pattern, 1)[1]
            name=request['path'].split(path, 1)[1][:-1]
            request['headers']['__FlaskEmulate_form2jsonrpc']=True
         except Exception: return
         return self.__simulateRequest(name, args, path, request['headers'])

   def jsonp2jsonrpc(self, request, server, controller):
      if self._403_pattern in controller.lastResponse[2]:
         try:
            request['headers']['__FlaskEmulate_jsonp2jsonrpc']=True
         except Exception: return
         return self.__simulateRequest(request['fileName'], request['args'], request['path'], request['headers'])

   def run(self, *args, **kwargs):
      if args or kwargs:
         self.server._logger(2, 'Emulated `run()` method not supports arguments')
      self.server.serveForever()
