#!/usr/bin/env python
# -*- coding: utf-8 -*-
__version__='0.4.1'
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

import sys, inspect, decimal, random, json, datetime, time, gzip, resource, os, zipfile, atexit, subprocess
from cStringIO import StringIO
Flask=None
request=None
Response=None

class magicDict(dict):
   #get and set values like in Javascript (dict.<key>)
   __getattr__=dict.__getitem__
   __setattr__=dict.__setitem__
   __delattr__=dict.__delitem__

class flaskJSONRPCServer:
   def __init__(self, ipAndPort, requestHandler=None, blocking=True, cors=False, gevent=False, debug=False, log=True, fallback=True, allowCompress=False, ssl=False, tweakDescriptors=(65536, 65536)):
      # Flask imported here for avoiding error in setup.py if Flask not installed yet
      global Flask, request, Response
      from flask import Flask, request, Response
      self.tweakLimit(tweakDescriptors)
      self.flaskAppName='_%s_'%(int(random.random()*65536))
      self.version=__version__
      self.setts=magicDict({
         'ip':ipAndPort[0],
         'port':ipAndPort[1],
         'blocking':blocking,
         'fallback_JSONP':fallback,
         'CORS':cors,
         'gevent':gevent,
         'debug':debug,
         'log':log,
         'allowCompress':allowCompress,
         'compressMinSize':1024,
         'ssl':ssl
      })
      self.dispatchers={}
      self.flaskApp=Flask(self.flaskAppName)
      self.fixJSON=None
      self.speedStats={}
      self.connPerMinute=magicDict({'nowMinute':0, 'count':0, 'oldCount':0, 'maxCount':0, 'minCount':0})
      if self.isFunction(requestHandler): self._requestHandler=requestHandler
      else: self._requestHandler=self.requestHandler

   def tweakLimit(self, descriptors=(65536, 65536)):
      if descriptors: #tweak ulimit for more file descriptors
         try: #for Linux
            if resource.getrlimit(resource.RLIMIT_NOFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_NOFILE, descriptors)
         except: pass
         try: #for BSD
            if resource.getrlimit(resource.RLIMIT_OFILE)!=descriptors:
               resource.setrlimit(resource.RLIMIT_OFILE, descriptors)
         except: pass

   def isFunction(self, o): return hasattr(o, '__call__')

   def isArray(self, o): return isinstance(o, (list))

   def isDict(self, o): return isinstance(o, (dict))

   def isString(self, o): return isinstance(o, (str, unicode))

   def fileGet(self, fName, method='r'):
      #get content from file,using $method and if file is ZIP, read file $method in this archive
      fName=fName.encode('cp1251')
      if not os.path.isfile(fName): return None
      if zipfile.is_zipfile(fName):
         c=zipfile.ZipFile(fName, method)
         try: s=c.read(method)
         except Exception, e:
            self.logger('Error fileGet', fName, ',', method, e)
            s=None
         c.close()
      else:
         try:
            with open(fName, method) as f: s=f.read()
         except: s=None
      return s

   def fileWrite(self, fName, text, mode='w'):
      if not self.isString(text): text=repr(text)
      with open(fName, mode) as f: f.write(text)

   def strGet(self, text, pref='', suf='', index=0, default=None):
      #return pattern by format pref+pattenr+suf
      if(text==''): return ''
      text1=text.lower()
      pref=pref.lower()
      suf=suf.lower()
      if pref!='': i1=text1.find(pref,index)
      else: i1=index
      if i1==-1: return default
      if suf!='': i2=text1.find(suf,i1+len(pref))
      else: i2=len(text1)
      if i2==-1: return default
      return text[i1+len(pref):i2]

   def speedStatsAdd(self, name, val):
      if name not in self.speedStats: self.speedStats[name]=[]
      self.speedStats[name].append(val)
      if len(self.speedStats[name])>99999:
         self.speedStats[name]=self.speedStats[name][len(self.speedStats[name])-99999:]

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
         self.logger('Error parseRequest', e)
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
            #convert *args to **kwargs
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
         from gevent.pywsgi import WSGIServer
         if self.setts.ssl:
            from gevent import ssl
            # from functools import wraps
            # def sslwrap(func):
            #    @wraps(func)
            #    def bar(*args, **kw):
            #       kw['ssl_version']=ssl.PROTOCOL_TLSv1
            #       return func(*args, **kw)
            #    return bar
            # ssl.wrap_socket=sslwrap(ssl.wrap_socket)
            WSGIServer((self.setts.ip, self.setts.port), self.flaskApp, log=('default' if self.setts.debug else False), keyfile=self.setts.ssl[0], certfile=self.setts.ssl[1], ssl_version=ssl.PROTOCOL_TLSv1_2).serve_forever() #ssl.PROTOCOL_SSLv23
         else:
            WSGIServer((self.setts.ip, self.setts.port), self.flaskApp, log=('default' if self.setts.debug else False)).serve_forever()
      else:
         self.logger('SERVER RUNNING..')
         if not self.setts.debug:
            import logging
            log=logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
         if self.setts.ssl:
            import ssl
            context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2) #SSL.Context(SSL.SSLv23_METHOD)
            context.load_cert_chain(self.setts.ssl[1], self.setts.ssl[0])
            self.flaskApp.run(host=self.setts.ip, port=self.setts.port, ssl_context=context, debug=self.setts.debug, threaded=not(self.setts.blocking))
         else:
            self.flaskApp.run(host=self.setts.ip, port=self.setts.port, debug=self.setts.debug, threaded=not(self.setts.blocking))

   # def createSSLTunnel(self, port_https, port_http, sslCert='', sslKey='', stunnel_configPath='/home/sslCert/', stunnel_exec='stunnel4', stunnel_configSample=None, stunnel_sslAllow='all', stunnel_sslOptions='-NO_SSLv2 -NO_SSLv3', stunnel_logLevel=4, stunnel_logFile='/home/python/logs/stunnel_%s.log'):
   #    print 'Creating tunnel (localhost:%s --> localhost:%s)..'%(port_https, port_http)
   #    configSample=self.fileGet(stunnel_configSample) if stunnel_configSample else """
   #    debug = %(logLevel)s
   #    output = /dev/null
   #    foreground = yes
   #    socket = l:TCP_NODELAY=1
   #    socket = r:TCP_NODELAY=1

   #    [myservice_%(name)s]
   #    sslVersion = %(sslAllow)s
   #    %(sslOptions)s
   #    cert = %(sslCert)s
   #    key = %(sslKey)s
   #    accept  = %(portHttps)s
   #    connect = %(portHttp)s
   #    TIMEOUTclose = 10
   #    TIMEOUTbusy     = 30
   #    TIMEOUTconnect  = 10
   #    TIMEOUTidle = 10
   #    sessionCacheTimeout = 60
   #    """
   #    name=os.path.splitext(os.path.basename(sys.argv[0]))[0]
   #    stunnel_sslOptions='\n'.join(['options = '+s for s in stunnel_sslOptions.split(' ') if s])
   #    config={'name':name, 'logLevel':stunnel_logLevel, 'sslAllow':stunnel_sslAllow, 'sslOptions':stunnel_sslOptions, 'sslCert':sslCert, 'sslKey':sslKey, 'portHttps':port_https, 'portHttp':port_http}
   #    config=configSample%config
   #    configPath=stunnel_configPath+('stunnel_%s.conf'%name)
   #    logPath=stunnel_logFile%name
   #    self.fileWrite(configPath, config)
   #    stunnel=subprocess.Popen([stunnel_exec, configPath], stderr=open(logPath, "w"))
   #    time.sleep(1)
   #    if stunnel.poll(): #error
   #       s=self.fileGet(logPath)
   #       s='[!] '+self.strGet(s, '[!]', '')
   #       print '!!! ERROR creating tunnel\n', s
   #       return False
   #    def closeSSLTunnel():
   #       try: os.system('pkill -f "%s %s"'%(stunnel_exec, configPath))
   #       except: pass
   #    atexit.register(closeSSLTunnel)
   #    # def checkSSLTunnel():
   #    #    badPatterns=['Connection rejected: too many clients']
   #    #    while True:
   #    #       time.sleep(3)
   #    #       #! Здесь нужно проверять лог на наличие критических ошибок
   #    #       stunnelLog=self.fileGet(logPath)
   #    # thread_checkSSLTunnel=threading.Thread(target=checkSSLTunnel).start()
   #    return stunnel

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
