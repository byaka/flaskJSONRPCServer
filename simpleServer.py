# -*- coding: utf-8 -*-
import sys, time, random
from flaskJSONRPCServer import flaskJSONRPCServer

class mySharedMethods:
   def random(self, mult=65536):
      # Sipmly return random value (0..mult)
      return int(random.random()*mult)

def echo(data='Hello world!'):
   # Simply echo
   return data

def myip(_connection=None):
   # Return client's IP
   return 'Hello, %s!'%(_connection.ip)

def setcookie(_connection=None):
   # Set cookie to client
   _connection.cookiesOut.append({'name':'myTestCookie', 'value':'Your IP is %s'%_connection.ip})
   return 'Setted'

def block():
   # Test for notification request. When it fully implemented, client must  not wait for compliting this function
   time.sleep(10)
   return 'ok'

if __name__=='__main__':
   print 'Running api..'
   # Creating instance of server
   #    <blocking>  set is this server async
   #    <cors>      switch auto CORS support
   #    <gevent>    switch to using Gevent as backend
   #    <debug>     switch to logging connection's info from Flask
   #    <log>       switch to logging debug info from flaskJSONRPCServer
   #    <fallback>  switch auto fallback to JSONP on GET requests
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=False, debug=False, log=True, fallback=True)
   # Register dispatcher for all methods of instance
   server.registerInstance(mySharedMethods(), path='/api')
   # Register dispatchers for single functions
   server.registerFunction(setcookie, path='/api')
   server.registerFunction(echo, path='/api')
   server.registerFunction(block, path='/api')
   server.registerFunction(myip, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
