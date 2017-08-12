#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This package links to dispatcher-execution backends for flaskJSONRPCServer.

"""

from ..utils import magicDict
from parallelWithSocket import execBackend as execBackend_parallelWithSocket
from parallelWithSocketNew import execBackend as execBackend_parallelWithSocketNew
from threaded import execBackend as execBackend_threaded
global execBackendMap

# declaring map of exec-backends
execBackendMap=magicDict({
   'parallelWithSocket':lambda notif: execBackend_parallelWithSocket(saveResult=not(notif)),
   'parallelWithSocketNew':lambda notif: execBackend_parallelWithSocketNew(),
   'threaded':lambda notif: execBackend_threaded(forceNative=False, saveResult=not(notif), sleepBeforeExecute=(0.001 if notif else False)),
   'threadedNative':lambda notif: execBackend_threaded(forceNative=True, saveResult=not(notif), sleepBeforeExecute=(0.01 if notif else False))
})
# backward compatible
# execBackendMap['threadPool']=execBackendMap['threaded']
# execBackendMap['threadPoolNative']=execBackendMap['threadedNative']
