data=[]

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

def compute():
   if not len(data): s='No data'
   else:
      s=arrMedian(data)
   return '"compute()" method from rr1 module: %s'%s
