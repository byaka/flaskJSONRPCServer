[![PyPI version](https://img.shields.io/pypi/v/flaskJSONRPCServer.svg)](https://pypi.python.org/pypi/flaskJSONRPCServer)
[![PyPI downloads](https://img.shields.io/pypi/dm/flaskJSONRPCServer.svg)](https://pypi.python.org/pypi/flaskJSONRPCServer)
[![License](https://img.shields.io/pypi/l/flaskJSONRPCServer.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)


# flaskJSONRPCServer
This library is an extended implementation of server for JSON-RPC protocol. It supports only json-rpc 2.0 specification for now, which includes batch submission, keyword arguments, notifications, etc.

### Comments, bug reports
flaskJSONRPCServer resides on **github**. You can file issues or pull requests [there](https://github.com/byaka/flaskJSONRPCServer/issues).

### Requirements
 - **Python2.6** or **Python2.7**
 - **Flask** >= 0.10 (not tested with older version)
 - **Gevent** >= 1.0 (optionally, but recommended)

####[How to install](#install)
####[About Gevent and async](#gevent-and-async)
####[About hot-reloading](#hot-reloading)
####[Simple example](#examples)
####[Licensing](#license)

### Pros
 - Lib ready for **production**, we use it in some products
 - Lib tested over **"highload"** (over 60 connections per second, 24/7 and it's not simulation) with **Gevent** enabled and no stability issues or memory leak (this is why i'm wrote this library)
 - Auto **CORS**
 - Simple switching to **Gevent** as backend
 - Auto fallback to **JSONP** on GET requests (for old browsers, that don't support CORS like **IE**<10)
 - Dispatchers can simply get info about connection (**IP**, **Cookies**, **Headers**)
 - Dispatchers can simply set **Cookies**, change output **Headers**, change output format for **JSONP** requests
 - Lib fully support **Notification** requests (see _example/notify.py_)
 - Lib supports **restarting** server (see _example/restart.py_)
 - Lib supports **hot-reloading** of API (see _example/hotReload1.py_, _example/hotReload2.py_)
 - Lib supports **multiple servers** in one app (see _example/multiple.py_)
 - Lib supports **merging** with another WSGI app on the same IP:PORT (see _example/mergeFlaskApp.py_)
 - Lib supports different **execution-backends**, for example multiprocessing (see _example/parallelExecuting.py_)
 - Lib supports **locking** (you can lock all server or specific dispatchers)
 - Lib supports different **serializing-backends** so you can implement any protocol, not only JSON
 - Lib supports **individual settings** for different dispatchers. For example one of them can be processed with parallel (multiprocess) backend, other with standard processing
 - Lib collects self **speed-stats**

### Cons
 - No **documentation**, only examples in package (sorry, i not have time for now)
 - Lib not has **decorators**, so it not a "Flask-way" (this can be simply added, but i not use decorators, sorry)

### Install
```pip install flaskJSONRPCServer```

### Gevent and async
Some server’s methods (like JSON processing or compression) not supported greenlets switching while processing. It can be big performance problem on highload. I start to implement functionality to solve this. Please see [experimental package](https://github.com/byaka/flaskJSONRPCServer/blob/with_parallel_executing/flaskJSONRPCServer/experimental/README.md).

### Hot-reloading
You can overload source of server without stopping.
```python
server.reload(data, clearOld=False)
```
Flag ``<clearOld>`` will remove all earlier existing dispatchers.

This operation safe, if something goes wrong, lib restore previous source. While reloading, server stop processing requests, but not reject them. Server handle all requests, and when reloading completed, all handled requests will be processed. It also wait for completing processing requests before start reloading and you can pass ``<timeout>`` for this waiting. Also you can pass ``<processingDispatcherCountMax>`` and server will not wait for given number of processed requests.

When reloading, you can change source, merge new variables with old and many more.

```python
data=[
   {'dispatcher':'testForReload1', 'scriptPath':server._getScriptPath(True), 'isInstance':False,'overload':[{'globalVar1':globalVar1}, callbackForManualOverload], 'path':'/api'}
]
```

For now overloading supports for any dispatcher or several dispatchers separately (you can fully change all dispatcher's settings and of course source and variables).

When you reload dispatcher and give path for file (of course it can be same file as "main"), this file imported. Then lib overloaded variables and attributes you give and replace old dispatcher with new from this module. If you give one path for several dispatchers, they all work in one imported file (in this case file will import one time only, not for every dispatcher).

If you need to overload some objects, that not dispatchers but used in them, you simply can do this with callback.

```python
def callbackForManualOverload(server, module, dispatcher):
   # overload globals also
   for k in dir(module):
      globals()[k]=getattr(module, k)
```
This code overload all global variables and replace them with variables from just imported file. In future i add simple method for reloading all source of server.

### Examples
Simple server. More examples you can find in directory _example/_

```python
import sys, time, random
from flaskJSONRPCServer import flaskJSONRPCServer

class mySharedMethods:
   def random(self):
      # Sipmly return random value (0..mult)
      return int(random.random()*65536)

class mySharedMethods2:
   def random(self):
      # Sipmly return random value (0..mult)
      return round(random.random()*1, 1)

def echo(data='Hello world!'):
   # Simply echo
   return data
echo._alias='helloworld' #setting alias for method

def myip(_connection=None):
   # Return client's IP
   return 'Hello, %s!'%(_connection.ip)

def setcookie(_connection=None):
   # Set cookie to client
   print _connection.cookies
   _connection.cookiesOut.append({'name':'myTestCookie', 'value':'Your IP is %s'%_connection.ip, 'domain':'byaka.name'})
   return 'Setted'

def stats(_connection=None):
   #return server's speed stats
   return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

def big(_connection=None):
   _connection.allowCompress=True #allow compression for this method only
   s="""
... large data here ...
   """
   return s

big._alias=['bigdata', 'compressed'] #setting alias for method

if __name__=='__main__':
   print 'Running api..'
   # Creating instance of server
   #    <blocking>         switch server to sync mode when <gevent> is False
   #    <cors>             switch auto CORS support
   #    <gevent>           switch to using Gevent as backend
   #    <debug>            switch to logging connection's info from Flask
   #    <log>              switch to logging debug info from flaskJSONRPCServer
   #    <fallback>         switch auto fallback to JSONP on GET requests
   #    <allowCompress>    switch auto compression
   #    <compressMinSize>  set min limit for compression
   #    <tweakDescriptors> set descriptor's limit for server
   #    <jsonBackend>      set JSON backend. Auto fallback to native when problems
   #    <notifBackend>     set backend for Notify-requests
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=False, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000])
   # Register dispatcher for all methods of instance
   server.registerInstance(mySharedMethods(), path='/api')
   # same name, but another path
   server.registerInstance(mySharedMethods2(), path='/api2')
   # Register dispatchers for single functions
   server.registerFunction(setcookie, path='/api')
   server.registerFunction(echo, path='/api')
   server.registerFunction(myip, path='/api')
   server.registerFunction(big, path='/api')
   server.registerFunction(stats, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620

```

### License
It is licensed under the Apache License, Version 2.0 ([read](http://www.apache.org/licenses/LICENSE-2.0.html)).
