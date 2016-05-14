#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os

if __name__=='__main__':
    command=sys.argv[1] if len(sys.argv)>1 else None
    if command in ['-x', '-d', '-l']: #work with examples
        mainPath=os.path.dirname(os.path.realpath(sys.argv[0]))
        if not os.path.isdir(mainPath+'/example'):
            print 'ERROR: Examples not included to package'
            sys.exit(0)
        if command=='-l': #list examples
            for f in sorted(os.listdir(mainPath+'/example')):
                if not os.path.isfile(mainPath+'/example/'+f): continue
                if os.path.splitext(os.path.basename(f))[1]=='.pyc': continue
                with open(mainPath+'/example/'+f, 'r') as ff: s=ff.read()
                if 'import flaskJSONRPCServer' not in s: continue
                print f
            sys.exit(0)
        scriptName=sys.argv[2] if len(sys.argv)>2 else 'simple'
        if not scriptName.endswith('.py'): scriptName+='.py'
        if not os.path.isfile(mainPath+'/example/'+scriptName):
            print 'ERROR: Example "%s" not included to package'%scriptName
            sys.exit(0)
        if command=='-x': #run
            os.system(sys.executable+' '+mainPath+'/example/'+scriptName)
        else: #show path
            print mainPath+'/example/'+scriptName
    elif command=='-v': #show version
        import __init__
        print __init__.__version__
    elif command=='-h': #show help
        print '"-v" for version'
        print '"-l" list names of included examples'
        print '"-x" for run default example'
        print '"-x <name>" for run specific example'
        print '"-d <name>" for show path to specific example'
    else:
        print '"-h" for help'
