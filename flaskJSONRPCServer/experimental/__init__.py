#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This package contains experimental extensions for flaskJSONRPCServer.

moreAsync:
   Tricky implemetations of some server's methods that add async executing.

asyncJSON:
   Pseudo-async implementation of JSON parser and dumper. It allow to switch context (switching to another greenlet vs thread) every given seconds. Useful on processing large data.

uJSON
   Extremely fast JSON-backend.
"""

if __name__=='__main__':
   import sys, os
   sys.path.append(os.path.dirname(os.path.realpath(sys.argv[0]))+'/..')
   from utils import magicDict
else:
   # from flaskJSONRPCServer.utils import magicDict
   from ..utils import magicDict

import sys, string, time, re, codecs
from collections import deque
from decimal import Decimal

use_moreAsync=True
use_ujson=True
use_asyncJSON=True
msgShowed=False

class moreAsync:
   def __init__(self, method, getSize=None, minSize=0, newMethod=None):
      self.method=method
      self.getSize=getSize if getSize is not None else lambda data: sys.getsizeof(data)
      self.minSize=minSize
      self.server=None
      self.speedStats={}
      self.minSleep=0.2
      self.result={}
      self._newMethod=newMethod

   def overload(self, server):
      if not server.settings.gevent: return
      # add link to server
      if self.server is None: self.server=server
      # add backup for old methods
      if not hasattr(self.server, '_moreAsync_backup'): setattr(self.server, '_moreAsync_backup', {})
      # backup old method
      self.server._moreAsync_backup[self.method]=getattr(server, self.method)
      # overload method
      setattr(server, self.method, self.wrapper)

   def wrapper(self, data):
      # calc size
      size=self.getSize(data) if self.server._isFunction(self.getSize) else 0
      # if size lower then minSize, call original method
      if size is not None and size<self.minSize: return self.server._moreAsync_backup[self.method](data)
      # create tmp result
      cId=self.server._randomEx(99999, self.result.keys())
      self.result[cId]=False
      # run in native thread and wait result
      self.server._thread(self.newMethod, args=[cId, data, size], forceNative=True)
      while self.result[cId] is False: self.server._sleep(self.minSleep)
      res=self.result[cId]
      del self.result[cId]
      return res

   def newMethod(self, cId, data, size):
      try:
         # print '>>>>>>MOREASYNC %s start <%s>, size %smb'%(self.method, cId, round(size/1024.0/1024.0, 2))
         mytime=self.server._getms()
         if self.server._isFunction(self._newMethod):
            self.result[cId]=self._newMethod(data, self)
         else:
            self.result[cId]=self.server._moreAsync_backup[self.method](data)
         speed=self.server._getms()-mytime
         self.speedStats[round(size/1024.0/1024.0)]=speed
         # print '>>>>>>MOREASYNC %s end <%s>, time %ss'%(self.method, cId, round(speed/1000.0, 1))
      except Exception, e:
         self.server._throw('MOREASYNC_ERROR %s: %s'%(self.method, e))

moreAsync_methods={
   '_compressGZIP': {'minSize':1*1024*1024},
   '_sha256': {'minSize':200*1024*1024},
   '_sha1': {'minSize':300*1024*1024}
}

asyncJSON_delimeter=re.compile('(,|\[|\]|{|}|:)')

def asyncJSON_dumps(data, cb=None, maxProcessTime=0.3):
   #from globals() to locals()
   _str=str
   _basestring=basestring
   _list=list
   _dict=dict
   _type=type
   _unicode=unicode
   _int=int
   _float=float
   _long=long
   _complex=complex
   _decimal=Decimal
   _len=len
   _true=True
   _false=False
   _none=None
   _timetime=time.time
   #create vars
   out=[]
   stack=deque()
   mytime=_timetime()
   maxProcessTime=maxProcessTime
   #link to var's methods
   _outAppend=out.append
   _stackAppend=stack.appendleft
   _stackPop=stack.popleft
   #check is given data is primitive type
   tv=_type(data)
   if (tv is _dict):
      _stackAppend(['o', data, 0, _len(data), data.items()])
   elif (tv is _list):
      _stackAppend(['l', data, 0, _len(data)])
   elif (data is _true): _outAppend('true') #check value, not type
   elif (data is _false): _outAppend('false') #check value, not type
   elif (data is _none): _outAppend('null') #check value, not type
   elif (tv is _str) or (tv is _unicode) or (tv is _basestring):
      _outAppend('"'+data+'"')
   elif (tv is _int) or (tv is _float) or (tv is _long) or (tv is _complex) or (tv is _decimal):
      _outAppend('%s'%data)
   else:
      #check base type
      tpv=tv.__bases__[0]
      if (tpv is _dict):
         _stackAppend(['o', data, 0, _len(data), data.items()])
      elif (tpv is _list):
         _stackAppend(['l', data, 0, _len(data)])
      elif (tpv is _str) or (tpv is _unicode) or (tpv is _basestring):
         _outAppend('"'+data+'"')
      elif (tpv is _int) or (tpv is _float) or (tpv is _long) or (tpv is _complex) or (tpv is _decimal):
         _outAppend('%s'%data)
   #walk through object without recursion
   startMap={'o':'{', 'l':'['}
   endMap={'o':'}', 'l':']'}
   while _len(stack):
      frame=_stackPop()
      #params to locals
      t=frame[0]
      d=frame[1]
      i=frame[2]
      l=frame[3]
      if t is 'o': _iter=frame[4]
      if i is 0: #add <start> symbol like {, [
         _outAppend(startMap[t])
      #iter over frame from saved position
      while i<l:
         if cb and _timetime()-mytime>=maxProcessTime:
            #callback of long processing
            s=cb(out, stack)
            if s is False: return
            mytime=_timetime()
         if i: _outAppend(', ') #add separator
         #get value by index
         if t is 'l': v=d[i]
         else:
            k, v=_iter[i]
            #add <key>
            _outAppend('"'+k+'":')
         #check type
         tv=_type(v)
         if (tv is _dict):
            #remember position for continue
            frame[2]=i+1
            #return current frame to stack, we end him later
            _stackAppend(frame)
            #replace frame, useful if no more childs
            i=-1
            t='o'
            l=_len(v)
            d=v
            _iter=v.items()
            frame=['o', v, 0, l, _iter]
            _outAppend(startMap[t])
         elif (tv is _list):
            #remember position for continue
            frame[2]=i+1
            #return current frame to stack, we end him later
            _stackAppend(frame)
            #replace frame, useful if no more childs
            i=-1
            t='l'
            l=_len(v)
            d=v
            frame=['l', v, 0, l]
            _outAppend(startMap[t])
         elif (v is _true): _outAppend('true') #check value, not type
         elif (v is _false): _outAppend('false') #check value, not type
         elif (v is _none): _outAppend('null') #check value, not type
         elif (tv is _str) or (tv is _unicode) or (tv is _basestring):
            _outAppend('"'+v.replace('"', '\\"')+'"')
         elif (tv is _int) or (tv is _float) or (tv is _long) or (tv is _complex) or (tv is _decimal):
            _outAppend('%s'%v)
         else:
            #check base type
            tpv=tv.__bases__[0]
            if (tpv is _dict):
               #remember position for continue
               frame[2]=i+1
               #return current frame to stack, we end him later
               _stackAppend(frame)
               #replace frame, useful if no more childs
               i=-1
               t='o'
               l=_len(v)
               d=v
               _iter=v.items()
               frame=['o', v, 0, l, _iter]
               _outAppend(startMap[t])
            elif (tpv is _list):
               #remember position for continue
               frame[2]=i+1
               #return current frame to stack, we end him later
               _stackAppend(frame)
               #replace frame, useful if no more childs
               i=-1
               t='l'
               l=_len(v)
               d=v
               frame=['l', v, 0, l]
               _outAppend(startMap[t])
            elif (tpv is _str) or (tpv is _unicode) or (tpv is _basestring):
               _outAppend('"'+v.replace('"', '\\"')+'"')
            elif (tpv is _int) or (tpv is _float) or (tpv is _long) or (tpv is _complex) or (tpv is _decimal):
               _outAppend('%s'%v)
         i=i+1
      else:
         #add <end> symbol like }, ]
         _outAppend(endMap[t])
   #list to string
   return string.joinfields(out, '')

"""
проверить вариант, когда вместо стека используется обычная очередь (тоесть элементы не удаляются после обработки, а факт завершения считается по достижению указателем конца очереди). при этом для возврата к предыдущему уровню здесь используется дублирование этого уровню
в _asyncJSON_loads() использование метода строки вместо string.<метод> дало прирост скорости
"""

def asyncJSON_loads(data, cb=None, maxProcessTime=0.3):
   data=codecs.encode(data, 'utf-8')
   data=asyncJSON_delimeter.split(data)
   #from globals() to locals()
   _unicode=unicode
   _float=float
   _int=int
   _timetime=time.time
   #create vars
   mytime=_timetime()
   out=None
   curLevelType=None
   curLevelLink=None
   prevLevel=deque()
   prevLevelAppend=prevLevel.appendleft
   prevLevelPop=prevLevel.popleft
   prevKey=None
   outEmpty=True
   #walk through parts of string
   v=None
   data.append(None) #as we work with prev element, we need last empty
   for part in data:
      if cb and _timetime()-mytime>=maxProcessTime:
         #callback of long processing
         s=cb()
         if s is False: return
         mytime=_timetime()
      #process previous part
      if v:
         #check value's type
         if v[0] is '"':
            if len(v)>1 and v[-1] is '"' and v[-2:]!='\\"':
               v=v[1:-1] #crop quotes
               if '\\' in v: v=v.replace('\\', '') #correct escaping
               v=_unicode(v, 'utf-8') #back to unicode
               #special check for map_key
               if part is ':':
                  prevKey=v
                  v=None
                  continue
            else:
               #correcting string if it contain special symbols
               if part: v=v+part
               continue
         else:
            v=_float(v) if '.' in v else _int(v)
         if outEmpty:
            out=v
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(v)
         else: curLevelLink[prevKey]=v
      #process part and generate event
      v=None
      if not part or part is ' ' or part is ',': continue
      elif part is '{':
         prevLevelAppend((curLevelType, curLevelLink))
         s={}
         if outEmpty:
            out=s
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s
         curLevelType='o'
      elif part is '[':
         prevLevelAppend((curLevelType, curLevelLink))
         s=[]
         if outEmpty:
            out=s
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s
         curLevelType='l'
      elif (part is ']') or (part is '}'):
         curLevelType, curLevelLink=prevLevelPop()
      elif part=='true':
         if outEmpty:
            out=True
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(True)
         else: curLevelLink[prevKey]=True
      elif part=='false':
         if outEmpty:
            out=False
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(False)
         else: curLevelLink[prevKey]=False
      elif part=='null':
         if outEmpty:
            out=None
            outEmpty=False
         elif curLevelType is 'l': curLevelLink.append(None)
         else: curLevelLink[prevKey]=None
      else:
         if part[0] is ' ': v=part.lstrip()
         else: v=part
   return out

def _patchServer(server):
   global msgShowed
   if not msgShowed: print 'EXPERIMENTAL futures used'
   msgShowed=True
   global use_moreAsync, use_ujson, use_asyncJSON
   # overload methods to moreAsync
   if server.settings.gevent and use_moreAsync:
      for k, v in moreAsync_methods.items():
         o=moreAsync(k, **v)
         o.overload(server)
   # try import and use ujson
   if use_ujson:
      try:
         import ujson
         server.jsonBackend=magicDict({
            'dumps': lambda data, **kwargs: ujson.dumps(data),
            'loads': lambda data, **kwargs: ujson.loads(data)
         })
      except ImportError: pass
   # use asyncJSON
   if use_asyncJSON:
      server._asyncJSON_backup=server.jsonBackend
      def tFunc_dumps(data, server=server, **kwargs):
         size=sys.getsizeof(data)
         if size is not None and size<1*1024*1024:
            return server._asyncJSON_backup.dumps(data)
         # print '>>>>>>ASYNCJSON dumps start, size %smb'%(round(size/1024.0/1024.0, 2))
         mytime=server._getms()
         res=asyncJSON_dumps(data, maxProcessTime=0.1, cb=lambda *args:server._sleep(0.001))
         speed=server._getms()-mytime
         # print '>>>>>>ASYNCJSON dumps end, time %ss'%(round(speed/1000.0, 1))
         return res
      def tFunc_loads(data, server=server, **kwargs):
         size=sys.getsizeof(data)
         if size is not None and size<10*1024*1024:
            return server._asyncJSON_backup.loads(data)
         # print '>>>>>>ASYNCJSON loads start, size %smb'%(round(size/1024.0/1024.0, 2))
         mytime=server._getms()
         res=asyncJSON_loads(data, maxProcessTime=0.1, cb=lambda:server._sleep(0.001))
         speed=server._getms()-mytime
         # print '>>>>>>ASYNCJSON loads end, time %ss'%(round(speed/1000.0, 1))
         return res
      server.jsonBackend=magicDict({
         'dumps': tFunc_dumps,
         'loads': tFunc_loads
      })

def initLocal(scope, server):
   global msgShowed
   if not msgShowed: print 'EXPERIMENTAL futures used'
   msgShowed=True
   scope['_patchServer']=_patchServer

def initGlobal(scope):
   global msgShowed
   # if not msgShowed: print 'EXPERIMENTAL futures used'
   # msgShowed=True
   pass

if __name__=='__main__':
   obj=[{"jsonrpc": "2.0", "method": u"привет", "params": [{"jsonrpc": "1.0", "method": "test2", "params": {"param1": -23, "param2": 42.2, "param3":True, "param4":False, "param5":None, "param6":u'[{"jsonrpc": "2.0", "method": "привет", "params": [{"jsonrpc": "1.0", "method": "test2", "params": {"param1": -23, "param2": 42.2, "param3":True, "param4":False, "param5":None}, "id": 3}, 23.123], "id": 1}]'}, "id": 3}, 23.123], "id": 1}]
   # obj={"id": '{"id": 1}'}
   # obj={'key1':'value"]', 'key2':'value:{2}'}
   data=asyncJSON_dumps(obj)
   print 'ORIGINAL:', obj
   print 'SERIALIZED:', data

   # import simplejson as json
   # print json.dumps(obj)
   # data=json.dumps(obj)

   obj2=asyncJSON_loads(data)
   print 'PARSED:', obj2
   print obj==obj2
   sys.exit(0)
