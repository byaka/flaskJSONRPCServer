#!/usr/bin/env python
# -*- coding: utf-8 -*-

__ver_major__ = 0
__ver_minor__ = 4
__ver_patch__ = 1
__ver_sub__ = ""
__version__ = "%d.%d.%d" % (__ver_major__, __ver_minor__, __ver_patch__)
"""
This package provide extended versions of StreamServer, WSGIRequestHandler and some additions.
It doesn't has any dependences and use some parts of Werkzeug's and pyWSGI's sources.

:authors: John Byaka
:copyright: Copyright 2016, Buber
:license: Apache License 2.0

:license:

   Copyright 2016 Buber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import sys, os, socket, threading, random, time, fcntl, urllib, traceback, inspect
from fhhp import httpInputWrapper, LongRequestError

sys_version="Python/"+sys.version.split()[0]

# Default http error message template
DEFAULT_ERROR_CONTENT_TYPE="text/html"
DEFAULT_ERROR_MESSAGE="""
<head>
<title>Error response</title>
</head>
<body>
<h1>Error response</h1>
<p>Error code %(code)d.
<p>Message: %(message)s.
<p>Error code explanation: %(code)s = %(explain)s.
</body>
"""

class StreamServerEx(object):
   """
   Extended impelementation of TCPServer, that supports UnixDomainSockets and passed sockets. It also supports SSL and overloading Socket's class and Select's class (for simple using with gevent, for example) by passing <socketClass>, <selectClass>, <eventClass>.
   """

   software_version='StreamServerEx/%s'%__version__
   multithread=False
   multiprocess=False
   allow_reuse_address=True
   request_queue_size=256
   socket_type=None

   def __init__(self, bind_addr, handler_class, bind_and_activate=True, dispatcher=None, socketClass=None, eventClass=None, ssl_args=None, log=True, request_queue_size=None):
      if (handler_class is None or handler_class is WSGIRequestHandlerEx) and not dispatcher:
         raise ValueError('You must set <dispatcher> for WSGIRequestHandlerEx')
      # vars
      self._uds=False
      self._socketPassed=False
      self._fdPassed=False
      # select mode
      if isinstance(bind_addr, tuple):
         if len(bind_addr)!=2:
            raise ValueError('Wrong length of attr <bind_addr>, must be 2')
         elif isinstance(bind_addr[0], int):  #file-descriptor
            self._fdPassed=True
            self._uds=not(bind_addr[1])
         else: pass  #ip and port
      elif isinstance(bind_addr, (str, unicode)):  #path to UDS
         self._uds=True
      else:  #socket object
         self._socketPassed=True
      #configure server
      self._log=log
      self._request_queue_size=request_queue_size or self.request_queue_size
      self._dispatcher=dispatcher
      self._requestHandlerClass=handler_class or WSGIRequestHandlerEx
      self._socketClass=socketClass or socket
      self._eventClass=eventClass or threading.Event
      self._sleep=time.sleep
      self.address_family=self._socketClass.AF_UNIX if self._uds else self._socketClass.AF_INET
      self.socket_type=self.socket_type or self._socketClass.SOCK_STREAM
      self._bind_addr=None if self._socketPassed else bind_addr
      self.__stopping={'called':False, 'ended':self._eventClass()}
      if self._fdPassed:
         # create socket from FD
         if not hasattr(self._socketClass, 'fromfd'):
            raise NotImplementedError('Creating socket from FD not implemented in given class %s'%self._socketClass)
         self.socket=self._socketClass.socket.fromfd(bind_addr[0], self.address_family, self.socket_type)
      elif not self._socketPassed:
         # create new socket
         if self._uds and os.path.exists(bind_addr): os.remove(bind_addr)
         self.socket=self._socketClass.socket(self.address_family, self.socket_type)
      else:
         # only set passed socket
         self.address_family=None
         self.socket=bind_addr
         self.server_name=''
         self.server_port=''
      # now we can bind if needed
      if bind_and_activate:
         try:
            if not self._socketPassed and not self._fdPassed: self.server_bind()
            if not self._fdPassed: self.server_activate()  #! проверить, возможно это нужно делать и для _fdPassed
         except:
            self.socket.close()
            raise
      # now prepare for SSL (source from werkzeug)
      if isinstance(ssl_args, tuple) and len(ssl_args):
         self._ssl_args=ssl_args
         self._ssl_context=_SSLContext(protocol=(None if len(ssl_args)<3 else ssl_args[2]))
         self._ssl_context.load_cert_chain(ssl_args[0], (None if len(ssl_args)<2 else ssl_args[1]))
         # In Python2 the return value from socket.fromfd is an internal socket object but what we need for ssl wrap is the wrapper around it
         if not isinstance(self.socket, self._socketClass.socket):
            self.socket=self._socketClass.socket(self.socket.family, self.socket.type, self.socket.proto, self.socket)
         self.socket=self._ssl_context.wrap_socket(self.socket, server_side=True)
      else:
         self._ssl_args=ssl_args
         self._ssl_context=None

   def __del__(self):
      self.socket.close()

   def server_bind(self):
      if self.allow_reuse_address:
         self.socket.setsockopt(self._socketClass.SOL_SOCKET, self._socketClass.SO_REUSEADDR, 1)
      self.socket.bind(self._bind_addr)
      # Tell the server socket file descriptor to destroy itself when this program ends.
      socketFlags=fcntl.fcntl(self.socket.fileno(), fcntl.F_GETFD)
      socketFlags|=fcntl.FD_CLOEXEC
      fcntl.fcntl(self.socket.fileno(), fcntl.F_SETFD, socketFlags)
      # for UDS we skip getting server_name
      if self._uds:
         self.server_name=self._bind_addr
         self.server_port=''
      else:
         host, port=self.socket.getsockname()[:2]
         self.server_name=self._socketClass.getfqdn(host)
         self.server_port=port

   def server_activate(self):
      self.socket.listen(self._request_queue_size)

   def start(self, poll_interval=1):
      """
      Start server's loop.

      This method switch socket to non-blocking mode with <poll_interval> and start main loop. If <poll_interval> is None, switching server to blocking mode. In this case for stopping server you need to do any request to it.
      """
      self.server_timeoutSet(poll_interval)
      self.__stopping['ended'].clear()
      try:
         self.handle_request_loop()
      finally:
         self.__stopping['called']=False
         self.__stopping['ended'].set()

   def serve_forever(self, poll_interval=1):
      """ Alias for self.start(). """
      self.start(poll_interval=poll_interval)

   def server_timeoutSet(self, timeout):
      self.socket.settimeout(timeout)

   def server_timeoutGet(self):
      return self.socket.gettimeout()

   def handle_request(self, cbTimeout=None):
      """
      Try to handle one request.

      In main case, timeout for socket must be previously setted. This method handle timeout correctly.
      You can pass <cbTimeout> callback, that will be called on timeouts.
      """
      try:
         client_socket, client_address=self.socket.accept()
      except self._socketClass.timeout:
         if cbTimeout: return cbTimeout(self)
         else: return
      except self._socketClass.error, e:
         print 'SOCKET_ERROR:', e
         return
      # now processing request
      try:
         self.process_request(client_socket, client_address)
      except:
         self.shutdown_request(client_socket, client_address, logError=True)

   def handle_request_loop(self):
      """
      Main loop for server.

      This is as 'self.handle_request()' in cicle, but contain optimisations for burst performance.
      """
      _stopping=self.__stopping
      _sock=self.socket
      _sockError=self._socketClass.error
      _sockTimeout=self._socketClass.timeout
      _process_request=self.process_request
      _shutdown_request=self.shutdown_request
      while not _stopping['called']:
         try:
            client_socket, client_address=_sock.accept()
         except _sockTimeout: continue
         except _sockError, e:
            print 'SOCKET_ERROR:', e
            continue
         # now processing request
         try:
            _process_request(client_socket, client_address)
         except:
            _shutdown_request(client_socket, client_address, logError=True)
      _stopping['called']=False
      _stopping['ended'].set()

   def process_request(self, client_socket, client_address):
      """ Call handler_class. Can be overriden. """
      self._requestHandlerClass(client_socket, client_address, self)
      self.shutdown_request(client_socket, client_address, logError=False)

   def shutdown_request(self, client_socket, client_address, logError=False):
      """ Called to shutdown and close an individual client_socket. Also print traceback if needed. """
      try:
         #explicitly shutdown.  socket.close() merely releases
         #the socket and waits for GC to perform the actual close.
         client_socket.shutdown(self._socketClass.SHUT_WR)
      except self._socketClass.error:
         pass  #some platforms may raise ENOTCONN here
      client_socket.close()
      if logError:
         print 'Exception happened during processing of request from', client_address
         traceback.print_exc()  #! this goes to stderr

   def stop(self, timeout=None):
      """ Stop server's cicle and close listener. """
      self.__stopping['called']=True
      self.__stopping['ended'].wait()

   def shutdown(self, timeout=None):
      """ Alias for self.stop(). """
      self.stop(timeout=timeout)

   def logger(self, level, *args):
      l=self._log
      if not l: return
      elif l is True or isinstance(l, int):
         if l is not True and level>l: return
         _write=sys.stdout.write
         for i, s in enumerate(args):
            try: _write(s)
            except:
               try: _write(repr(s))
               except UnicodeEncodeError:
                  _write(s.encode('utf8'))
               except Exception, e:
                  _write('<UNPRINTABLE_DATA> %s'%e)
            if i<len(args)-1: _write(' ')
         _write('\n')
      elif hasattr(l, '__call__'): l(level, *args)

