# -*- coding: utf-8 -*-
import re, time, codecs
from collections import deque
from decimal import Decimal

# cimport cython

# cdef class iterex2:
#    # Implementation of generator without yeild.
#    # With Cython version 0.24 has same speed as generator.

#    cdef int i
#    cdef int l
#    cdef int _isDict
#    cdef _iterable
#    cdef _next

#    def __init__(self, iterable, int isDict):
#       self._iterable=iterable
#       self.i=-1
#       self.l=len(iterable)
#       self._isDict=isDict
#       if isDict:
#          self._next=iterable.iteritems().next

#    # cpdef next(self): return self.nextNative()

#    cpdef tuple next(self):
#       self.i+=1
#       if self.i>=self.l:
#          raise StopIteration
#       elif self._isDict:
#          return (self.i, self.l, self._next())
#       else:
#          return (self.i, self.l, self._iterable[self.i])

def iterex(iterable, int isDict=0):
   cdef:
      int i=0
      int l=len(iterable)
      tuple r
   if isDict:
      _next=iterable.iteritems().next
   while i<l:
      if isDict: v=_next()
      else: v=iterable[i]
      r=(i, l, v)
      yield r
      i+=1

def dumps(data, cb=None, float maxProcessTime=0.3):
   #create vars and link to var's methods
   _timetime=time.time
   cdef:
      int i
      int l
      int t
      int zero=0
      int one=1
      float mytime=_timetime()
      list out=[]
      tuple frame
   stack=deque()
   _outAppend=out.append
   _stackAppend=stack.appendleft
   _stackPop=stack.popleft
   #check is given data is primitive type
   if isinstance(data, dict):
      if not data: return '{}'
      _outAppend('{')
      _stackAppend((one, iterex(data, one).next))
   elif isinstance(data, list):
      if not data: return '[]'
      _outAppend('[')
      _stackAppend((zero, iterex(data, zero).next))
   elif (data is True): return 'true'  #check value, not type
   elif (data is False): return 'false'  #check value, not type
   elif (data is None): return 'null'  #check value, not type
   elif isinstance(data, (str, unicode, basestring)): return '"'+data+'"'
   elif isinstance(data, (int, float, long, complex, Decimal)): return str(data)
   #walk through object without recursion
   while len(stack):
      frame=_stackPop()
      #params to locals
      t, it=frame
      try:
         i, l, v=it()
         if i: _outAppend(', ')  #add separator
         if t:
            k, v=v
            _outAppend('"'+k.replace('"', '\\"')+'":')  #add <key>
      except StopIteration:
         _outAppend('}' if t else ']')
         continue
      #iter over frame from saved position
      while one:
         if cb and _timetime()-mytime>=maxProcessTime:
            #callback of long processing
            if cb() is False: return
            mytime=_timetime()
         #check type
         if isinstance(v, dict):
            if not v: _outAppend('{}')
            else:
               #return current frame to stack, we end him later
               _stackAppend(frame)
               #replace frame, useful if no more childs
               t=one
               it=iterex(v, one).next
               frame=(one, it)
               _outAppend('{')
         elif isinstance(v, list):
            if not v: _outAppend('[]')
            else:
               #return current frame to stack, we end him later
               _stackAppend(frame)
               #replace frame, useful if no more childs
               t=zero
               it=iterex(v, zero).next
               frame=(zero, it)
               _outAppend('[')
         elif v is True: _outAppend('true')  #check value, not type
         elif v is False: _outAppend('false')  #check value, not type
         elif v is None: _outAppend('null')  #check value, not type
         elif isinstance(v, (str, unicode, basestring)): _outAppend('"'+v.replace('"', '\\"')+'"')
         elif isinstance(v, (int, float, long, complex, Decimal)): _outAppend(str(v))
         # get next val
         try:
            i, l, v=it()
            if i: _outAppend(', ')  #add separator
            if t:
               k, v=v
               _outAppend('"'+k.replace('"', '\\"')+'":')  #add <key>
         except StopIteration:
            _outAppend('}' if t else ']')  #add <end> symbol like }, ]
            break
   #list to string
   return ''.join(out)

delimeter=re.compile('(,|\[|\]|{|}|:)')

