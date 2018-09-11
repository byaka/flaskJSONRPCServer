# -*- coding: utf-8 -*-
import sys, time, random, urlparse, inspect, json

from flaskJSONRPCServer import flaskJSONRPCServer
from flaskJSONRPCServer.utils import MagicDictCold, bind

class FlaskEmulate(object):
   """
   This simple class emulates Flask-like `route` decorator, thread-local read-only `request` variable for accessing `args`, `form` and `method` and basic `run()` method. Also it redirect POST-form requests to correct path like true jsonrpc calls.

   :Attention:

   It not completed and just `proof-of-concept` really.
   """

   _404_pattern='Not found, but known previous level: '

   def __init__(self, server):
      self.server=server
      server.postprocessAdd('cb', self.form2jsonrpc, status=[404])

   def route(self, rule, **options):
      def decorator(f):
         need_args, _, _, _=inspect.getargspec(f)
         need_args=set(s for i, s in enumerate(need_args) if not(i==0 and (s=='self' or s=='cls')))
         def f_wrapped(_connection=None, **kwargs):
            request=MagicDictCold(_connection.request.copy())
            request.method='POST'
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
         endpoint=options.pop('endpoint', f.__name__)
         options.pop('methods')
         self.server.registerFunction(f_wrapped, path=rule, name=endpoint, **options)
         return f_wrapped
      return decorator

   @classmethod
   def form2jsonrpc(cls, request, server, controller):
      if cls._404_pattern in controller.lastResponse[2]:
         try:
            req_data=server._loadPostData(request)
            req_args={k:v for k,v in urlparse.parse_qsl(req_data)}
            req_path=controller.lastResponse[2].split(cls._404_pattern, 1)[1]
            req_fileName=request['path'].split(req_path, 1)[1][:-1]
            request['headers']['__FlaskEmulate_form2jsonrpc']=True
         except Exception: return
         resp_data, resp_headers=server.simulateRequest(req_fileName, req_args, req_path, request['headers'])
         return (200, resp_data)

   def run(self, *args, **kwargs):
      if args or kwargs:
         self.server._log(2, 'Emulated `run()` method not supports arguments')
      self.server.serveForever()

server=flaskJSONRPCServer(("0.0.0.0", 7001), cors=True, gevent=True, debug=False, log=3, fallback=True, tweakDescriptors=False, experimental=False)
app=FlaskEmulate(server)

#######################################################################
####### This is old, Flask-specified, newbie pseudo-RESTful api #######
### But with `FlaskEmulate` we can support it without modifications ###
#######################################################################

def getParams(request):
   params={}
   if request.method == 'POST':
      params={k:v for k,v in request.form.iteritems()}
   else:
      for k in request.args:
         params[k]=request.args.get(k)
   return params

@app.route('/api', methods=['GET','POST'])
def test1():
   params=getParams(request)  # noqa: F821 (we add this var in runtime)
   res={'result':['test'], 'params_echo':params}
   return json.dumps(res)

if __name__=='__main__':
   app.run()