# def serveMultipleServers(servers, poll_interval=0.5):
#    """
#    Start multiple servers with one eventLoop.
#    """
#    # reset event
#    for s in servers:
#       s._StreamServerEx__shutdown_request=False
#       s._StreamServerEx__is_shut_down.clear()
#    # run main cicle
#    while len(servers):
#       # try handle requsets
#       r, _, _=servers[0]._wait_for_file_ready(servers, [], [], poll_interval)
#       if r:
#          for s in r:
#             if s in servers:
#                s._handle_request_noblock()
#       # try handle stopping-signals
#       servers2=[]
#       for s in servers:
#          if s._StreamServerEx__shutdown_request: s._StreamServerEx__is_shut_down.set()
#          else: servers2.append(s)
#       servers=servers2

class _SSLContext(object):
   """
   Wrapper that provides SSL-context and ability for patching sockets. Source from Werkzeug
   """

   try: import ssl
   except ImportError:
      class _SslDummy(object):
         def __getattr__(self, name):
            raise RuntimeError('SSL support unavailable')
      ssl=_SslDummy()

   def __init__(self, protocol=None):
      if protocol is None: protocol=self.ssl.PROTOCOL_SSLv23
      self._protocol = protocol
      self._certfile = None
      self._keyfile = None
      self._password = None

   def load_cert_chain(self, certfile, keyfile=None, password=None):
      self._certfile = certfile
      self._keyfile = keyfile or certfile
      self._password = password

   def wrap_socket(self, sock, **kwargs):
      return self.ssl.wrap_socket(sock, keyfile=self._keyfile, certfile=self._certfile, ssl_version=self._protocol, **kwargs)

   def is_ssl_error(self, error=None):
      """Checks if the given error (or the current one) is an SSL error."""
      exc_types=(self.ssl.SSLError,)
      try:
         from OpenSSL.SSL import Error
         exc_types+=(Error,)
      except ImportError: pass
      if error is None: error=sys.exc_info()[1]
      return isinstance(error, exc_types)

