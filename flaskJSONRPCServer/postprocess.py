#!/usr/bin/env python
# -*- coding: utf-8 -*
"""

"""

from utils import *

class postprocess(object):
   """
   This class implements all logic of executing postprocess-callbacks. It doesn't has any public method, but instances of this class is callable.

   :param server: Instance of server.
   :param dict postprocessMap: Map of postprocess wsgi by conditions.
   """

   _modeDefault='rewrite'
   _modeSupported=('rewrite', 'fake')
   _typeSupported=('wsgi', 'cb')

   def __init__(self, server, postprocessMap):
      self._server=server
      self._postprocessMap_byStatus=postprocessMap.get('byStatus', {})
      self.__request={}
      self.__isEnd=False
      self.__isSkipSaving=False

      self.__status_original=0
      self.__headers_original=[]
      self.__data_original=[]
      self.__dataRaw_original=None

      self.__status=0
      self.__headers=[]
      self.__data=[]
      self.__dataRaw=None
      self.__mode=None
      self.__type=None

   def __call__(self, request, status, headers, data, dataRaw):
      """
      Select and run postprocessers for passed request.
      """
      # routing
      cbArr=None
      if self._postprocessMap_byStatus:
         cbArr=[]
         # http-status
         if status in self._postprocessMap_byStatus:
            cbArr+=self._postprocessMap_byStatus[status]
         # rpc-error
         if dataRaw and dataRaw['rpcError']:
            for s in dataRaw['rpcError']:
               if s in self._postprocessMap_byStatus:
                  cbArr+=self._postprocessMap_byStatus[s]
      if not cbArr:  #without postprocessers
         return status, headers, data
      self.__request=request
      # store current response-values
      self.__status_original=self.__status=status
      self.__headers_original=self.__headers=headers
      self.__data_original=self.__data=data
      self.__dataRaw_original=self.__dataRaw=dataRaw
      # prepare environ
      self._prepare()
      # start processing
      for type, mode, cb in cbArr:
         # erase locals
         self.__isEnd=False
         self.__isSkipSaving=False
         self.__mode=mode or self._modeDefault
         self.__type=type
         self.__postData_pos=0
         # process one cb
         self._process(cb)
         if self.__isEnd: break
      # return new response-values
      return self.__status, self.__headers, self.__data

   def _prepare(self,):
      self.__postData_input=self.__request['environ']['wsgi.input']
      self.__postData_pos=0
      if self.__request['data'] is not None:
         self.__postData_readed=True
         self.__postData_cache=self.__request['data']
         self.__postData_length=len(self.__request['data'])
      else:
         self.__postData_readed=0
         self.__postData_cache=''
         if 'CONTENT_LENGTH' in self.__request['environ'] and self.__request['environ']['CONTENT_LENGTH']:
            self.__postData_length=int(self.__request['environ']['CONTENT_LENGTH'])
         else: self.__postData_length=0
      self.__request['environ']['wsgi.input']=filelikeWrapper(self._postData)

   def _postData(self, l=None, *args, **kwargs):
      """ Allow read post-data multiple times. """
      if l is None or self.__postData_pos+l>self.__postData_length:
         l=self.__postData_length-self.__postData_pos
      data=''
      if self.__postData_readed is True:
         # read from cache only
         data=self.__postData_cache[self.__postData_pos:self.__postData_pos+l]
      else:
         # read from cache and input
         lCache=(self.__postData_readed-self.__postData_pos)  #сколько есть в кеше для чтения
         if lCache>0:
            l1=min(l, lCache)  #сколько читаем из кеша
            data=self.__postData_cache[self.__postData_pos:self.__postData_pos+l1]
            l2=l-l1  #сколько читаем из input
         else: l2=l
         if l2>0:
            s=self.__postData_input.read(l2)
            data+=s
            self.__postData_cache+=s
         self.__postData_readed=max(self.__postData_readed, self.__postData_pos+l)
         if self.__postData_readed>=self.__postData_length: self.__postData_readed=True
      self.__postData_pos+=l
      return data

   def _skip(self):
      self.__isSkipSaving=True

   def _end(self):
      self.__isEnd=True

   def _process(self, cb):
      if self.__type=='wsgi':
         # cb is WSGI app
         env=self.__request['environ']
         env['flaskJSONRPCServer']=self._server
         env['flaskJSONRPCServer_end']=self._end
         env['flaskJSONRPCServer_skip']=self._skip
         env['flaskJSONRPCServer_lastResponse']=(
            self._server._toHttpStatus(self.__status) if not isString(self.__status) else self.__status,
            [self.__data] if isString(self.__data) else self.__data,
            self.__headers, self.__dataRaw
         )
         env['flaskJSONRPCServer_originalResponse']=(
            self._server._toHttpStatus(self.__status_original) if not isString(self.__status_original) else self.__status_original,
            [self.__data_original] if isString(self.__data_original) else self.__data_original,
            self.__headers_original, self.__dataRaw_original
         )
         res=cb(env, self._wsgi_start_response)
         if self.__isSkipSaving or self.__mode=='fake': return
         elif self.__mode=='rewrite':
            self.__data=res
      elif self.__type=='cb':
         # cb is simple callback
         controller=controllerWrapper(
            self._end, self._skip,
            (self._server._fromHttpStatus(self.__status) if isString(self.__status) else self.__status, self.__headers, self.__data, self.__dataRaw),
            (self._server._fromHttpStatus(self.__status_original) if isString(self.__status_original) else self.__status_original, self.__headers_original, self.__data_original, self.__dataRaw_original),
         )
         res=cb(self.__request, self._server, controller)
         if self.__isSkipSaving or self.__mode=='fake': return
         elif self.__mode=='rewrite' and res:
            self.__status=res[0]
            self.__data=res[1]
            self.__headers=res[2] if len(res)>2 else []

   def _wsgi_start_response(self, status, headers, e=None):
      #! we not implement returnable write() method because it's not robust
      if not self.__isSkipSaving and self.__mode!='fake':
         if self.__mode=='rewrite':
            self.__status=status
            self.__headers=headers

class controllerWrapper(object):
   """
   Class for wrapping controller for <postprocess type='cb'>. Faster than magicDict.
   """
   if PY_V<2.7:
      # by some unknown reason, in python>2.6 slots slightly slower
      __slots__=('end', 'skip', 'lastResponse', 'originalResponse')

   def __init__(self, end, skip, lastResponse, originalResponse):
      self.end=end
      self.skip=skip
      self.lastResponse=lastResponse
      self.originalResponse=originalResponse
