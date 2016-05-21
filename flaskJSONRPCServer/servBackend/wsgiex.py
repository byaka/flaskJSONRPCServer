#!/usr/bin/env python
# -*- coding: utf-8 -*-

__ver_major__ = 0
__ver_minor__ = 2
__ver_patch__ = 1
__ver_sub__ = ""
__version__ = "%d.%d.%d" % (__ver_major__, __ver_minor__, __ver_patch__)
"""
This package provide extended versions of StreamServer, WSGIRequestHandler and some additions.
It doesn't has any dependences and use some parts of Werkzeug's source.

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

import sys, os, socket, select, errno, threading, random, time, fcntl
import wsgiref.simple_server
import SocketServer
import BaseHTTPServer

class StreamServerEx(SocketServer.TCPServer, object):
   """
   Extended impelementation of standart Python BaseHTTPServer.HTTPServer, that supports UnixDomainSockets and passed sockets. It also supports SSL and overloading Socket's class and Select's class (for simple using with gevent, for example) by passing <socketClass>, <selectClass>, <eventClass>.
   """

   software_version='StreamServerEx/%s'%__version__
   multithread=False
   multiprocess=False
   allow_reuse_address=1
   request_queue_size=256
   socket_type=None
   _uds=False
   _socketPassed=False
   _fdPassed=False
   _spawnThread=None
   _killThread=None
   _sleep=time.sleep

   def __init__(self, bind_addr, RequestHandlerClass=None, bind_and_activate=True, dispatcher=None, socketClass=None, selectClass=None, eventClass=None, ssl_args=None, log=True, request_queue_size=None):
      if not RequestHandlerClass and not dispatcher:
         raise ValueError('You must set <RequestHandlerClass> or <dispatcher>')
      # select mode
      if isinstance(bind_addr, tuple):
         if len(bind_addr)!=2:
            raise ValueError('Wrong length of attr <bind_addr>, must be 2')
         elif isinstance(bind_addr[0], int): #file-descriptor
            self._fdPassed=True
            self._uds=not(bind_addr[1])
         else: pass #ip and port
      elif isinstance(bind_addr, (str, unicode)): #path to UDS
         self._uds=True
      else: #socket object
         self._socketPassed=True
      #configure server
      self._log=log
      self.request_queue_size=request_queue_size or self.request_queue_size
      self._dispatcher=dispatcher
      self._requestHandlerClass=RequestHandlerClass or WSGIRequestHandlerEx
      self._socketClass=socketClass or socket
      self._selectClass=selectClass or select
      self._eventClass=eventClass or threading.Event
      self._spawnThread=self._spawnThread or self._spawnThreadDefault
      self._killThread=self._killThread or None
      self._sleep=self._sleep or time.sleep
      self.address_family=self._socketClass.AF_UNIX if self._uds else self._socketClass.AF_INET
      self.socket_type=self.socket_type or self._socketClass.SOCK_STREAM
      self._bind_addr=None if self._socketPassed else bind_addr
      SocketServer.BaseServer.__init__(self, bind_addr, self._requestHandlerClass)
      self.__is_shut_down=self._eventClass()
      self.__shutdown_request=False
      if self._fdPassed: #create socket from FD
         if not hasattr(self._socketClass, 'fromfd'):
            raise NotImplementedError('Creating socket from FD not implemented in given class %s'%self._socketClass)
         self.socket=self._socketClass.socket.fromfd(bind_addr[0], self.address_family, self.socket_type)
      elif not self._socketPassed: #create new socket
         if self._uds and os.path.exists(bind_addr): os.remove(bind_addr)
         self.socket=self._socketClass.socket(self.address_family, self.socket_type)
      else: #only set passed socket
         self.address_family=None
         self.socket=bind_addr
         self.server_name=''
         self.server_port=''
      # now we can bind if needed
      if bind_and_activate:
         try:
            if not self._socketPassed and not self._fdPassed: self.server_bind()
            if not self._fdPassed: self.server_activate() #! проверить
            # self.socket.setblocking(0)
         except:
            self.server_close()
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
      # construct env
      self.setup_environ()

   def setup_environ(self):
      # Set up base environment
      self.base_environ={}
      self.base_environ['SERVER_NAME']=self.server_name
      self.base_environ['GATEWAY_INTERFACE']='CGI/1.1'
      self.base_environ['SERVER_PORT']=str(self.server_port)
      self.base_environ['SERVER_SOFTWARE']=self.software_version
      self.base_environ['REMOTE_HOST']=''
      self.base_environ['CONTENT_LENGTH']=''
      self.base_environ['SCRIPT_NAME'] = ''

   def __del__(self):
      self.server_close()

   def _server_reuse_address(self):
      if self.allow_reuse_address:
         self.socket.setsockopt(self._socketClass.SOL_SOCKET, self._socketClass.SO_REUSEADDR, 1)

   def server_bind(self):
      # SocketServer.TCPServer.server_bind(self)
      self._server_reuse_address()
      self.socket.bind(self._bind_addr)
      # Tell the server socket file descriptor to destroy itself when this program ends.
      socketFlags=fcntl.fcntl(self.socket.fileno(), fcntl.F_GETFD)
      socketFlags|=fcntl.FD_CLOEXEC
      fcntl.fcntl(self.socket.fileno(), fcntl.F_SETFD, socketFlags)
      #inherit from BaseHTTPServer.HTTPServer and adapted for using with UDS
      if self._uds:
         self.server_name=self._bind_addr
         self.server_port=''
      else:
         host, port=self.socket.getsockname()[:2]
         self.server_name=self._socketClass.getfqdn(host)
         self.server_port=port
      # re-construct env
      self.setup_environ()

   def start(self):
      self.serve_forever(self, poll_interval=0.5)
      # while not self.__shutdown_request: self.handle_request()

   def _wait_for_file_ready(self, *args):
      while True:
         try:
            return self._selectClass.select(*args)
         except (OSError, self._selectClass.error) as e:
            if e.args[0]!=errno.EINTR: raise

   def serve_forever(self, poll_interval=0.5):
      """Handle one request at a time until shutdown."""
      self.__is_shut_down.clear()
      try:
         while not self.__shutdown_request:
            #коммент из оригинального SocketServer.BaseServer
            """
            Consider using another file descriptor or connecting to the socket to wake this up instead of polling. Polling reduces our responsiveness to a shutdown request and wastes cpu at all other times.
            """
            r, _, _=self._wait_for_file_ready([self], [], [], poll_interval)
            if self in r:
               self._handle_request_noblock()
      finally:
         self.__shutdown_request=False
         self.__is_shut_down.set()

   def handle_request(self):
      """Handle one request, possibly blocking. Respects self.timeout."""
      timeout=self.socket.gettimeout()
      if timeout is None: timeout=self.timeout
      elif self.timeout is not None:
         timeout=min(timeout, self.timeout)
      r, _, _=self._wait_for_file_ready([self], [], [], timeout)
      if not r:
         return self.handle_timeout()
      elif self in r:
         self._handle_request_noblock()

   def _handle_request_noblock(self):
      """Handle one request, without blocking.

      I assume that select.select has returned that the socket is
      readable before this function was called, so there should be
      no risk of blocking in get_request().
      """
      try:
         request, client_address=self.get_request()
      except self._socketClass.error:
         return
      if self.verify_request(request, client_address):
         try:
            self.process_request(request, client_address)
         except:
            self.handle_error(request, client_address)
            self.shutdown_request(request)
      else:
         self.shutdown_request(request)

   def handle_error(self, request, client_address):
      # if self.passthrough_errors: raise
      return SocketServer.TCPServer.handle_error(self, request, client_address)

   def shutdown_request(self, request):
      """Called to shutdown and close an individual request."""
      try:
         #explicitly shutdown.  socket.close() merely releases
         #the socket and waits for GC to perform the actual close.
         request.shutdown(self._socketClass.SHUT_WR)
      except self._socketClass.error:
         pass #some platforms may raise ENOTCONN here
      self.close_request(request)

   def stop(self, timeout=None):
      self.__shutdown_request=True
      self.__is_shut_down.wait()

   def shutdown(self):
      self.stop()

   def _spawnThreadDefault(self, target, args=None, kwargs=None, daemon=False):
      t=threading.Thread(target=target, args=args or [], kwargs=kwargs or {})
      t.daemon=daemon
      t.start()
      return t

class _SSLContext(object):
   """
   Wrapper that provides SSL-context and ability for patching sockets. Source from Werkzeug
   """

   try: import ssl
   except ImportError:
      class _SslDummy(object):
         def __getattr__(self, name): raise RuntimeError('SSL support unavailable')
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
   Multi-threaded version of StreamServerEx, that use pool and allow to kill spawned threads.
   It also can be patched for using something, that emulate threads by passing <spawnThreadFunc>, <killThreadFunc> and <sleepFunc>.
   """

   daemon_threads=False
   _startedThreads={}
   multithread=True

   def __init__(self, bind_addr, RequestHandlerClass=None, bind_and_activate=True, dispatcher=None, socketClass=None, selectClass=None, eventClass=None, ssl_args=None, log=True, request_queue_size=None, spawnThreadFunc=None, killThreadFunc=None, sleepFunc=None):
      StreamServerEx.__init__(self, bind_addr, RequestHandlerClass=RequestHandlerClass, bind_and_activate=bind_and_activate, dispatcher=dispatcher, socketClass=socketClass, selectClass=selectClass, eventClass=eventClass, ssl_args=ssl_args, log=log, request_queue_size=request_queue_size)
      if spawnThreadFunc: self._spawnThread=spawnThreadFunc
      if killThreadFunc: self._killThread=killThreadFunc
      if sleepFunc: self._sleep=sleepFunc
      self.software_version+=' (Threaded)'

   def process_request_thread(self, rId, request, client_address):
      """Same as in BaseServer but as a thread. In addition, exception handling is done here."""
      try:
         self.finish_request(request, client_address)
         self.shutdown_request(request)
      except Exception:
         self.handle_error(request, client_address)
         self.shutdown_request(request)
      del self._startedThreads[rId]

   def process_request(self, request, client_address):
      """Start a new thread to process the request."""
      #generate request_id
      rId=0
      while(not rId or rId in self._startedThreads):
         rId='_'+str(int(random.random()*999999))+'_'
      #start new thread
      self._startedThreads[rId]=None
      t=self._spawnThread(target=self.process_request_thread, args=(rId, request, client_address), daemon=self.daemon_threads)
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
               try: self._killThread(self._startedThreads[rId])
               except Exception, e: errors.append(e)
            #! нужно вызвать ошибки, которые произошли
            if len(errors):
               print '!ERROR on killThread', errors

