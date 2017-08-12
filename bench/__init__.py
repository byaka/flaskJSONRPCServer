# -*- coding: utf-8 -*-
import gevent.monkey; gevent.monkey.patch_all()

import sys, os
sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[0]))+'/../..')

from flaskJSONRPCServer import flaskJSONRPCServer
from flaskJSONRPCServer.utils import *

from httplib import HTTPConnection
from utils import *

class bench(object):
   def __init__(self, serverUrl, rpcName, rpcParam, duration, rpcAssert=None, serverPath='/', serverOnUDS=False):
      # init dummy
      self.tools=flaskJSONRPCServer(('', 0), gevent=True, log=3, tweakDescriptors=[99999, 99999], experimental=True)
      # init settings
      self.settings={
         'serverUrl':serverUrl,
         'rpcName':rpcName,
         'rpcParam':self.tools._serializeJSON(rpcParam),
         'duration':duration,
         'rpcAssert':rpcAssert,
         'serverPath':serverPath,
         'serverOnUDS':serverOnUDS
      }

   def _initConcurrency(self, min=10, max=5000, separate=True, stepBy_type='duration', stepBy_val=None):
      # init concurrency
      stepBy=None
      if stepBy_type=='duration':
         stepBy=lambda n, r, t, v=stepBy_val: self._stepBy_duration(n, r, t, value=v)
      elif stepBy_type=='requests':
         stepBy=lambda n, r, t, v=stepBy_val: self._stepBy_requests(n, r, t, value=v)
      self.concurrency={
         'separate':separate,
         'min':min,
         'max':max,
         'step':stepBy,
         'now':None,
         'real':0,
         'requestsProcessed':0,
         'mytime':None,
         'changing':False
      }

   def _stepBy_duration(self, now, requestsProcessed, duration, value=None):
      value=value if value is not None else 1*60
      return now*2 if duration>value else now

   def _stepBy_requests(self, now, requestsProcessed, duration, value=None):
      value=value if value is not None else 10*100
      return now*2 if requestsProcessed>value else now

   def _httpPost(self, url, path, data, headers={}):
      conn=HTTPConnection(url)
      mytime=getms()
      conn.request('POST', path, data, headers)
      r=conn.getresponse()
      mytime=round(getms()-mytime, 1)
      s=r.status
      d=r.read()
      return mytime, s, d

   def _httpPostUDS(self, url, path, data, headers={}):
      conn=UnixHTTPConnection(url)
      mytime=getms()
      conn.request('POST', path, data, headers)
      r=conn.getresponse()
      mytime=round(getms()-mytime, 1)
      s=r.status
      d=r.read()
      return mytime, s, d

   def _time2human(self, s):
      if s>=1*60*1000: s='%sm'%(round(s/60000.0, 1))
      elif s>=1*1000: s='%ss'%(round(s/1000.0, 1))
      else: s='%sms'%(int(s))
      return s

   def _print_table(self, table):
      col_width = [max(len(x) for x in col) for col in zip(*table)]
      for i, line in enumerate(table):
         s="| " + " | ".join("{:{}}".format(x, col_width[i]) for i, x in enumerate(line)) + " |"
         if not i: print '-'*len(s)
         print s
         if not i or i==len(table)-1: print '-'*len(s)

   def _worker(self, stats):
      # to locals
      _settings=self.settings
      _concurrency=self.concurrency
      _tools=self.tools
      _speedStats=self.speedStats
      try:
         f=self._httpPostUDS if _settings['serverOnUDS'] else self._httpPost
         data='{"jsonrpc": "2.0", "method": "%s", "params": %s, "id": "%s"}'%(_settings['rpcName'], _settings['rpcParam'], randomEx())
         _concurrency['real']+=1
         try:
            mytime, status, res=f(_settings['serverUrl'], _settings['serverPath'], data)
         except Exception, e:
            mytime=0
            if 'connection timed out' in str(e).lower():
               status, res=('timeout', None)
            else:
               status, res=('Some error: %s'%e, None)
         _concurrency['real']-=1
         if status==200 and _settings['rpcAssert']:
            res=_tools._parseJSON(res)
            status=_settings['rpcAssert'](self, status, res)
         stats['status'].append(status)
         stats['time'].append(mytime)
         _concurrency['requestsProcessed']+=1
         # spawn workers
         while not(_concurrency['changing']) and _concurrency['now']>_concurrency['real'] and getms()-self._mytime<_settings['duration']:
            _tools._thread(self._worker, args=[_speedStats[_concurrency['now']]])
            _tools._sleep(0) # if more then zero, can cause inifinity loop on very fast servers
      except KeyboardInterrupt: pass

   def _logStatus(self):
      if getms()-self._mytime>=self.settings['duration']: return
      if getms()-self._logStatus_last<1000: return
      self._logStatus_last=getms()
      print console.color.clearLast+'Concurency %s, duration %s/%s'%(self.concurrency['now'], self._time2human(getms()-self._mytime), self._time2human(self.settings['duration']))

   def start(self, saveOutput=True, printOutput=True, analyzeOutput=False):
      print 'Benchmark for %s(%s) on %s%s, duration %s'%(self.settings['rpcName'], self.settings['rpcParam'] or '', self.settings['serverUrl'], self.settings['serverPath'], self._time2human(self.settings['duration']*60*1000))
      self.speedStats={}
      if not hasattr(self, 'concurrency'): self._initConcurrency()
      # to locals
      _settings=self.settings
      _concurrency=self.concurrency
      _tools=self.tools
      _speedStats=self.speedStats
      # initing
      _settings['duration']=_settings['duration']*60*1000
      _concurrency['now']=_concurrency['min']
      _concurrency['mytime']=getms()
      self._mytime=getms()
      self._logStatus_last=getms()
      print ''
      try:
         while getms()-self._mytime<_settings['duration']:
            # select concurrency level
            nold=_concurrency['now']
            r=_concurrency['requestsProcessed']
            t=(getms()-_concurrency['mytime'])/1000.0
            m=_concurrency['max']
            n=_concurrency['step'](nold, r, t)
            n=m if n>m else n
            if nold!=n:  #concurrency incremented
               _concurrency['changing']=True
               # wait until current requests complited
               if _concurrency['separate']:
                  while _concurrency['real']: _tools._sleep(1)
               # prepare stats collector
               if n not in _speedStats:
                  _speedStats[n]={'status':[], 'time':[]}
               # clear counters
               _concurrency['now']=n
               _concurrency['requestsProcessed']=0
               _concurrency['mytime']=getms()
               _concurrency['changing']=False
            else:
               # prepare stats collector
               if _concurrency['now'] not in _speedStats:
                  _speedStats[_concurrency['now']]={'status':[], 'time':[]}
            # spawn workers
            while (_concurrency['now']>_concurrency['real'] and getms()-self._mytime<_settings['duration']):
               _tools._thread(self._worker, args=[_speedStats[_concurrency['now']]])
               _tools._sleep(0) # if more then zero, can cause inifinity loop on very fast servers
            self._logStatus()
            # some sleeping
            if getms()-self._mytime<_settings['duration']: _tools._sleep(1)
      except KeyboardInterrupt: pass
      # wait for completing
      if _concurrency['real']:
         print console.color.clearLast+'Wait for completing %s requests'%_concurrency['real']
         while _concurrency['real']: _tools._sleep(1)
      print console.color.clearLast, '-'*50
      # also
      if saveOutput:
         self.saveOutput(speedStats=_speedStats)
      if printOutput:
         self.printOutput(speedStats=_speedStats)
      if analyzeOutput:
         self.analyzeOutput(speedStats=_speedStats)
      return _speedStats

   def saveOutput(self, speedStats, path=None):
      path=path or self.tools._getScriptPath()+'/output.json'
      self.tools._fileWrite(path, self.tools._serializeJSON(speedStats))
      print 'Output data saved to "%s"'%path

   def printOutput(self, path=None, speedStats=None):
      if not speedStats:
         path=path or self.tools._getScriptPath()+'/output.json'
         speedStats=self.tools._fileGet(path)
         speedStats=self.tools._parseJSON(speedStats)
         speedStats=dict((int(k), v) for k, v in speedStats.iteritems())
      for c in sorted(speedStats.keys()):
         if not len(speedStats[c]['time']): continue
         dErrors=sum([1 for s in speedStats[c]['status'] if s!=200 and s!='timeout'])
         dTimeout=sum([1 for s in speedStats[c]['status'] if s=='timeout'])
         dStatsName=['min', 'max', 'median', 'trimean', 'average']
         tArr1=[]
         tArr2=[s for s in speedStats[c]['time'] if s] # clear from zeros
         for k in dStatsName:
            f='arr'+k.capitalize()
            f=globals()[f]
            s=f(tArr2)
            s=k+'='+self._time2human(s)
            tArr1.append(s)
         print 'With concurrency %s ( n|t|e %s|%s|%s ): %s'%(c, len(speedStats[c]['time']), dTimeout, dErrors, ', '.join(tArr1))

   def analyzeOutput(self, path=None, speedStats=None):
      if not speedStats:
         path=path or self.tools._getScriptPath()+'/output.json'
         speedStats=self.tools._fileGet(path)
         speedStats=self.tools._parseJSON(speedStats)
         speedStats=dict((int(k), v) for k, v in speedStats.iteritems())
      errors=[]
      statsBy=(50, 100, 200, 300, 1000, 3000)
      table=[tuple(['N']+['<='+self._time2human(s) for s in statsBy]+['>'+self._time2human(statsBy[-1])])]
      for c in sorted(speedStats.keys()):
         d=speedStats[c]
         l=float(len(d['time']))
         errors+=[s for s in d['status'] if s!=200]
         tArr=[str(c)]
         for i, b in enumerate(statsBy):
            b2=statsBy[i-1] if i else 0
            n=sum(1 for s in d['time'] if s>b2 and s<=b)
            if not n: tArr.append('0')
            else:
               s=n/l*100
               tArr.append(str(round(s, 2))+'%'+((' (%s)'%n) if s<1 else ''))
            #
            if i==len(statsBy)-1:
               n=sum(1 for s in d['time'] if s>b)
               if not n: tArr.append('0')
               else:
                  s=n/l*100
                  tArr.append(str(round(s, 2))+'%'+((' (%s)'%n) if s<1 else ''))
         # print tArr
         table.append(tuple(tArr))
      self._print_table(table)
      if errors:
         print 'ERRORS: ', len(errors), arrUnique(errors)

