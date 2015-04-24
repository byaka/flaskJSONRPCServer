# flaskJSONRPCServer
This library is an implementation of the JSON-RPC specification. It supports only 2.0 specification for now, which includes batch submission, keyword arguments, etc.

## Requirements
 - Python >=2.6
 - Flask >= 0.10 (not tested with older version)
 - Gevent >= 1.0 (optionally)

## Pros

 - Lib tested over **highload** (>=60 connections per second, 24/7 and it's not simulation) with **Gevent** enabled and no stability issues or memory leak (this is why i'm wrote this library)
 - Auto **CORS**
 - Simple switching to **Gevent** as backend
 - Auto fallback to **JSONP** on GET requests (for old browsers, that don't support CORS like **IE**<10)
 - Dispatchers can simply get info about connection (**IP**, **Cookies**, **Headers**)
 - Dispatchers can simply set **Cookies**, change output **Headers**, change output format for **JSONP** requests
 - Lib can be simply integreted with another **Flask** app on the same IP:PORT

## Cons
 - No **documentation**, only examples below (sorry, i not have time for now)
 - Lib not handle **Notification** requests fully (for now client waiting, while server processes requests)
 - Lib not has **decorators**, so it not a "Flask-way" (this can be simply added, but i not use decorators, sorry)

## Examples
Simple server
```python
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

```

## License
It is licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0.html).
