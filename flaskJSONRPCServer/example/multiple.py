# -*- coding: utf-8 -*-
import sys, time, random

"""
This example show how to run multiple servers in one app
"""

from flaskJSONRPCServer import flaskJSONRPCServer

class mySharedMethods:
   def random(self, mult=65536):
      # Sipmly return random value (0..mult)
      return int(random.random()*mult)

if __name__=='__main__':
   print 'Running api..'
   ports=[7001, 7002, 7003]
   for i, port in enumerate(ports):
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
      server=flaskJSONRPCServer(("0.0.0.0", port), blocking=False, cors=True, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000])
      # Register dispatcher for all methods of instance
      server.registerInstance(mySharedMethods(), path='/api')
      # Run server
      if i+1<len(ports): server.start() #don't join to event loop, so we can do anything else
      else:
         print 'Runned'
         server.start(joinLoop=True) #same as server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
