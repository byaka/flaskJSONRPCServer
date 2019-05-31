# -*- coding: utf-8 -*-
"""
Pseudo-async implementation of JSON parser and dumper.
It allow to switch context (switching to another greenlet or thread) every given seconds.
Useful on processing large data.
Also has cython implementation and auto-load it if exist.
"""
import re, time, codecs
from collections import deque
from decimal import Decimal

def iterex(iterable, isDict=False):
   i=0
   l=len(iterable)
   if isDict:
      _next=iterable.iteritems().next
   while i<l:
      if isDict: v=_next()
      else: v=iterable[i]
      yield (i, l, v)
      i+=1

def dumps(data, cb=None, maxProcessTime=0.3):
   # from globals() to locals()
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
   _true=True
   _false=False
   _none=None
   _timetime=time.time
   _iterex=iterex
   _StopIteration=StopIteration
   # create vars
   out=[]
   stack=deque()
   mytime=_timetime()
   maxProcessTime=maxProcessTime
   # link to var's methods
   _outAppend=out.append
   _stackAppend=stack.appendleft
   _stackPop=stack.popleft
   # check is given data is primitive type
   tv=_type(data)
   if (tv is _dict):
      if not data: return '{}'
      _outAppend('{')
      _stackAppend((1, _iterex(data, _true).next))
   elif (tv is _list):
      if not data: return '[]'
      _outAppend('[')
      _stackAppend((0, _iterex(data, _false).next))
   elif (data is _true): return 'true'  #check value, not type
   elif (data is _false): return 'false'  #check value, not type
   elif (data is _none): return 'null'  #check value, not type
   elif (tv is _str) or (tv is _unicode) or (tv is _basestring): return '"'+data.encode('unicode-escape').replace('"', '\\"')+'"'
   elif (tv is _int) or (tv is _float) or (tv is _long) or (tv is _complex) or (tv is _decimal): return '%s'%data
   else:
      # check base type also
      tvb=tv.__bases__[0]
      if (tvb is _dict):
         if not data: return '{}'
         _outAppend('{')
         _stackAppend((1, _iterex(data, _true).next))
      elif (tvb is _list):
         if not data: return '[]'
         _outAppend('[')
         _stackAppend((0, _iterex(data, _false).next))
      elif (data is _true): return 'true'  #check value, not type
      elif (data is _false): return 'false'  #check value, not type
      elif (data is _none): return 'null'  #check value, not type
      elif (tvb is _str) or (tvb is _unicode) or (tvb is _basestring): return '"'+data.encode('unicode-escape').replace('"', '\\"')+'"'
      elif (tvb is _int) or (tvb is _float) or (tvb is _long) or (tvb is _complex) or (tvb is _decimal): return '%s'%data
   # walk through object without recursion
   while stack:
      frame=_stackPop()
      # params to locals
      t, it=frame
      try:
         i, l, v=it()
         if i: _outAppend(', ')  #add separator
         if t:
            k, v=v
            _outAppend('"'+k.encode('unicode-escape').replace('"', '\\"')+'":')  #add <key>
      except _StopIteration:
         _outAppend('}' if t else ']')
         continue
      # iter over frame from saved position
      while _true:
         if cb and _timetime()-mytime>=maxProcessTime:
            # callback of long processing
            if cb() is _false: return
            mytime=_timetime()
         # check type
         tv=_type(v)
         if (tv is _dict):
            if not v: _outAppend('{}')
            else:
               # return current frame to stack, we end him later
               _stackAppend(frame)
               # replace frame, useful if no more childs
               t=_true
               it=_iterex(v, _true).next
               frame=(_true, it)
               _outAppend('{')
         elif (tv is _list):
            if not v: _outAppend('[]')
            else:
               # return current frame to stack, we end him later
               _stackAppend(frame)
               # replace frame, useful if no more childs
               t=_false
               it=_iterex(v, _false).next
               frame=(_false, it)
               _outAppend('[')
         elif (v is _true): _outAppend('true')  #check value, not type
         elif (v is _false): _outAppend('false')  #check value, not type
         elif (v is _none): _outAppend('null')  #check value, not type
         elif (tv is _str) or (tv is _unicode) or (tv is _basestring):
            _outAppend('"'+v.encode('unicode-escape').replace('"', '\\"')+'"')
         elif (tv is _int) or (tv is _float) or (tv is _long) or (tv is _complex) or (tv is _decimal):
            _outAppend(_str(v))
         else:
            # check base type also
            tvb=tv.__bases__[0]
            if (tvb is _dict):
               if not v: _outAppend('{}')
               else:
                  # return current frame to stack, we end him later
                  _stackAppend(frame)
                  # replace frame, useful if no more childs
                  t=_true
                  it=_iterex(v, _true).next
                  frame=(_true, it)
                  _outAppend('{')
            elif (tvb is _list):
               if not v: _outAppend('[]')
               else:
                  # return current frame to stack, we end him later
                  _stackAppend(frame)
                  # replace frame, useful if no more childs
                  t=_false
                  it=_iterex(v, _false).next
                  frame=(_false, it)
                  _outAppend('[')
            elif (v is _true): _outAppend('true')  #check value, not type
            elif (v is _false): _outAppend('false')  #check value, not type
            elif (v is _none): _outAppend('null')  #check value, not type
            elif (tvb is _str) or (tvb is _unicode) or (tvb is _basestring):
               _outAppend('"'+v.encode('unicode-escape').replace('"', '\\"')+'"')
            elif (tvb is _int) or (tvb is _float) or (tvb is _long) or (tvb is _complex) or (tvb is _decimal):
               _outAppend(_str(v))
         # get next val
         try:
            i, l, v=it()
            if i: _outAppend(', ')  #add separator
            if t:
               k, v=v
               _outAppend('"'+k.encode('unicode-escape').replace('"', '\\"')+'":')  #add <key>
         except _StopIteration:
            _outAppend('}' if t else ']')  #add <end> symbol like }, ]
            break
   # list to string
   return ''.join(out)

