#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This package links to dispatcher-execution backends for flaskJSONRPCServer.

"""

from parallelWithSocket import execBackend as execBackend_parallelWithSocket
from threaded import execBackend as execBackend_threaded
global execBackendMap

# declaring map of exec-backends
execBackendMap={
   'parallelWithSocket':lambda notif: execBackend_parallelWithSocket(saveResult=not(notif)),
   'threaded':lambda notif: execBackend_threaded(),
   'threadedNative':lambda notif: execBackend_threaded(forceNative=True)
}
# backward compatible
execBackendMap['threadPool']=execBackendMap['threaded']
execBackendMap['threadPoolNative']=execBackendMap['threadedNative']