class ThreadedStreamServerEx(StreamServerEx):
   """
   Multi-threaded version of StreamServerEx, that allow to kill spawned threads.
   It also can be patched for using something, that emulate threads (greenlets for example), by passing <spawnThreadFunc>, <killThreadFunc> and <sleepFunc>.
   """

   daemon_threads=False
   multithread=True

   def __init__(self, bind_addr, handler_class, bind_and_activate=True, dispatcher=None, socketClass=None, eventClass=None, ssl_args=None, log=True, request_queue_size=None, spawnThreadFunc=None, killThreadFunc=None, sleepFunc=None):
      StreamServerEx.__init__(self, bind_addr, handler_class, bind_and_activate=bind_and_activate, dispatcher=dispatcher, socketClass=socketClass, eventClass=eventClass, ssl_args=ssl_args, log=log, request_queue_size=request_queue_size)
      self._spawnThread=spawnThreadFunc or self._spawnThreadDefault
      self._sleep=sleepFunc or self._sleep
      self._killThread=killThreadFunc
      self.software_version+=' (Threaded)'
      self._startedThreads={}

   def process_request_threaded(self, rId, client_socket, client_address):
      """ Same as in StreamServerEx, but as a thread. In addition, exception handling is done here. """
      try:
         self._requestHandlerClass(client_socket, client_address, self)
         self.shutdown_request(client_socket, client_address, logError=False)
      except Exception:
         self.shutdown_request(client_socket, client_address, logError=True)
      del self._startedThreads[rId]

   def process_request(self, client_socket, client_address):
      """ Start a new thread to process the request. """
      #generate request_id
      rId="_999999_"
      while(rId in self._startedThreads):
         rId='_'+str(int(random.random()*999999))+'_'
      #start new thread
      self._startedThreads[rId]=None
      t=self._spawnThread(target=self.process_request_threaded, args=(rId, client_socket, client_address), daemon=self.daemon_threads)
      self._startedThreads[rId]=t

   def stop(self, timeout=1):
      StreamServerEx.stop(self, timeout=timeout)
      #if timeout passed, we wait some time for processing requests and also try to kill them
      if timeout!=0 and len(self._startedThreads):
         #try to wait until processing requests not complited
         mytime=time.time()*1000.0
         timeout=None if timeout is None else timeout*1000
         while len(self._startedThreads):
            if (time.time()*1000.0-mytime)>=timeout: break
            self._sleep(0.3)
         if self._killThread and len(self._startedThreads):
            #try to kill processing requests
            errors=[]
            for rId in self._startedThreads:
               try:
                  self._killThread(self._startedThreads[rId])
               except Exception, e: errors.append(e)
            #! нужно вызвать ошибки, которые произошли
            if len(errors):
               print '!ERROR on killThread', errors

   def _spawnThreadDefault(self, target, args=None, kwargs=None, daemon=False):
      t=threading.Thread(target=target, args=args or [], kwargs=kwargs or {})
      t.daemon=daemon
      t.start()
      return t

