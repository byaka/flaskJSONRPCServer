|PyPI version| |PyPI downloads| |License|

flaskJSONRPCServer
------------------

This library is an implementation of the JSON-RPC specification. It supports only 2.0 specification for now, which includes batch submission, keyword arguments, etc.

Comments, bug reports
---------------------

flaskJSONRPCServer resides on **github**. You can file issues or pull requests `there <https://github.com/byaka/flaskJSONRPCServer/issues>`_.

Requirements
------------

-  Python >=2.6
-  Flask >= 0.10 (not tested with older version)
-  Gevent >= 1.0 (optionally)

Pros
----

-  Lib tested over **highload** (>=60 connections per second, 24/7 and it's not simulation) with **Gevent** enabled and no stability issues or memory leak (this is why i'm wrote this library)
-  Auto **CORS**
-  Simple switching to **Gevent** as backend
-  Auto fallback to **JSONP** on GET requests (for old browsers, that don't support CORS like **IE**\ <10)
-  Dispatchers can simply get info about connection (**IP**, **Cookies**, **Headers**)
-  Dispatchers can simply set **Cookies**, change output **Headers**, change output format for **JSONP** requests
-  Lib can be simply integrated with another **Flask** app on the same IP:PORT
-  Lib can be simply integrated with another **Flask** app on the same IP:PORT
-  Lib fully support **Notification** requests (see example/notify.py)
-  Lib supports **restarting** server (see example/restart.py)
-  Lib supports **hot reloading** of API (see example/reloadAndReplace.py)
-  Lib supports **multiple servers** in one app (see example/multiple.py)
-  Lib supports **merging** with another WSGI app (see example/mergeFlaskApp.py)

Cons
----

-  No **documentation**, only examples in package (sorry, i not have time for now)
-  Lib not has **decorators**, so it not a "Flask-way" (this can be simply added, but i not use decorators, sorry)

Install
-------

``pip install flaskJSONRPCServer``

Examples
--------

Simple server

.. code:: python

    import sys, time, random
    from flaskJSONRPCServer import flaskJSONRPCServer

    class mySharedMethods:
       def random(self, mult=65536):
          # Sipmly return random value (0..mult)
          return int(random.random()*mult)
          
    class mySharedMethods2:
       def random(self):
          # Sipmly return random value (0..mult)
          return round(random.random()*1, 1)

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

    def stats(_connection=None):
       #return server's speed stats
       return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

    def big(_connection=None):
       _connection.allowCompress=True #allow compression for this method
       s="""
    ... large data here ...
       """
       return s

    if __name__=='__main__':
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

License
-------

It is licensed under the Apache License, Version 2.0
(`read <http://www.apache.org/licenses/LICENSE-2.0.html>`_).

.. |PyPI version| image:: https://img.shields.io/pypi/v/flaskJSONRPCServer.svg
   :target: https://pypi.python.org/pypi/flaskJSONRPCServer
.. |PyPI downloads| image:: https://img.shields.io/pypi/dm/flaskJSONRPCServer.svg
   :target: https://pypi.python.org/pypi/flaskJSONRPCServer
.. |License| image:: https://img.shields.io/pypi/l/flaskJSONRPCServer.svg
   :target: http://www.apache.org/licenses/LICENSE-2.0.html
