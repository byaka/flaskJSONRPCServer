#!/usr/bin/env python
# -*- coding: utf-8 -*-
__version__='0.3.1'
"""
:authors: Jhon Byaka
:copyright: Copyright 2015, Buber
:license: Apache License 2.0

:license:

   Copyright 2015 Buber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import sys, inspect, decimal, random, json, datetime, time, gzip
from cStringIO import StringIO
from flask import Flask, request, Response

class magicDict(dict):
   #get and set values like in Javascript (dict.<key>)
   __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__

class flaskJSONRPCServer:
   def __init__(self, ipAndPort, requestHandler=None, blocking=True, cors=False, gevent=False, debug=False, log=True, fallback=True, allowCompress=False):
      self.flaskAppName='_%s_'%(int(random.random()*65536))
      self.version=__version__
      self.setts=magicDict({'ip':ipAndPort[0], 'port':ipAndPort[1], 'blocking':blocking, 'fallback_JSONP':fallback, 'CORS':cors, 'gevent':gevent, 'debug':debug, 'log':log, 'allowCompress':allowCompress, 'compressMinSize':1024})
      self.dispatchers={}
      self.flaskApp=Flask(self.flaskAppName)
      self.fixJSON=None
      self.speedStats={}
      self.connPerMinute=magicDict({'nowMinute':0, 'count':0, 'oldCount':0, 'maxCount':0, 'minCount':0})
      if self.isFunction(requestHandler): self._requestHandler=requestHandler
      else: self._requestHandler=self.requestHandler

   def isFunction(self, o): return hasattr(o, '__call__')

   def isArray(self, o): return isinstance(o, (list))

   def isDict(self, o): return isinstance(o, (dict))

   def speedStatsAdd(self, name, val):
      if name not in self.speedStats: self.speedStats[name]=[]
      self.speedStats[name].append(val)
      if len(self.speedStats[name])>9999:
         self.speedStats[name]=self.speedStats[name][len(self.speedStats[name])-9999:]

   def registerInstance(self, dispatcher, path=''):
      #add links to methods
      for name in dir(dispatcher):
         link=getattr(dispatcher, name)
         if self.isFunction(link):
            self.dispatchers[name]=link
            if hasattr(link, '_alias'):
               tArr1=link._alias if self.isArray(link._alias) else [link._alias]
               for alias in tArr1: self.dispatchers[alias]=link
      #register dispatcher
      if self.setts.fallback_JSONP: #additional path for support JSONP
         path_jsonp=path+('/' if path[-1]!='/' else '')+'<method>'
         self.flaskApp.add_url_rule(rule=path_jsonp, view_func=self._requestHandler, methods=['GET', 'OPTIONS', 'POST'])
      self.flaskApp.add_url_rule(rule=path, view_func=self._requestHandler, methods=['GET', 'OPTIONS', 'POST'])

   def registerFunction(self, dispatcher, path=''):
      #add links to methods
      self.dispatchers[dispatcher.__name__]=dispatcher
      if hasattr(dispatcher, '_alias'):
         tArr1=dispatcher._alias if self.isArray(dispatcher._alias) else [dispatcher._alias]
         for alias in tArr1: self.dispatchers[alias]=dispatcher
      #register dispatcher
      if self.setts.fallback_JSONP: #additional path for support JSONP
         path_jsonp=path+('/' if path[-1]!='/' else '')+'<method>'
         self.flaskApp.add_url_rule(rule=path_jsonp, view_func=self._requestHandler, methods=['GET', 'OPTIONS', 'POST'])
      self.flaskApp.add_url_rule(rule=path, view_func=self._requestHandler, methods=['GET', 'OPTIONS', 'POST'])

   def parseRequest(self, data):
      try:
         mytime=time.time()*1000.0
         tArr1=json.loads(data)
         tArr2=[]
         tArr1=tArr1 if self.isArray(tArr1) else [tArr1] #support for batch requests
         for r in tArr1:
            tArr2.append({'jsonrpc':r.get('jsonrpc', None), 'method':r.get('method', None), 'params':r.get('params', None), 'id':r.get('id', None)})
         self.speedStatsAdd('parseRequest', time.time()*1000.0-mytime)
         return [True, tArr2]
      except Exception, e:
         self.logger(e)
         return [False, e]

   def prepResponse(self, data, isError=False):
      id=data.get('id', None)
      if 'id' in data: del data['id']
      if isError:
         s={"jsonrpc": "2.0", "error": data, "id": id}
      elif id:
         s={"jsonrpc": "2.0", "result": data['data'], "id": id}
      return s

   def serializeResponse(self, data):
      def _fixJSON(o):
         if isinstance(o, decimal.Decimal): return str(o) #fix Decimal conversion
         elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)): return o.isoformat() #fix DateTime conversion
         elif self.isFunction(self.fixJSON): return self.fixJSON(o) #callback for user's types
      mytime=time.time()*1000.0
      s=json.dumps(data, indent=None, separators=(',',':'), ensure_ascii=True, sort_keys=True, default=_fixJSON)
      self.speedStatsAdd('serializeResponse', time.time()*1000.0-mytime)
      return s

   def getErrorInfo(self):
      tArr=inspect.trace()[-1]
      fileName=tArr[1]
      lineNo=tArr[2]
      exc_obj=sys.exc_info()[1]
      s='%s:%s > %s'%(fileName, lineNo, exc_obj)
      sys.exc_clear()
      return s

   def logger(self, *args):
      if not self.setts.log: return
      for i in xrange(len(args)):
         s=args[i]
         try: sys.stdout.write(s)
         except:
            try:
               s=self.serializeResponse(s)
               sys.stdout.write(s if s else '') #! strUniDecode(s)
            except: sys.stdout.write('<UNPRINTABLE DATA>')
         if i<len(args)-1: sys.stdout.write(' ')
      sys.stdout.write('\n')

   def callDispatcher(self, data, request, isJSONP=False):
      try:
         params={}
         _args, _varargs, _keywords, _defaults=inspect.getargspec(self.dispatchers[data['method']])
         _args=[s for s in _args if s!='self']
         if self.isDict(data['params']): params=data['params']
         elif self.isArray(data['params']):
            #convert array of arguments to **kwargs
            for i in xrange(len(data['params'])):
               params[_args[i]]=data['params'][i]
         if '_connection' in _args: #add connection info if needed
            params['_connection']=magicDict({'headers':dict([h for h in request.headers]), 'cookies':request.cookies, 'ip':request.environ.get('HTTP_X_REAL_IP', request.remote_addr), 'cookiesOut':[], 'headersOut':{}, 'jsonp':isJSONP, 'allowCompress':self.setts.allowCompress, 'server':self})
         mytime=time.time()*1000.0
         result=self.dispatchers[data['method']](**params)
         self.speedStatsAdd('callDispatcher', time.time()*1000.0-mytime)
         return True, params, result
      except Exception:
         return False, params, self.getErrorInfo()

   def requestHandler(self, method=None):
      #calculate connections per second
      nowMinute=int(time.time())/60
      if nowMinute!=self.connPerMinute.nowMinute:
         self.connPerMinute.nowMinute=nowMinute
         if self.connPerMinute.count:
            self.connPerMinute.oldCount=self.connPerMinute.count
         if self.connPerMinute.count>self.connPerMinute.maxCount:
            self.connPerMinute.maxCount=self.connPerMinute.count
         if self.connPerMinute.count<self.connPerMinute.minCount or not self.connPerMinute.minCount:
            self.connPerMinute.minCount=self.connPerMinute.count
         self.connPerMinute.count=0
      self.connPerMinute.count+=1
      #start processing request
      error=[]
      out=[]
      outHeaders={}
      outCookies=[]
      dataOut=[]
      mytime=round(time.time()*1000.0, 0)
      allowCompress=self.setts.allowCompress
      if self.setts.CORS:
         outHeaders.update({'Access-Control-Allow-Headers':'Origin, Authorization, X-Requested-With, Content-Type, Accept', 'Access-Control-Max-Age':'0', 'Access-Control-Allow-Methods':'GET, PUT, POST, DELETE, OPTIONS'})
         if self.isDict(self.setts.CORS):
            outHeaders['Access-Control-Allow-Origin']=self.setts.CORS.get('origin', '*')
         else:
            outHeaders['Access-Control-Allow-Origin']='*'
      if request.method=='OPTIONS':
         self.logger('REQUEST TYPE == OPTIONS')
      elif request.method=='POST': #JSONRPC
         data=request.data or (request.form.keys()[0] if len(request.form.keys())==1 else None)
         self.logger('REQUEST:', data)
         status, dataInList=self.parseRequest(data)
         if not status: #error of parsing
            error={"code": -32700, "message": "Parse error"}
         else:
            for dataIn in dataInList:
               if not(dataIn['jsonrpc']) or not(dataIn['method']) or (dataIn['params'] and not(self.isDict(dataIn['params'])) and not(self.isArray(dataIn['params']))): #syntax error in request
                  error.append({"code": -32600, "message": "Invalid Request"})
               elif dataIn['method'] not in self.dispatchers: #call of uncknown method
                  error.append({"code": -32601, "message": "Method not found", "id":dataIn['id']})
               else: #process correct request
                  if not dataIn['id']: #notification request
                     #! add non-blocking processing
                     status, params, result=self.callDispatcher(dataIn, request)
                  else: #simple request
                     status, params, result=self.callDispatcher(dataIn, request)
                     if status:
                        if '_connection' in params: #get additional headers and cookies
                           outHeaders.update(params['_connection'].headersOut)
                           outCookies+=params['_connection'].cookiesOut
                           if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                           elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
                        out.append({"id":dataIn['id'], "data":result})
                     else:
                        error.append({"code": 500, "message": result, "id":dataIn['id']})
         #prepare output for response
         self.logger('ERRORS:', error)
         self.logger('OUT:', out)
         if self.isDict(error): #error of parsing
            dataOut=self.prepResponse(error, isError=True)
         elif len(error) and len(dataInList)>1: #error for batch request
            for d in error: dataOut.append(self.prepResponse(d, isError=True))
         elif len(error): #error for simple request
            dataOut=self.prepResponse(error[0], isError=True)
         if len(out) and len(dataInList)>1: #response for batch request
            for d in out: dataOut.append(self.prepResponse(d, isError=False))
         elif len(out): #response for simple request
            dataOut=self.prepResponse(out[0], isError=False)
         #serialize response
         dataOut=self.serializeResponse(dataOut)
      elif request.method=='GET': #JSONP fallback
         self.logger('REQUEST:', method, request.args)
         jsonpCB=request.args.get('jsonp', False)
         jsonpCB='%s(%%s);'%(jsonpCB) if jsonpCB else '%s;'
         if not method or method not in self.dispatchers: #call of uncknown method
            out.append({'jsonpCB':jsonpCB, 'data':{"error":{"code": -32601, "message": "Method not found"}}})
         else: #process correct request
            params=dict([(k, v) for k, v in request.args.items()])
            if 'jsonp' in params: del params['jsonp']
            dataIn={'method':method, 'params':params}
            status, params, result=self.callDispatcher(dataIn, request, isJSONP=jsonpCB)
            if status:
               if '_connection' in params: #get additional headers and cookies
                  outHeaders.update(params['_connection'].headersOut)
                  outCookies+=params['_connection'].cookiesOut
                  jsonpCB=params['_connection'].jsonp
                  if self.setts.allowCompress and params['_connection'].allowCompress is False: allowCompress=False
                  elif self.setts.allowCompress is False and params['_connection'].allowCompress: allowCompress=True
               out.append({'jsonpCB':jsonpCB, 'data':result})
            else:
               out.append({'jsonpCB':jsonpCB, 'data':result})
         #prepare output for response
         self.logger('ERRORS:', error)
         self.logger('OUT:', out)
         if len(out): #response for simple request
            dataOut=self.serializeResponse(out[0]['data'])
            dataOut=out[0]['jsonpCB']%(dataOut)
      self.logger('RESPONSE:', dataOut)
      resp=Response(response=dataOut, status=200, mimetype=('text/javascript' if request.method=='GET' else 'application/json'))
      for hk, hv in outHeaders.items(): resp.headers[hk]=hv
      for c in outCookies:
         try: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647), domain=c.get('domain', '*'))
         except: resp.set_cookie(c.get('name', ''), c.get('value', ''), expires=c.get('expires', 2147483647))
      self.logger('GENERATE TIME:', round(time.time()*1000.0, 0)-mytime)
      #compression
      if resp.status_code!=200 or len(resp.data)<self.setts.compressMinSize or not allowCompress or 'gzip' not in request.headers.get('Accept-Encoding', '').lower():
         #without compression
         return resp
      mytime=round(time.time()*1000.0, 0)
      resp.direct_passthrough=False
      gzip_buffer=StringIO()
      gzip_file=gzip.GzipFile(mode='wb', fileobj=gzip_buffer)
      gzip_file.write(resp.data)
      gzip_file.close()
      resp.data=gzip_buffer.getvalue()
      resp.headers['Content-Encoding']='gzip'
      resp.headers['Vary']='Accept-Encoding'
      resp.headers['Content-Length']=len(resp.data)
      self.speedStatsAdd('compressResponse', time.time()*1000.0-mytime)
      self.logger('COMPRESSION TIME:', round(time.time()*1000.0, 0)-mytime)
      return resp

   def serveForever(self):
      if self.setts.gevent:
         self.logger('SERVER RUNNING AS GEVENT..')
         if not self.setts.blocking:
            from gevent import monkey
            monkey.patch_all()
         #! For auto-restart on change with gevent see http://goo.gl/LCbAcA
         # if self.setts.debug:
         #    from werkzeug.serving import run_with_reloader
         #    self.flaskApp=run_with_reloader(self.flaskApp)
         #    self.flaskApp.debug=True
         from gevent.wsgi import WSGIServer
         WSGIServer((self.setts.ip, self.setts.port), self.flaskApp, log=('default' if self.setts.debug else False)).serve_forever()
      else:
         self.logger('SERVER RUNNING..')
         self.flaskApp.run(host=self.setts.ip, port=self.setts.port, debug=self.setts.debug, threaded=not(self.setts.blocking))

"""REQUEST-RESPONSE SAMPLES
--> {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}
<-- {"jsonrpc": "2.0", "result": 19, "id": 1}

--> {"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}
<-- {"jsonrpc": "2.0", "result": 19, "id": 3}

--> {"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}
--> {"jsonrpc": "2.0", "method": "foobar"}

--> {"jsonrpc": "2.0", "method": "foobar", "id": "1"}
<-- {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}

--> {"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]
<-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}

--> {"jsonrpc": "2.0", "method": 1, "params": "bar"}
<-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}

--> [1,2,3]
<-- [
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    ]

--> [
      {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
      {"jsonrpc": "2.0", "method"
    ]
<-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}

--> [
      {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
      {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
      {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
      {"foo": "boo"},
      {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
      {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
    ]
<-- [
      {"jsonrpc": "2.0", "result": 7, "id": "1"},
      {"jsonrpc": "2.0", "result": 19, "id": "2"},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "5"},
      {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
    ]
"""