def terminate_thread(thread):
   """
   Terminates a python thread from another thread. Source from http://stackoverflow.com/a/15274929

   :param thread: a threading.Thread instance
   """
   if not thread.isAlive(): return
   import ctypes
   tid=thread.ident
   tid=ctypes.c_long(tid)
   exc=SystemExit  #! возможно сначала лучше пробовать KeyboardInterrupt
   exc=ctypes.py_object(exc)
   res=ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, exc)
   if res==0:
      raise ValueError("nonexistent thread id")
   elif res>1:
      #if it returns a number greater than one, you're in trouble, and you should call it again with exc=NULL to revert the effect
      ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
      raise SystemError("PyThreadState_SetAsyncExc failed")

class WSGIRequestHandlerEx:
   """
   Extended implementation of WSGIRequestHandler, that also use some code from Werkzeug.
   """

   # Disable nagle algorithm for client socket, if True.
   disable_nagle_algorithm=False
   # A timeout to apply to the request socket, if not None.
   timeout=None

   server_version='wsgiEx/%s'%__version__  #inherit from WSGIRequestHandler
   default_request_version="HTTP/0.9"
   protocol_version="HTTP/1.0"

   def __init__(self, client_socket, client_address, server):
      self.client_address=client_address
      self.server=server
      self.version_string=' - '.join([self.server_version, self.server.software_version, sys_version])
      self.client_socket=client_socket
      if self.timeout is not None:
         self.client_socket.settimeout(self.timeout)
      if self.disable_nagle_algorithm:
         self.client_socket.setsockopt(self.server._socketClass.IPPROTO_TCP, self.server._socketClass.TCP_NODELAY, 1)
      try: self.handle()
      finally: self.finish()

   def finish(self):
      try: self.client_socket.close()
      except self.server._socketClass.error: pass

   def get_stderr(self):
      return sys.stderr

   def handle(self):
      """Handles a request ignoring dropped connections."""
      data=None
      self.close_connection=1
      try:
         """Handle multiple requests if necessary."""
         self.handle_one_request()
         while not self.close_connection:
            self.handle_one_request()
      except (self.server._socketClass.error, self.server._socketClass.timeout) as e:
         self.connection_dropped(e)
      except Exception:
         if self.server._ssl_context is None or not self.server._ssl_context.is_ssl_error(): raise
      return data

   def handle_one_request(self):
      """Handle a single HTTP request."""
      try:
         self.rfile=httpInputWrapper(self.client_socket, useUpper=True, storeOriginalName=False, flatValueFor={'EXPECT':'', 'CONNECTION':'', 'CONTENT-LENGTH':'', 'CONTENT-TYPE':''})
      except LongRequestError:  #so long request
         self.requestline=''
         self.request_version=''
         self.command=''
         self.send_error(414)
         return
      requestline=self.rfile._firstline
      if not requestline:
         self.close_connection=1
      elif self.parse_request(requestline):
         # serving request and generate response
         connexpect=self.headers['EXPECT'].lower() if 'EXPECT' in self.headers else ''
         if connexpect=='100-continue':
            self.client_socket.sendall(b'HTTP/1.1 100 Continue\r\n\r\n')
         #execute wsgi app
         env=self.get_environ()
         self.headers_set=[]
         self.headers_sent=[]
         data_iter=None
         try:
            data_iter=self.server._dispatcher(env, self.wsgi_start_response)
            _wsgi_write=self.wsgi_write
            for data in data_iter: _wsgi_write(data)
            if not self.headers_sent: _wsgi_write(b'')
         except KeyboardInterrupt: raise
         except (self.server._socketClass.error, self.server._socketClass.timeout) as e:
            self.connection_dropped(e, env)
         except Exception, e:
            if not self.headers_sent: del self.headers_set[:]
            self.close_connection=1
            self.log_error('Error on serving request as WSGI: '+getErrorInfo())
            self.send_error(500)
         #PEP3333 demand this
         if data_iter and hasattr(data_iter, 'close'): data_iter.close()

   def wsgi_write(self, data):
      assert self.headers_set, 'write() before start_response'
      if not self.headers_sent:
         status, response_headers=self.headers_sent[:]=self.headers_set
         try:
            code, msg=status.split(None, 1)
         except ValueError:
            code, msg=status, ""
         self.send_response(int(code), msg)
         isSended_contentLength=False
         isSended_server=False
         isSended_date=False
         _send_header=self.send_header
         for key, value in response_headers:
            _send_header(key, value)
            key=key.lower()
            if key=='content-length': isSended_contentLength=True
            elif key=='server': isSended_server=True
            elif key=='date': isSended_date=True
         # check sended headers
         if not isSended_contentLength:
            self.close_connection=1
            _send_header('Connection', 'close')
         if not isSended_server:
            _send_header('Server', self.version_string)
         if not isSended_date:
            _send_header('Date', date_time_string())
         # ending
         self.end_headers()
      assert isinstance(data, bytes), 'applications must write bytes'
      self.client_socket.sendall(data)

   def wsgi_start_response(self, status, response_headers, exc_info=None):
      if exc_info:
         try:
            if self.headers_sent:
               raise exc_info[0], exc_info[1], exc_info[2]
         finally: exc_info=None
      elif self.headers_set:
         raise AssertionError('Headers already set')
      assert isinstance(status, (str, unicode)), 'Status must be a string'
      assert len(status)>=4, 'Status must be at least 4 characters'
      assert int(status[:3]), 'Status message must begin w/3-digit code'
      assert status[3]==' ', 'Status message must have a space after code'
      self.headers_set[:]=[status, response_headers]
      return self.wsgi_write

   def parse_request(self, requestline):
      """
      Parse a request (internal).

      The results are in self.command, self.path, self.request_version and self.headers.
      Return True for success, False for failure; on failure, an error is sent back.
      """
      self.command=None  #set in case of error on the first line
      self.request_version=version=self.default_request_version
      self.close_connection=1
      self.requestline=requestline
      words=requestline.split(' ', 2)
      if len(words)==3:
         command, path, version=words
         if version[:5]!='HTTP/':
            self.send_error(400, "Bad request version (%r)" % version)
            return False
         try:
            base_version_number=version.split('/', 1)[1]
            version_number=base_version_number.split(".", 1)
            if len(version_number)!=2:
               raise ValueError
            version_number=int(version_number[0]), int(version_number[1])
         except (ValueError, IndexError):
            self.send_error(400, "Bad request version (%r)" % version)
            return False
         if version_number>=(1, 1) and self.protocol_version>="HTTP/1.1":
            self.close_connection=0
         if version_number>=(2, 0):
            self.send_error(505, "Invalid HTTP Version (%s)" % base_version_number)
            return False
      elif len(words)==2:
         command, path=words
         self.close_connection=1
         if command!='GET':
            self.send_error(400, "Bad HTTP/0.9 request type (%r)" % command)
            return False
      elif not words:
         return False
      else:
         self.send_error(400, "Bad request syntax (%r)" % requestline)
         return False
      self.command, self.path, self.request_version=command, path, version
      # parse headers and look for a Connection directive
      hh=self.headers=self.rfile._headers
      conntype=hh['CONNECTION'].lower() if 'CONNECTION' in hh else ''
      if conntype=='close':
         self.close_connection=1
      elif conntype=='keep-alive' and self.protocol_version>="HTTP/1.1":
         self.close_connection=0
      return True

   def connection_dropped(self, error, environ=None):
      """ Called if the connection was closed by the client. """
      pass

   def get_environ(self):
      if not self.client_address:
         client_addr='unrecognized'
      else:
         client_addr=self.client_address[0]
      env={}
      env['SERVER_NAME']=self.server.server_name
      env['GATEWAY_INTERFACE']='CGI/1.1'
      env['SERVER_PORT']=str(self.server.server_port)
      env['SCRIPT_NAME']=''
      env['wsgi.version']=(1, 0)
      env['wsgi.multithread']=self.server.multithread
      env['wsgi.multiprocess']=self.server.multiprocess
      env['wsgi.run_once']=False
      env['SERVER_PROTOCOL']=self.request_version
      env['REQUEST_METHOD']=self.command
      if '?' in self.path:
         path, query=self.path.split('?', 1)
         query=self.encoding_dance(query)  #solve some encoding's problems
      else:
         path, query=self.path, ''
      env['PATH_INFO']=self.encoding_dance(urllib.unquote(path))  #solve some encoding's problems
      env['QUERY_STRING']=query
      #! method "self.server._socketClass.getfqdn()" slow and also block greenlets
      # host=client_addr
      # try:
      #    host, _=self.client_address[:2]
      #    host=self.server._socketClass.getfqdn(host)
      # except ValueError: host=''
      # if host!=client_addr: env['REMOTE_HOST']=host
      env['REMOTE_ADDR']=client_addr
      env['SERVER_SOFTWARE']=self.version_string
      env['wsgi.input']=self.rfile
      env['wsgi.errors']=None  #! change to actual
      env['wsgi.url_scheme']='http' if self.server._ssl_context is None else 'https'
      #server-specific
      env['wsgiex.server_instance']=self.server
      env['wsgiex.handler_instance']=self
      # work with headers
      hh=self.headers
      env['CONTENT_TYPE']=hh['CONTENT-TYPE'] if 'CONTENT-TYPE' in hh else 'text/plain'
      length=hh['CONTENT-LENGTH'] if 'CONTENT-LENGTH' in hh else ''
      if length:
         env['CONTENT_LENGTH']=length
      # add other headers to environ
      for k in hh:
         kk=k.replace('-', '_')
         if kk in env: continue  #skip content-length, content-type, etc.
         v=hh[k]
         v=','.join(v) if len(v)>1 else v[0]
         env['HTTP_'+kk]=v
      return env

   def send_error(self, code, message=None):
      """ Send and log an error reply. """
      short, explain='???', '???'
      if code in self.httpResponseMap:
         short, explain=self.httpResponseMap[code]
      if message is None: message=short
      self.log_error("code %d, message %s"%(code, message))
      self.send_response(code, message)
      self.send_header("Content-Type", DEFAULT_ERROR_CONTENT_TYPE)
      self.send_header('Connection', 'close')
      self.end_headers()
      if self.command!='HEAD' and code>=200 and code not in (204, 304):
         # quote message to prevent Cross Site Scripting attacks
         content=DEFAULT_ERROR_MESSAGE%{'code':code, 'message':message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), 'explain':explain}
         self.client_socket.sendall(content)

   def send_response(self, code, message=None):
      """ Send the response header and log the response code. """
      self.log_request(code)
      if message is None:
         message=self.httpResponseMap[code][0] if code in self.httpResponseMap else ''
      if self.request_version!='HTTP/0.9':
         hdr="%s %d %s\r\n"%(self.protocol_version, code, message)
         self.client_socket.sendall(hdr.encode('ascii'))

   def send_header(self, key, val):
      """ Send a MIME header. """
      if self.request_version!='HTTP/0.9':
         self.client_socket.sendall(b"%s: %s\r\n"%(key, val))
      if key.lower()=='connection':
         val=val.lower()
         if val=='close':
            self.close_connection=1
         elif val=='keep-alive':
            self.close_connection=0

   def end_headers(self):
      """ Send the blank line ending the MIME headers. """
      if self.request_version!='HTTP/0.9':
         self.client_socket.sendall(b"\r\n")

   def decoding_dance(self, s, charset='utf-8', errors='replace'):
      return s.decode(charset, errors)

   def encoding_dance(self, s, charset='utf-8', errors='replace'):
      if isinstance(s, bytes): return s
      return s.encode(charset, errors)

   def log_error(self, msg):
      s="<%s> %s"%(self.client_address[0], msg)
      self.server.logger(1, s)

   def log_request(self, code):
      s='<%s> %s "%s"'%(self.client_address[0], self.requestline, code)
      self.server.logger(4, s)

   httpResponseMap={
      100: ('Continue', 'Request received, please continue'),
      101: ('Switching Protocols', 'Switching to new protocol; obey Upgrade header'),

      200: ('OK', 'Request fulfilled, document follows'),
      201: ('Created', 'Document created, URL follows'),
      202: ('Accepted', 'Request accepted, processing continues off-line'),
      203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
      204: ('No Content', 'Request fulfilled, nothing follows'),
      205: ('Reset Content', 'Clear input form for further input.'),
      206: ('Partial Content', 'Partial content follows.'),

      300: ('Multiple Choices', 'Object has several resources -- see URI list'),
      301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
      302: ('Found', 'Object moved temporarily -- see URI list'),
      303: ('See Other', 'Object moved -- see Method and URL list'),
      304: ('Not Modified', 'Document has not changed since given time'),
      305: ('Use Proxy', 'You must use proxy specified in Location to access this resource.'),
      307: ('Temporary Redirect', 'Object moved temporarily -- see URI list'),

      400: ('Bad Request', 'Bad request syntax or unsupported method'),
      401: ('Unauthorized', 'No permission -- see authorization schemes'),
      402: ('Payment Required', 'No payment -- see charging schemes'),
      403: ('Forbidden', 'Request forbidden -- authorization will not help'),
      404: ('Not Found', 'Nothing matches the given URI'),
      405: ('Method Not Allowed', 'Specified method is invalid for this resource.'),
      406: ('Not Acceptable', 'URI not available in preferred format.'),
      407: ('Proxy Authentication Required', 'You must authenticate with this proxy before proceeding.'),
      408: ('Request Timeout', 'Request timed out; try again later.'),
      409: ('Conflict', 'Request conflict.'),
      410: ('Gone', 'URI no longer exists and has been permanently removed.'),
      411: ('Length Required', 'Client must specify Content-Length.'),
      412: ('Precondition Failed', 'Precondition in headers is false.'),
      413: ('Request Entity Too Large', 'Entity is too large.'),
      414: ('Request-URI Too Long', 'URI is too long.'),
      415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
      416: ('Requested Range Not Satisfiable', 'Cannot satisfy request range.'),
      417: ('Expectation Failed', 'Expect condition could not be satisfied.'),

      500: ('Internal Server Error', 'Server got itself in trouble'),
      501: ('Not Implemented', 'Server does not support this operation'),
      502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
      503: ('Service Unavailable', 'The server cannot process the request due to a high load'),
      504: ('Gateway Timeout', 'The gateway server did not receive a timely response'),
      505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
   }

def getErrorInfo():
   """
   This method return info about last exception.

   :return str:
   """
   tArr=inspect.trace()[-1]
   fileName=tArr[1]
   lineNo=tArr[2]
   exc_obj=sys.exc_info()[1]
   s='%s:%s > %s'%(fileName, lineNo, exc_obj)
   sys.exc_clear()
   return s


def date_time_string(timestamp=None):
   """ Return the current date and time formatted for a message header. """
   if timestamp is None:
      timestamp=time.time()
   year, month, day, hh, mm, ss, wd, _, _=time.gmtime(timestamp)
   weekdayname=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
   monthname=(None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
   s="%s, %02d %3s %4d %02d:%02d:%02d GMT"%(weekdayname[wd], day, monthname[month], year, hh, mm, ss)
   return s
