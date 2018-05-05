#!/usr/bin/env python
# -*- coding: utf-8 -*-

__ver_major__ = 0
__ver_minor__ = 2
__ver_patch__ = 1
__ver_sub__ = ""
__version__ = "%d.%d.%d" % (__ver_major__, __ver_minor__, __ver_patch__)
"""
Extremely-fast parser for HTTP headers and some tools.
This module contains:
   1. Fast parser for http headers from file-like object. Two times faster then default `mimetools.Message()` and lib `http_parser`.
   2. Fast parser for http headers from string. Sligthly faster, then from file-like object.
   3. File-like wrapper for socket, that provide auto-parsing of http-request's head (split first line and parse headers) and give file-compatible interface for reading data from socket.

:authors: John Byaka
:copyright: Copyright 2016, Buber
:license: Apache License 2.0

:license:

   Copyright 2016 Buber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import sys

global PY_V
PY_V=float(sys.version[:3])

# dont store multiple values for this headers
FLAT_HEADERS={'CONNECTION':'', 'CONTENT-TYPE':'', 'CONTENT-LENGTH':'', 'EXPECT':'', 'REFERER':'', 'USER-AGENT':'', 'COOKIE':'', 'ACCEPT':'', 'ACCEPT-CHARSET':'', 'ACCEPT-ENCODING':'', 'ACCEPT-LANGUAGE':'', 'HOST':'', 'connection':'', 'content-type':'', 'content-length':'', 'expect':'', 'referer':'', 'user-agent':'', 'cookie':'', 'accept':'', 'accept-charset':'', 'accept-encoding':'', 'accept-language':'', 'host':''}

def fhhp_fromString(data, ignoreBadLine=False, findEOH=True, useUpper=False, storeOriginalName=True, flatValueFor=None):
   """
   Parser for http headers from string.
   """
   # first line must be readed
   if findEOH:
      i=data.find('\r\n\r\n')
      if i==-1:
         raise ValueError('Not all message recivied')
      data=data[:i]
   if flatValueFor is None:
      flatValueFor=FLAT_HEADERS
   res={}
   lines=data.split('\r\n')
   for line in lines:
      line=line.strip()
      if ': ' not in line:
         if ignoreBadLine: continue
         raise ValueError('Incorrect line: "%s"'%line)
      k, v=line.split(': ', 1)
      if k[-1]==' ': k=k.rstrip()
      if v[0]==' ': v=v.lstrip()
      k2=k.upper() if useUpper else k.lower()
      # check if needed multiple-storing for this header
      flatVal=False
      if flatValueFor is True: flatVal=True
      elif flatValueFor is not False and k2 in flatValueFor: flatVal=True
      # store header
      if k2 not in res:
         if storeOriginalName: res[k2]=(k, v) if flatVal else (k, [v])
         else: res[k2]=v if flatVal else [v]
      elif not flatVal:
         if storeOriginalName: res[k2][1].append(v)
         else: res[k2].append(v)
   return res

def fhhp_fromFile(data, ignoreBadLine=False, useUpper=False, storeOriginalName=True, flatValueFor=None):
   """
   Parser for http headers from file-like object.
   """
   # first line must be readed
   if flatValueFor is None:
      flatValueFor=FLAT_HEADERS
   res={}
   line=None
   while True:
      line=data.readline().strip()  #we need strip to avoid trailing breaker
      if not line: break
      if ': ' not in line:
         if ignoreBadLine: continue
         raise ValueError('Incorrect line: "%s"'%line)
      k, v=line.split(': ', 1)
      if k[-1]==' ': k=k.rstrip()
      if v[0]==' ': v=v.lstrip()
      k2=k.upper() if useUpper else k.lower()
      # check if needed multiple-storing for this header
      flatVal=False
      if flatValueFor is True: flatVal=True
      elif flatValueFor is not False and k2 in flatValueFor: flatVal=True
      # store header
      if k2 not in res:
         if storeOriginalName: res[k2]=(k, v) if flatVal else (k, [v])
         else: res[k2]=v if flatVal else [v]
      elif not flatVal:
         if storeOriginalName: res[k2][1].append(v)
         else: res[k2].append(v)
   return res

# default size-settings for parts of http-request
HEAD_SIZE_CHUNK=1024
HEAD_SIZE_MAX=10*1024
BODY_SIZE_CHUNK=30*1024
BODY_SIZE_MAX=30*1024*1024

class LongRequestError(Exception):
   """ This error raised by httpInputWrapper, if limit of parsing exceeded. """

class httpInputWrapper(object):
   """
   File-like wrapper for socket, that provide auto-parsing of http-request's head (split first line and parse headers) and give file-compatible interface for reading data from socket.
   """
   #! only partially support of file-like methods
   #! dont supports non-blocking sockets, must be implemented

   if PY_V<2.7:
      # by some unknown reason, in python>2.6 slots slightly slower
      __slots__=('readable', 'read', 'readline', '_sock', '_cache', '_readed', '_firstline', '_headers')

   def __init__(self, sock, parseHeaders=True, useUpper=False, storeOriginalName=True, flatValueFor=None, maxSize=None, chunkSize=None):
      firstline=None
      headers=''
      cache=''
      readed=0
      maxSize=HEAD_SIZE_MAX if maxSize is None else maxSize
      chunkSize=HEAD_SIZE_CHUNK if chunkSize is None else chunkSize
      # read and find end-of-headers
      while True:
         if maxSize and readed>maxSize:
            raise LongRequestError('Limit of HEAD exceeded')
         s=sock.recv(chunkSize)
         if not s: break
         readed+=chunkSize
         if not s: break
         if firstline is None and '\r\n' in s:
            firstline, s=s.split('\r\n', 1)
         if '\r\n\r\n' in s:
            s, cache=s.split('\r\n\r\n', 1)
            headers+=s
            break
         else:
            headers+=s
      if firstline is None: firstline=''
      # also parse headers if needed
      if parseHeaders:
         headers=fhhp_fromString(headers, ignoreBadLine=False, findEOH=False, useUpper=useUpper, storeOriginalName=storeOriginalName, flatValueFor=flatValueFor)
      # store data to instance
      self._sock=sock
      self._cache=cache
      self._readed=readed
      self._firstline=firstline
      self._headers=headers

   def readable(self):
      return True

   #! при попытке прочитать данные с пустого сокета в блокирующем режиме, мы будем вечно ждать
   def read(self, n, maxSize=None, chunkSize=None):
      r=''
      complete=False
      # from cache
      if self._cache:
         cache=self._cache
         if n=='line':
            if '\n' in cache:
               r, self._cache=cache.split('\n', 1)
               r+='\n'
               complete=True
            else:
               r=cache
               self._cache=''
         else:
            lCache=len(cache)
            if n<=lCache:
               r=cache[:n]
               self._cache=cache[n:]
               complete=True
            else:
               n-=lCache
               r=cache
               self._cache=''
      # from socket
      if not complete:
         sock=self._sock
         maxSize=BODY_SIZE_MAX if maxSize is None else maxSize
         chunkSize=BODY_SIZE_CHUNK if chunkSize is None else chunkSize
         if n=='line':
            # find line-breaker
            readed=self._readed
            while True:
               if maxSize and readed>maxSize:
                  raise LongRequestError('Limit of BODY exceeded')
               s=sock.recv(chunkSize)
               if not s: break
               readed+=chunkSize
               if '\n' in s:
                  s, self._cache=s.split('\n', 1)
                  r+=s+'\n'
                  break
               else: r+=s
            self._readed=readed
         else:
            r+=sock.recv(n)
      return r

   def readline(self, maxSize=None, chunkSize=None):
      return self.read('line', maxSize=maxSize, chunkSize=chunkSize)
