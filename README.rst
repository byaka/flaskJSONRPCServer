|python27| |License| |PyPI version| |PyPI downloads|

flaskJSONRPCServer
==================

This library is an extended implementation of server for JSON-RPC
protocol. It supports only json-rpc 2.0 specification for now, which
includes batch submission, keyword arguments, notifications, etc.

Comments, bug reports
~~~~~~~~~~~~~~~~~~~~~

flaskJSONRPCServer resides on **github**. You can file issues or pull
requests `there <https://github.com/byaka/flaskJSONRPCServer/issues>`__.

Requirements
~~~~~~~~~~~~

-  **Python2.6** or **Python2.7**
-  **Flask** >= 0.10 (not tested with older version)
-  **Gevent** >= 1.0 (optionally, but recommended)

`How to install <#install>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Documentation <https://byaka.github.io/flaskJSONRPCServer-docs/>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Simple example <#examples>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Licensing <#license>`__
^^^^^^^^^^^^^^^^^^^^^^^^

Pros
~~~~

-  Lib ready for **production**, we use it in some products
-  Lib tested over **"highload"** (over 60 connections per second, 24/7
   and it's not simulation) with **Gevent** enabled and no stability
   issues or memory leak (this is why i'm wrote this library)
-  Auto **CORS**
-  Simple switching to **Gevent** as backend
-  Auto fallback to **JSONP** on GET requests (for old browsers, that
   don't support CORS like **IE**\ <10)
-  Dispatchers can simply get info about connection (**IP**,
   **Cookies**, **Headers**)
-  Dispatchers can simply set **Cookies**, change output **Headers**,
   change output format for **JSONP** requests
-  Lib fully support **Notification** requests (see *example/notify.py*)
-  Lib supports **restarting** server (see *example/restart.py*)
-  Lib supports **hot-reloading** of API (see *example/hotReload1.py*,
   *example/hotReload2.py*)
-  Lib supports **multiple servers** in one app (see
   *example/multiple.py*)
-  Lib supports **merging** with another WSGI app on the same IP:PORT
   (see *example/mergeFlaskApp.py*)
-  Lib supports different **execution-backends**, for example
   multiprocessing (see *example/parallelExecuting.py*)
-  Lib supports **locking** (you can lock all server or specific
   dispatchers)
-  Lib supports different **serializing-backends** so you can implement
   any protocol, not only JSON
-  Lib supports **individual settings** for different dispatchers. For
   example one of them can be processed with parallel (multiprocess)
   backend, other with standard processing
-  Lib collects self **speed-stats**

Cons
~~~~

-  Not fully **documentated**. For now only examples in package and `API
   documentation <https://byaka.github.io/flaskJSONRPCServer-docs/>`__.
-  Lib not has **decorators**, so it not a "Flask-way" (this can be
   simply added, but i not use decorators, sorry)
-  Lib not covered with **tests**.

Install
~~~~~~~

``pip install flaskJSONRPCServer``

Examples
~~~~~~~~

Simple server. More examples you can find in directory *example/*

.. code:: python

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

License
~~~~~~~

It is licensed under the Apache License, Version 2.0
(`read <http://www.apache.org/licenses/LICENSE-2.0.html>`__).

.. |python27| image:: https://img.shields.io/badge/python-2.7-blue.svg
   :target: https://github.com/byaka/flaskJSONRPCServer
.. |License| image:: https://img.shields.io/pypi/l/flaskJSONRPCServer.svg
   :target: http://www.apache.org/licenses/LICENSE-2.0.html
.. |PyPI version| image:: https://img.shields.io/pypi/v/flaskJSONRPCServer.svg
   :target: https://pypi.python.org/pypi/flaskJSONRPCServer
.. |PyPI downloads| image:: https://img.shields.io/pypi/dm/flaskJSONRPCServer.svg
   :target: https://pypi.python.org/pypi/flaskJSONRPCServer
