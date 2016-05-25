# -*- coding: utf-8 -*-

def sexy_primes(n):
   """ Source from http://habrahabr.ru/post/259095/ """
   def is_prime(n):
      if not n % 2:
         return False
      i = 3
      while True:
         if n % i == 0:
            return False
         i += 2
         if i >= n:
            return True
      return True
   l = []
   for j in range(9, n+1):
      if is_prime(j-6) and is_prime(j):
         l.append([j-6, j])
   return l

if __name__=='__main__':
   import sys, time, random

   from flaskJSONRPCServer import flaskJSONRPCServer

   def stats(_connection=None):
      #return server's speed stats
      return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

   class testAsync:
      def sexyPrime(self, n=20000):
         return len(sexy_primes(n))

      def sexyPrimeA(self, n=20000, _connection=None):
         return len(_connection.server.callAsync(sexy_primes, [n]))

   print 'Running api..'
   # Creating instance of server
   #    <blocking>         switch server to one-request-per-time mode
   #    <cors>             switch auto CORS support
   #    <gevent>           switch to patching process with Gevent
   #    <debug>            switch to logging connection's info from serv-backend
   #    <log>              set logging level (0-critical, 1-errors, 2-warnings, 3-info, 4-debug)
   #    <fallback>         switch auto fallback to JSONP on GET requests
   #    <allowCompress>    switch auto compression
   #    <compressMinSize>  set min limit for compression
   #    <tweakDescriptors> set file-descriptor's limit for server (useful on high-load servers)
   #    <jsonBackend>      set JSON-backend. Auto fallback to native when problems
   #    <notifBackend>     set exec-backend for Notify-requests
   #    <servBackend>      set serving-backend ('pywsgi', 'werkzeug', 'wsgiex' or 'auto'). 'auto' is more preffered
   #    <experimental>     switch using of experimental perfomance-patches
   server=flaskJSONRPCServer(("0.0.0.0", 7001), cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, compressMinSize=1024, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000], servBackend='auto', experimental=True)
   # Register dispatcher for all methods of instance
   server.registerInstance(testAsync(), path='/api')
   # Register dispatchers for single functions
   server.registerFunction(stats, path='/api')
   # Register dispatchers for lambda
   server.registerFunction(lambda _connection=None: 'Hello, %s!'%(_connection.ip), name='myip', path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
