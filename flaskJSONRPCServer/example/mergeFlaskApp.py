# -*- coding: utf-8 -*-
import sys, time, random

#FLASK
from flask import Flask, request

from flaskJSONRPCServer import flaskJSONRPCServer

def echo(data='Hello world!'):
   # Simply echo
   return data
echo._alias='helloworld' #setting alias for method

def stats(_connection=None):
   #return server's speed stats
   return _connection.server.stats(inMS=True) #inMS=True return stats in milliseconds

app=Flask(__name__)
@app.route('/readpost', methods=['POST'])
def flaskReadpost1():
   print 'flaskReadpost1 called'
   d=request.data
   s='{"jsonrpc": "2.0", "result":"You sended %s", "id": 1}'%(d.replace('"', '\\"'))
   return s

app2=Flask(__name__)
@app2.route('/helloworld', methods=['GET'])
def flaskHelloworld():
   return 'Hello world!'

@app2.route('/readpost', methods=['POST'])
def flaskReadpost2():
   print 'flaskReadpost2 called'
   d=request.data
   s='{"jsonrpc": "2.0", "result":"(REWRITED_WITH_flaskReadpost2) You sended %s", "id": 1}'%(d.replace('"', '\\"'))
   return s

def fakeWSGI1(env, start_response):
   d=env['wsgi.input'].read(10)+env['wsgi.input'].read(10)
   print 'fakeWSGI1 called', d
   env['flaskJSONRPCServer_skip']()

def fakeWSGI2(env, start_response):
   d=env['wsgi.input'].read(3)+env['wsgi.input'].read(20)+env['wsgi.input'].read()
   print 'fakeWSGI2 called', d
   env['flaskJSONRPCServer_skip']()

def ppCB1(request, server, controller):
   d=server._loadPostData(request)
   print 'ppCB1 called', d
   # return 200, '{"jsonrpc": "2.0", "result":"HI!", "id": 1}'
   controller.skip()

if __name__=='__main__':
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
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=False, gevent=True, debug=False, log=3, fallback=True, allowCompress=False, jsonBackend='simplejson', notifBackend='simple', tweakDescriptors=[1000, 1000], servBackend='auto')
   # Register dispatchers for single functions
   server.registerFunction(echo, path='/api')
   server.registerFunction(stats, path='/api')
   # merge with Flask app
   server.postprocessAdd_wsgi(app, status=404)
   server.postprocessAdd_wsgi(fakeWSGI1, status=404)
   server.postprocessAdd_wsgi(fakeWSGI2, status=404)
   server.postprocessAdd_wsgi(app2, status=404)
   server.postprocessAdd_cb(ppCB1, status=404)
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620