def terminate_thread(thread):
   """
   Terminates a python thread from another thread. Source from http://stackoverflow.com/a/15274929

   :param thread: a threading.Thread instance
   """
   if not thread.isAlive(): return
   import ctypes
   tid=thread.ident
   tid=ctypes.c_long(tid)
   exc=SystemExit #! возможно сначала лучше пробовать KeyboardInterrupt
   exc=ctypes.py_object(exc)
   res=ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, exc)
   if res==0:
      raise ValueError("nonexistent thread id")
   elif res>1:
      #if it returns a number greater than one, you're in trouble, and you should call it again with exc=NULL to revert the effect
      ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
      raise SystemError("PyThreadState_SetAsyncExc failed")

class WSGIRequestHandlerEx(wsgiref.simple_server.WSGIRequestHandler, object):
   """
   Extended implementation of WSGIRequestHandler, that also use some code from Werkzeug.
   """

   server_version='wsgiEx/%s'%__version__ #inherit from WSGIRequestHandler
   def get_stderr(self): return None #inherit from WSGIRequestHandler

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
      self.raw_requestline=self.rfile.readline()
      if not self.raw_requestline: self.close_connection=1
      elif self.parse_request():
         return self.serve_request()

   def connection_dropped(self, error, environ=None):
      """Called if the connection was closed by the client.  By default nothing happens."""

   def version_string(self):
      return ' - '.join([self.server_version, self.server.software_version, wsgiref.simple_server.sys_version])

   def address_string(self):
      try:
         host, port=self.client_address[:2]
         return self.server._socketClass.getfqdn(host)
      except ValueError: return ''

   def serve_request(self):
      """Here we serving request and generate response"""
      if self.headers.get('Expect', '').lower().strip()=='100-continue':
         self.wfile.write(b'HTTP/1.1 100 Continue\r\n\r\n')
      env=self.get_environ()
      headers_set=[]
      headers_sent=[]
      #callback 'write'
      def write(data):
         assert headers_set, 'write() before start_response'
         if not headers_sent:
            status, response_headers=headers_sent[:]=headers_set
            try: code, msg=status.split(None, 1)
            except ValueError: code, msg=status, ""
            self.send_response(int(code), msg)
            header_keys=set()
            for key, value in response_headers:
               self.send_header(key, value)
               header_keys.add(key.lower())
            if 'content-length' not in header_keys:
               self.close_connection=1
               self.send_header('Connection', 'close')
            if 'server' not in header_keys:
               self.send_header('Server', self.version_string())
            if 'date' not in header_keys:
               self.send_header('Date', self.date_time_string())
            self.end_headers()
         assert isinstance(data, bytes), 'applications must write bytes'
         self.wfile.write(data)
         self.wfile.flush()
      #callback 'start_response'
      def start_response(status, response_headers, exc_info=None):
         if exc_info:
            try:
               if headers_sent:
                  raise exc_info[0], exc_info[1], exc_info[2]
            finally: exc_info=None
         elif headers_set:
            raise AssertionError('Headers already set')
         assert isinstance(status, (str, unicode)), 'Status must be a string'
         assert len(status)>=4, 'Status must be at least 4 characters'
         assert int(status[:3]), 'Status message must begin w/3-digit code'
         assert status[3]==' ', 'Status message must have a space after code'
         headers_set[:]=[status, response_headers]
         return write
      #execute dispatcher
      data_iter=None
      try:
         data_iter=self.server._dispatcher(env, start_response)
         for data in data_iter: write(data)
         if not headers_sent: write(b'')
      except KeyboardInterrupt: raise
      except (self.server._socketClass.error, self.server._socketClass.timeout) as e:
         self.connection_dropped(e, env)
      except Exception, e:
         if not headers_sent: del headers_set[:]
         self.close_connection=1
         self.send_error(500)
         self.log_error('Error on "serve_request()":%s'%e)
      #PEP3333 demand this
      if hasattr(data_iter, 'close'): data_iter.close()

   def get_environ(self):
      if not self.client_address: self.client_address='unrecognized'
      env=wsgiref.simple_server.WSGIRequestHandler.get_environ(self)
      env['wsgi.version']=(1, 0)
      env['SERVER_SOFTWARE']=self.version_string()
      env['wsgi.multithread']=self.server.multithread
      env['wsgi.multiprocess']=self.server.multiprocess
      env['wsgi.input']=self.rfile
      env['wsgi.errors']=None #! change to actual
      env['wsgi.run_once']=False #! change to actual
      env['wsgi.url_scheme']='http' if self.server._ssl_context is None else 'https'
      #solve some encoding's problems
      env['PATH_INFO']=self.encoding_dance(env['PATH_INFO'])
      env['QUERY_STRING']=self.encoding_dance(env['PATH_INFO'])
      #server-specific
      env['wsgiex.server_instance']=self.server
      env['wsgiex.handler_instance']=self
      return env

   def decoding_dance(self, s, charset='utf-8', errors='replace'):
      return s.decode(charset, errors)

   def encoding_dance(self, s, charset='utf-8', errors='replace'):
      if isinstance(s, bytes): return s
      return s.encode(charset, errors)

   def send_response(self, code, message=None):
      """Send the response header and log the response code."""
      self.log_request(code)
      if message is None:
         message=code in self.responses and self.responses[code][0] or ''
      if self.request_version!='HTTP/0.9':
         hdr="%s %d %s\r\n"%(self.protocol_version, code, message)
         self.wfile.write(hdr.encode('ascii'))

   # def log_error(self, format, *args): pass
   # def log_request(self, format, *args): pass
   def log_message(self, format, *args):
      if not self.server._log: return
      BaseHTTPServer.BaseHTTPRequestHandler.log_message(self, format, *args)
