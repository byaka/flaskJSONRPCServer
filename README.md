[![PyPI version](https://img.shields.io/pypi/v/flaskJSONRPCServer.svg)](https://pypi.python.org/pypi/flaskJSONRPCServer)
[![PyPI downloads](https://img.shields.io/pypi/dm/flaskJSONRPCServer.svg)](https://pypi.python.org/pypi/flaskJSONRPCServer)
[![License](https://img.shields.io/pypi/l/flaskJSONRPCServer.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

# flaskJSONRPCServer
This library is an implementation of the JSON-RPC specification. It supports only 2.0 specification for now, which includes batch submission, keyword arguments, etc.

## Comments, bug reports
flaskJSONRPCServer resides on **github**. You can file issues or pull requests [there](https://github.com/byaka/flaskJSONRPCServer/issues).

## Requirements
 - Python >=2.6
 - Flask >= 0.10 (not tested with older version)
 - Gevent >= 1.0 (optionally)

## Pros

 - Lib tested over **highload** (>=60 connections per second, 24/7 and it's not simulation) with **Gevent** enabled and no stability issues or memory leak (this is why i'm wrote this library)
 - Auto **CORS**
 - Simple switching to **Gevent** as backend
 - Auto fallback to **JSONP** on GET requests (for old browsers, that don't support CORS like **IE**<10)
 - Dispatchers can simply get info about connection (**IP**, **Cookies**, **Headers**)
 - Dispatchers can simply set **Cookies**, change output **Headers**, change output format for **JSONP** requests
 - Lib can be simply integreted with another **Flask** app on the same IP:PORT

## Cons
 - No **documentation**, only examples below (sorry, i not have time for now)
 - Lib not handle **Notification** requests fully (for now client waiting, while server processes requests)
 - Lib not has **decorators**, so it not a "Flask-way" (this can be simply added, but i not use decorators, sorry)

## Install
```pip install flaskJSONRPCServer```

## Examples
Simple server
```python
import sys, time, random
sys.path.append('/var/python/libs/')
sys.path.append('/var/python/')
sys.path.append('/home/python/libs/')
sys.path.append('/home/python/')

from flaskJSONRPCServer import flaskJSONRPCServer

class mySharedMethods:
   def random(self, mult=65536):
      # Sipmly return random value (0..mult)
      return int(random.random()*mult)

def echo(data='Hello world!'):
   # Simply echo
   return data

def myip(_connection=None):
   # Return client's IP
   return 'Hello, %s!'%(_connection.ip)

def setcookie(_connection=None):
   # Set cookie to client
   _connection.cookiesOut.append({'name':'myTestCookie', 'value':'Your IP is %s'%_connection.ip})
   return 'Setted'

def block():
   # Test for notification request. When it fully implemented, client must  not wait for compliting this function
   time.sleep(10)
   return 'ok'

def stats(_connection=None):
   #calculate connections per second
   tArr1={'connPerSec_now':_connection.server.connPerMinute.count/60.0, 'connPerSec_old':_connection.server.connPerMinute.oldCount/60.0, 'speedStats':{}}
   #calculate spped stats
   for k, v in _connection.server.speedStats.items():
      tArr1['speedStats'][k+'_min']=min(v)
      tArr1['speedStats'][k+'_max']=max(v)
      tArr1['speedStats'][k+'_average']=sum(v)/float(len(v))
   return tArr1

def big(_connection=None):
   _connection.allowCompress=True #allow compression for this method
   s="""
They say that if you sat an infinite number of monkeys with an infinite number of typewriters, then they would write the complete works of Shakespeare. This is known as the Infinite Monkey Theorem. I always feel it would be nice to try the actual experiment out. I mean all these monkeys with typewriters would be kinda cool.

However wouldn't it be easier to get one monkey and one typewriter and give him an infinite amount of time to see how he goes?

Although in theory it sounds simpler, getting hold of even a single monkey is not that easy.

But what if we created a simulated monkey in Python? Now we are talking! That would be easy, and unlike a real monkey our simulated one could work all day and all night. No food required.

Sounds like a plan for a blog post.

However I want to give our virtual monkey a chance. If he managed to type the complete works of Shakespeare without worrying about punctuation, we would be happy right? Same goes for capital letters, let's just ignore them for now. We want to give him a fighting chance of completing his task.

To help you get started I have taken a text file of the complete works of Shakespeare, and removed all punctuation and made all letters small. If any of you are thinking I did that by hand, think again. Python is your friend for automating tasks like that.

Because the complete works is a large tome, I have also included a similar file, with just Hamlet. You can choose which one you want your monkey to attempt!

As with all my blog posts I will give you the complete program first of all. Have a read through this and see how much of it you understand. Try and figure out those sections you don’t. I will then go through the program a line at a time explaining it in more detail.
We do this by using scriptRead.count(monkeyTyped) >= 1 What does that even mean? Well we take the complete works of Shakespeare stored in scriptRead, and we do a count of how many times the thing in the brackets appears. If we put monkeyTyped into the brackets then it will count how many times monkeyCount appeared in scriptRead. We only need it to appear once but if it appears more than once, then that is ok as well. We check this with the greater than or equal to symbol >=.

But the line also has monkeyTyped = ''. Why is that? Well when we start off this while loop the monkey has not typed anything, as we have set the variable to = '' , which means an empty string. This would mean our while loop would be false straight away, and our monkey would never start typing.

To get around this we us an or condition. We check that monkeyTyped is '' or scriptRead.count(monkeyTyped) >= 1

The next line is the line which does the actual typing.
We take monkeyTyped and we add the result of (random.choice(string.ascii_lowercase + ' ')) onto it and save the result as monkeyTyped.

What on earth is (random.choice(string.ascii_lowercase + ' ')) ?

Well we want to simulate the monkey typing on a keyboard. We have already said to make it easy we will not ask for punctuation, although we should ask him for a space between words. Thats not too much to ask is it? We also said we will not be too concerned about it being in capital letters.

So random.choice picks something from inside the brackets by random selection. So what have we put in the brackets. The first thing is

string.ascii_lowercase

This creates a string of the lower case ascii letters. i.e

abcdefghijklmnopqrstuvwxyz

We also add onto the end of that a space using ' '

Now remember this has a space between the two speech-marks. This is different from when we are creating a blank string, which doesn't have a space.

Once he has typed a word, the loop will start again and check if what has been typed is in the complete works. If it is he will continue. If not he will go to the else statement.
Here we return what he has typed. However remember we only get to this place if what is typed is not in the complete works. That's no use to us! We will need to remove the last letter of what he typed, as it was that last letter we know to have made perfect Shakespeare prose into gibberish.

So we return monkeyTyped[:-1] which returns everything up to the last letter but not the last letter.

Ok back to where we were in the main program.

Remember we said we would keep track of the number of key presses? Well lets update that now. We know the monkey has just typed a word, so it is easy to determine the size of that word and increase keyPresses by that amount. Oh but the monkey typed a letter which turned his prose into gibberish. We should add that on as well as we want our count to be accurate!
This line checks to see if the number of key presses he has made is a multiple of 10,000. The % checks if keyPresses / 10,000 has no remainder i.e. it is a multiple of 10,000. If it is then it will print the number of key-presses made. This only works if the key-presses are an exact multiple of 10,000. There will be times when the monkey is in the middle of a word when this happen, so it will not report back. However it reports enough to make you realise the monkey is still working and not fallen asleep.

Remember to press F5 to save and run your program.

That is the end of the program. All you need now it to download the complete works of Shakespeare or just Hamlet if thats what you want to use. Use the links below to do that.
   """
   return s

if __name__=='__main__':
   print 'Running api..'
   # Creating instance of server
   #    <blocking>      set is this server async
   #    <cors>          switch auto CORS support
   #    <gevent>        switch to using Gevent as backend
   #    <debug>         switch to logging connection's info from Flask
   #    <log>           switch to logging debug info from flaskJSONRPCServer
   #    <fallback>      switch auto fallback to JSONP on GET requests
   #    <allowCompress> switch auto compression
   server=flaskJSONRPCServer(("0.0.0.0", 7001), blocking=False, cors=True, gevent=False, debug=False, log=True, fallback=True, allowCompress=False)
   # Register dispatcher for all methods of instance
   server.registerInstance(mySharedMethods(), path='/api')
   # Register dispatchers for single functions
   server.registerFunction(setcookie, path='/api')
   server.registerFunction(echo, path='/api')
   server.registerFunction(block, path='/api')
   server.registerFunction(myip, path='/api')
   big._alias='bigdata' #setting alias for method
   server.registerFunction(big, path='/api')
   server.registerFunction(stats, path='/api')
   # Run server
   server.serveForever()
   # Now you can access this api by path http://127.0.0.1:7001/api for JSON-RPC requests
   # Or by path http://127.0.0.1:7001/api/<method>?jsonp=<callback>&(params) for JSONP requests
   #    For example by http://127.0.0.1:7001/api/echo?data=test_data&jsonp=jsonpCallback_129620

```

## License
It is licensed under the Apache License, Version 2.0 ([read](http://www.apache.org/licenses/LICENSE-2.0.html)).