delimeter=re.compile('(,|\[|\]|{|}|:)')

ucodes_map=[('\\u0430', 'а'), ('\\u0410', 'А'), ('\\u0431', 'б'), ('\\u0411', 'Б'), ('\\u0432', 'в'), ('\\u0412', 'В'), ('\\u0433', 'г'), ('\\u0413', 'Г'), ('\\u0434', 'д'), ('\\u0414', 'Д'), ('\\u0435', 'е'), ('\\u0415', 'Е'), ('\\u0451', 'ё'), ('\\u0401', 'Ё'), ('\\u0436', 'ж'), ('\\u0416', 'Ж'), ('\\u0437', 'з'), ('\\u0417', 'З'), ('\\u0438', 'и'), ('\\u0418', 'И'), ('\\u0439', 'й'), ('\\u0419', 'Й'), ('\\u043a', 'к'), ('\\u041a', 'К'), ('\\u043b', 'л'), ('\\u041b', 'Л'), ('\\u043c', 'м'), ('\\u041c', 'М'), ('\\u043d', 'н'), ('\\u041d', 'Н'), ('\\u043e', 'о'), ('\\u041e', 'О'), ('\\u043f', 'п'), ('\\u041f', 'П'), ('\\u0440', 'р'), ('\\u0420', 'Р'), ('\\u0441', 'с'), ('\\u0421', 'С'), ('\\u0442', 'т'), ('\\u0422', 'Т'), ('\\u0443', 'у'), ('\\u0423', 'У'), ('\\u0444', 'ф'), ('\\u0424', 'Ф'), ('\\u0445', 'х'), ('\\u0425', 'Х'), ('\\u0446', 'ц'), ('\\u0426', 'Ц'), ('\\u0447', 'ч'), ('\\u0427', 'Ч'), ('\\u0448', 'ш'), ('\\u0428', 'Ш'), ('\\u0449', 'щ'), ('\\u0429', 'Щ'), ('\\u044a', 'ъ'), ('\\u042a', 'Ъ'), ('\\u044b', 'ы'), ('\\u042b', 'Ы'), ('\\u044c', 'ь'), ('\\u042c', 'Ь'), ('\\u044d', 'э'), ('\\u042d', 'Э'), ('\\u044e', 'ю'), ('\\u042e', 'Ю'), ('\\u044f', 'я'), ('\\u042f', 'Я')]

