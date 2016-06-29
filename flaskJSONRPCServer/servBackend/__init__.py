#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This package links to serving backends for flaskJSONRPCServer.

"""

from ..utils import magicDict
from useWsgiex import servBackend as servBackend_wsgiex
from usePywsgi import servBackend as servBackend_pywsgi
from useWerkzeug import servBackend as servBackend_werkzeug
from useFake import servBackend as servBackend_fake
global servBackendMap

# declaring map of exec-backends
servBackendMap=magicDict({
   'wsgiex':servBackend_wsgiex,
   'pywsgi':servBackend_pywsgi,
   'werkzeug':servBackend_werkzeug,
   'fake':servBackend_fake,
})
