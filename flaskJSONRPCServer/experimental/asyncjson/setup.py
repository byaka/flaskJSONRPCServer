# -*- coding: utf-8 -*-
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

setup(
   name='asyncjson_c',
   ext_modules=[
      Extension('asyncjson_c', ['asyncjson_c.pyx'], language='c++')
   ],
   cmdclass={'build_ext': build_ext}
)
