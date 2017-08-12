#!/usr/bin/env python
# -*- coding: utf-8 -*-

__all__=['arrMin', 'arrMax', 'arrMedian', 'arrTrimean', 'arrMode', 'arrAverage', 'oGet', 'arrUnique']

def arrUnique(arr, key=None):
   #unique elements of array
   if not(arr): return []
   tArr1=arr
   if key: tArr1=[key(s) for s in tArr1]
   tArr1=set(list(tArr1))
   return tArr1

def arrFind(arr, item, default=-1):
   return oGet(arr, item, default=default)

def oGet(o, key, default=None):
   try: return o[key]
   except: return default

def arrAverage(arr):
   if not len(arr): return 0
   return sum(arr)/float(len(arr))

def arrMax(arr, key=None, returnIndex=False):
   if not len(arr): return 0 if not returnIndex else -1
   elif len(arr)==1: return arr[0] if not returnIndex else 0
   if key: arr=[key(s) for s in arr]
   if not returnIndex:
      try: return max(arr)
      except: return None
   else:
      try: return arrFind(arr, max(arr))
      except: -1

def arrMin(arr, key=None, returnIndex=False):
   if not len(arr): return 0 if not returnIndex else -1
   elif len(arr)==1: return arr[0] if not returnIndex else 0
   if key: arr=[key(s) for s in arr]
   if not returnIndex:
      try: return min(arr)
      except: return None
   else:
      try: return arrFind(arr, min(arr))
      except: -1

def arrMedian(arr, arrMap=None):
   if not len(arr): return 0
   elif len(arr)==1: return arr[0]
   if not arrMap:
      arrMap=sorted(range(len(arr)), key=lambda i:arr[i], reverse=False)
   if len(arrMap)%2:
      median=arr[arrMap[len(arrMap)/2]]
   else:
      median=(arr[arrMap[(len(arrMap)-1)/2]]+arr[arrMap[(len(arrMap)-1)/2+1]])/2.0
   return median

def arrQuartiles(arr, arrMap=None, method=1):
   if not len(arr): return 0
   elif len(arr)==1: return arr[0]
   if not arrMap:
      arrMap=sorted(range(len(arr)), key=lambda i:arr[i], reverse=False)
   median=arrMedian(arr, arrMap)
   def getHalve(isLow=True, includeM=False):
      tArr=[]
      for i in arrMap:
         if isLow and (arr[i]<=median if includeM else arr[i]<median): tArr.append(arr[i])
         if not isLow and (arr[i]>=median if includeM else arr[i]>median): tArr.append(arr[i])
      tArrMap=range(len(tArr))
      return tArr, tArrMap
   if method in [1, 2]: #methods "1-Var Stats" and "Tukey's hinges"
      tHalveL, tHalveL_arrMap=getHalve(True, method==2)
      tHalveH, tHalveH_arrMap=getHalve(False, method==2)
      qL=arrMedian(tHalveL, tHalveL_arrMap)
      qH=arrMedian(tHalveH, tHalveH_arrMap)
   elif method==3:
      tHalveL1, tHalveL1_arrMap=getHalve(True, False)
      tHalveH1, tHalveH1_arrMap=getHalve(False, False)
      qL1=arrMedian(tHalveL1, tHalveL1_arrMap)
      qH1=arrMedian(tHalveH1, tHalveH1_arrMap)
      tHalveL2, tHalveL2_arrMap=getHalve(True, True)
      tHalveH2, tHalveH2_arrMap=getHalve(False, True)
      qL2=arrMedian(tHalveL2, tHalveL2_arrMap)
      qH2=arrMedian(tHalveH2, tHalveH2_arrMap)
      qL=(qL1+qL2)/2.0
      qH=(qH1+qH2)/2.0
   return qL, median, qH

def arrTrimean(arr, arrMap=None):
   """
    >>> trimean([1, 1, 3, 5, 7, 9, 10, 14, 18])
    6.75
    >>> trimean([0, 1, 2, 3, 4, 5, 6, 7, 8])
    4.0
   """
   if not len(arr): return 0
   elif len(arr)==1: return arr[0]
   if not arrMap:
      arrMap=sorted(range(len(arr)), key=lambda i:arr[i], reverse=False)
   q1, m, q3=arrQuartiles(arr, arrMap, method=2)
   trimean=(q1+2.0*m+q3)/4.0
   return trimean

def arrMode(arr, rank=0, returnIndex=False):
   arrMap={}
   for i, v in enumerate(arr):
      if v not in arrMap: arrMap[v]=[]
      arrMap[v].append(i)
   kMap=arrMap.keys()
   if rank>=len(kMap):
      return [] if returnIndex else None
   kMap=sorted(kMap, key=lambda s: len(arrMap[s]), reverse=True)
   k=kMap[rank]
   return arrMap[k] if returnIndex else k

if __name__=='__main__': pass
