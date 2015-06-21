#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
   name              ='flaskJSONRPCServer',
   version           =__import__('flaskJSONRPCServer').__version__,
   packages          =find_packages(exclude=["tests.*", "tests"]),
   requires          =['python (>= 2.6)', 'flask (>= 0.10)'],
   install_requires  =['flask>=0.10'],
   extras_require    ={
                        'gevent': ['gevent>=1.0']
                     },
   description       ='A Python JSON-RPC over HTTP with flask and gevent',
   long_description  =open('README.rst').read(),
   author            ='Jhon Byaka',
   author_email      ='byaka.life@gmail.com',
   url               ='https://byaka.github.io/flaskJSONRPCServer/',
   download_url      ='https://github.com/byaka/flaskJSONRPCServer/tarball/master',
   license           ='Apache 2.0',
   keywords          ='flask json-rpc jsonrpc gevent',
   classifiers       =[
      'Environment :: Web Environment',
      'Framework :: Flask',
      'Intended Audience :: Developers',
      'Operating System :: OS Independent',
      'Programming Language :: Python',
   ],
)