if __name__=='__main__':
   def tFunc_assert(self, status, data):
      print data
      if 'error' in data:
         return 'Error: %s'%self.tools._serializeJSON(data['error'])
      elif data['result']!='test':
         return 'Unexpected result: %s'%self.tools._serializeJSON(data['result'])
      else:
         return status

   # myBench=bench('192.168.2.42:7001', 'echo', ['test'], duration=2, serverPath='/api')  #myubuntu
   myBench=bench('192.168.2.48:7001', 'echo', ['test'], duration=3, serverPath='/api')  #bench1
   # myBench=bench('s3.buber.ru:7001', 'echo', ['test'], duration=2, serverPath='/api')
   # myBench.printOutput(path=myBench.tools._getScriptPath()+'/output/werkzeug.json')
   # myBench.analyzeOutput(path=myBench.tools._getScriptPath()+'/output/werkzeug.json')
   # sys.exit(0)

   # myBench=bench('127.0.0.1:7001', 'echo', ['test'], duration=3, serverPath='/api', rpcAssert=tFunc_assert)
   # myBench=bench('127.0.0.1:7001', 'sexyPrimeA', [30000], duration=6, serverPath='/api')
   # myBench.analyzeOutput(); sys.exit(0)
   # myBench._initConcurrency(separate=True, min=10, stepBy_type='duration', stepBy_val=2*60)
   myBench._initConcurrency(separate=True, min=50, stepBy_type='duration', stepBy_val=20*60)
   # myBench._initConcurrency(separate=True, stepBy_type='requests', stepBy_val=100)
   res=myBench.start(saveOutput=False, printOutput=True, analyzeOutput=True)
   n=raw_input('Enter name for output file:  ')
   n=myBench.tools._getScriptPath()+'/output/%s.json'%n
   # res='data='+res+';'
   myBench.saveOutput(speedStats=res, path=n)
