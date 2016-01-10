# Experimental futures
This package contains experimental extensions for flaskJSONRPCServer. This mean that this extensions need more testing or they breaks some functionality.

### moreAsync
Tricky implementations of some servers methods that add async executing. It very useful in Gevent backend. When server start some methods (like compression or hashing) with large data, it hang all server. It very big performance problem and this extension solve this. When **moreAsync** enabled, some jobs run in separate threads and main thread only wait for completing. And while wait, it can do another jobs.

For now **moreAsync** extend this methods:

 - compressGZIP (min input size **1mb**)
 - sha256 (min input size **200mb**)
 - sha1 (min input size **300mb**)

*Perfomance issues*: none

*Testing*: need more

*Broken functionality*: none

### asyncJSON
Pseudo-async implementation of JSON parser and dumper. It allow to switch context (switching to another greenlet vs thread) every given seconds. Useful on processing large data. 

It supports:

- dumps (min input size **1mb**)
- loads (min input size **10mb**)

*Perfomance issues*: 3-5 times slower on serialization and 10 times slower on parsing

*Testing*: need more

*Broken functionality*: for now it not implements type-extending (“default” param), disabling escaping of non-ASCII characters ( “ensure_ascii” param) and checking circular reference (“check_circular” param)

### uJSON
Extremely fast JSON-backend.

*Perfomance issues*: none

*Testing*: need more

*Broken functionality*: for now it not implements type-extending (“default” param) and disabling escaping of non-ASCII characters ( “ensure_ascii” param)