def loads(data, cb=None, maxProcessTime=0.3):
   # from globals() to locals()
   _unicode=unicode
   _float=float
   _int=int
   _timetime=time.time
   _true=True
   _false=False
   _none=None
   # decoding
   data=codecs.encode(data, 'utf-8')
   if '\\u' in data:
      try:
         for code, to in ucodes_map: data=data.replace(code, to)
      except: pass
   # split to parts
   data=delimeter.split(data)
   # create vars
   mytime=_timetime()
   out=_none
   curLevelType=_none
   curLevelLink=_none
   prevLevel=deque()
   prevLevelAppend=prevLevel.appendleft
   prevLevelPop=prevLevel.popleft
   prevKey=_none
   outEmpty=_true
   v=_none
   # walk through parts of string
   data.append(_none)  #as we work with prev element, we need last empty
   for part in data:
      if cb and _timetime()-mytime>=maxProcessTime:
         #callback of long processing
         if cb() is _false: return
         mytime=_timetime()
      # process previous part
      if v:
         # check value's type
         if v[0] is '"':
            if len(v)>1 and v[-1] is '"' and v[-2:]!='\\"':
               v=v[1:-1]  #crop quotes
               if '\\' in v: v=v.decode('string-escape')  #correct escaping
               v=_unicode(v, 'utf-8')  #back to unicode
               # special check for map_key
               if part is ':':
                  prevKey=v
                  v=_none
                  continue
            else:
               # correcting string if it contain special symbols
               if part: v+=part
               continue
         else:
            v=_float(v) if '.' in v else _int(v)
         if outEmpty:
            out=v
            outEmpty=_false
         elif curLevelType: curLevelLink(v)
         else: curLevelLink[prevKey]=v
      # process part and generate event
      v=_none
      if not part or part is ' ' or part is ',': continue
      elif part[0] is ' ': part=part.lstrip()
      if part is '{':
         prevLevelAppend((curLevelType, curLevelLink))
         s={}
         if outEmpty:
            out=s
            outEmpty=_false
         elif curLevelType: curLevelLink(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s
         curLevelType=_false
      elif part is '[':
         prevLevelAppend((curLevelType, curLevelLink))
         s=[]
         if outEmpty:
            out=s
            outEmpty=_false
         elif curLevelType: curLevelLink(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s.append
         curLevelType=_true
      elif (part is ']') or (part is '}'):
         curLevelType, curLevelLink=prevLevelPop()
      elif part=='true':
         if outEmpty:
            out=_true
            outEmpty=_false
         elif curLevelType: curLevelLink(_true)
         else: curLevelLink[prevKey]=_true
      elif part=='false':
         if outEmpty:
            out=_false
            outEmpty=_false
         elif curLevelType: curLevelLink(_false)
         else: curLevelLink[prevKey]=_false
      elif part=='null':
         if outEmpty:
            out=_none
            outEmpty=_false
         elif curLevelType: curLevelLink(_none)
         else: curLevelLink[prevKey]=_none
      else: v=part
   return out

# replace with cython version if exist
try:
   iterex_native, dumps_native, loads_native=iterex, dumps, loads
   #! сишная версия стала работать очень медленно, какаято регрессия
   # from asyncjson_c import iterex, dumps, loads
except ImportError: pass

if __name__ == '__main__':
   pass