cdef list ucodes_map=[('\\u0430', 'а'), ('\\u0410', 'А'), ('\\u0431', 'б'), ('\\u0411', 'Б'), ('\\u0432', 'в'), ('\\u0412', 'В'), ('\\u0433', 'г'), ('\\u0413', 'Г'), ('\\u0434', 'д'), ('\\u0414', 'Д'), ('\\u0435', 'е'), ('\\u0415', 'Е'), ('\\u0451', 'ё'), ('\\u0401', 'Ё'), ('\\u0436', 'ж'), ('\\u0416', 'Ж'), ('\\u0437', 'з'), ('\\u0417', 'З'), ('\\u0438', 'и'), ('\\u0418', 'И'), ('\\u0439', 'й'), ('\\u0419', 'Й'), ('\\u043a', 'к'), ('\\u041a', 'К'), ('\\u043b', 'л'), ('\\u041b', 'Л'), ('\\u043c', 'м'), ('\\u041c', 'М'), ('\\u043d', 'н'), ('\\u041d', 'Н'), ('\\u043e', 'о'), ('\\u041e', 'О'), ('\\u043f', 'п'), ('\\u041f', 'П'), ('\\u0440', 'р'), ('\\u0420', 'Р'), ('\\u0441', 'с'), ('\\u0421', 'С'), ('\\u0442', 'т'), ('\\u0422', 'Т'), ('\\u0443', 'у'), ('\\u0423', 'У'), ('\\u0444', 'ф'), ('\\u0424', 'Ф'), ('\\u0445', 'х'), ('\\u0425', 'Х'), ('\\u0446', 'ц'), ('\\u0426', 'Ц'), ('\\u0447', 'ч'), ('\\u0427', 'Ч'), ('\\u0448', 'ш'), ('\\u0428', 'Ш'), ('\\u0449', 'щ'), ('\\u0429', 'Щ'), ('\\u044a', 'ъ'), ('\\u042a', 'Ъ'), ('\\u044b', 'ы'), ('\\u042b', 'Ы'), ('\\u044c', 'ь'), ('\\u042c', 'Ь'), ('\\u044d', 'э'), ('\\u042d', 'Э'), ('\\u044e', 'ю'), ('\\u042e', 'Ю'), ('\\u044f', 'я'), ('\\u042f', 'Я')]
cdef int ucodes_len=len(ucodes_map)

def loads(sdata, cb=None, float maxProcessTime=0.3):
   # from globals() to locals()
   _timetime=time.time
   # decoding
   sdata=codecs.encode(sdata, 'utf-8')
   cdef int i=0
   if '\\u' in sdata:
      try:
         for i in range(ucodes_len):
            sdata=sdata.replace(ucodes_map[i][0], ucodes_map[i][1])
      except: pass
   # split to parts
   cdef list data=delimeter.split(sdata)
   data.append(None)  #as we work with prev element, we need last empty
   # create vars
   cdef:
      float mytime=_timetime()
      int curLevelType=0
      int outEmpty=1
      unicode prevKey=u''
      int l=len(data)
      str part
   out=None
   curLevelLink=None
   prevLevel=deque()
   prevLevelAppend=prevLevel.appendleft
   prevLevelPop=prevLevel.popleft
   v=None
   # walk through parts of string
   for i in range(l):
      part=data[i]
      if cb and _timetime()-mytime>=maxProcessTime:
         #callback of long processing
         if cb() is False: return
         mytime=_timetime()
      # process previous part
      if v:
         # check value's type
         if v[0] is '"':
            if len(v)>1 and v[-1] is '"' and v[-2:]!='\\"':
               v=v[1:-1]  #crop quotes
               if '\\' in v: v=v.replace('\\', '')  #correct escaping
               v=unicode(v, 'utf-8')  #back to unicode
               # special check for map_key
               if part is ':':
                  prevKey=v
                  v=None
                  continue
            else:
               # correcting string if it contain special symbols
               if part: v=v+part
               continue
         else:
            v=float(v) if '.' in v else int(v)
         if outEmpty:
            out=v
            outEmpty=0
         elif curLevelType: curLevelLink(v)
         else: curLevelLink[prevKey]=v
      # process part and generate event
      v=None
      if not part or part is ' ' or part is ',': continue
      elif part[0] is ' ': part=part.lstrip()
      if part is '{':
         prevLevelAppend((curLevelType, curLevelLink))
         s={}
         if outEmpty:
            out=s
            outEmpty=0
         elif curLevelType: curLevelLink(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s
         curLevelType=0
      elif part is '[':
         prevLevelAppend((curLevelType, curLevelLink))
         s=[]
         if outEmpty:
            out=s
            outEmpty=0
         elif curLevelType: curLevelLink(s)
         else: curLevelLink[prevKey]=s
         curLevelLink=s.append
         curLevelType=1
      elif (part is ']') or (part is '}'):
         curLevelType, curLevelLink=prevLevelPop()
      elif part=='true':
         if outEmpty:
            out=True
            outEmpty=0
         elif curLevelType: curLevelLink(True)
         else: curLevelLink[prevKey]=True
      elif part=='false':
         if outEmpty:
            out=False
            outEmpty=0
         elif curLevelType: curLevelLink(False)
         else: curLevelLink[prevKey]=False
      elif part=='null':
         if outEmpty:
            out=None
            outEmpty=0
         elif curLevelType: curLevelLink(None)
         else: curLevelLink[prevKey]=None
      else: v=part
   return out
