# -*- coding: utf-8 -*-
import sys, time, random

from flaskJSONRPCServer import flaskJSONRPCServer

def hiGuest(_connection=None):
   return 'Hello, %s!'%(_connection.ip)

def hiUser(_connection=None):
   return 'Hello, USER!'

def auth(server, path, request, jsonpMethod):
   # <server>        is a flaskJSONRPCServer instance
   # <path>          is a PATH of request
   # <request>       is a copy of REQUEST object
   # <jsonpMethod>   is a dispatcher's name, if request sended over JSONP (GET)
   print 'AUTH_CB', path, request.headers, request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
   if path=='/api/': return True
   if request.headers.get('Token', None)=='1234': return True
   if request.environ.get('HTTP_X_REAL_IP', request.remote_addr)=='127.0.0.1': return True

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
   #    <auth>             set callback for authorization
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=True, debug=False, log=False, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000], auth=auth)
   # Register dispatchers for single functions
   server.registerFunction(hiUser, path='/apiAuth', name='hi')
   server.registerFunction(hiGuest, path='/api', name='hi')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
