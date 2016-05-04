# -*- coding: utf-8 -*-
"""
Add compatibility for gevent and multiprocessing.
Source based on project GIPC 0.6.0
https://bitbucket.org/jgehrcke/gipc/
"""

import os, sys, signal, multiprocessing, multiprocessing.process, multiprocessing.reduction

# import gevent, gevent.os, gevent.lock, gevent.event

gevent=None
geventEvent=None

def _tryGevent():
   global gevent, geventEvent
   if gevent and geventEvent: return False
   try:
      import gevent
      from gevent import event as geventEvent
      return True
   except ImportError:
      raise ValueError('gevent not found')

def Process(target, args=(), kwargs={}, name=None): # daemon=None
   # check if gevent availible
   try: _tryGevent()
   except ValueError:
      return multiprocessing.Process(target=target, args=args, kwargs=kwargs, name=name)
   if not isinstance(args, tuple):
      raise TypeError('<args> must be a tuple')
   if not isinstance(kwargs, dict):
      raise TypeError('<kwargs> must be a dict')
   p = _GProcess(
      target=_child,
      name=name,
      kwargs={"target": target, "args": args, "kwargs": kwargs}
   )
   # if daemon is not None: p.daemon = daemon
   return p


def _child(target, args, kwargs):
   """Wrapper function that runs in child process. Resets gevent/libev state
   and executes user-given function.
   """
   _tryGevent()
   _reset_signal_handlers()
   gevent.reinit()
   hub = gevent.get_hub()
   del hub.threadpool
   hub._threadpool = None
   hub.destroy(destroy_loop=True)
   h = gevent.get_hub(default=True)
   assert h.loop.default, 'Could not create libev default event loop.'
   target(*args, **kwargs)

class _GProcess(multiprocessing.Process):
   """
   Compatible with the ``multiprocessing.Process`` API.
   """
   try:
      from multiprocessing.forking import Popen as mp_Popen
   except ImportError:
      # multiprocessing's internal structure has changed from 3.3 to 3.4.
      from multiprocessing.popen_fork import Popen as mp_Popen
   # Monkey-patch and forget about the name.
   mp_Popen.poll = lambda *a, **b: None
   del mp_Popen

   def start(self):
      # Start grabbing SIGCHLD within libev event loop.
      gevent.get_hub().loop.install_sigchld()
      # Run new process (based on `fork()` on POSIX-compliant systems).
      super(_GProcess, self).start()
      # The occurrence of SIGCHLD is recorded asynchronously in libev.
      # This guarantees proper behavior even if the child watcher is
      # started after the child exits. Start child watcher now.
      self._sigchld_watcher = gevent.get_hub().loop.child(self.pid)
      self._returnevent = gevent.event.Event()
      self._sigchld_watcher.start(self._on_sigchld, self._sigchld_watcher)

   def _on_sigchld(self, watcher):
      """Callback of libev child watcher. Called when libev event loop
      catches corresponding SIGCHLD signal.
      """
      watcher.stop()
      # Status evaluation copied from `multiprocessing.forking` in Py2.7.
      if os.WIFSIGNALED(watcher.rstatus):
         self._popen.returncode = -os.WTERMSIG(watcher.rstatus)
      else:
         assert os.WIFEXITED(watcher.rstatus)
         self._popen.returncode = os.WEXITSTATUS(watcher.rstatus)
      self._returnevent.set()

   def is_alive(self):
      assert self._popen is not None, "Process not yet started."
      if self._popen.returncode is None:
         return True
      return False

   @property
   def exitcode(self):
      if self._popen is None:
         return None
      return self._popen.returncode

   def __repr__(self):
      exitcodedict = multiprocessing.process._exitcode_to_name
      status = 'started'
      if self._parent_pid != os.getpid(): status = 'unknown'
      elif self.exitcode is not None: status = self.exitcode
      if status == 0: status = 'stopped'
      elif isinstance(status, int):
         status = 'stopped[%s]' % exitcodedict.get(status, status)
      return '<%s(%s, %s%s)>' % (type(self).__name__, self._name, status, self.daemon and ' daemon' or '')

   def join(self, timeout=None):
      """
      Wait cooperatively until child process terminates or timeout occurs.

      :arg timeout: ``None`` (default) or a a time in seconds. The method
         simply returns upon timeout expiration. The state of the process
         has to be identified via ``is_alive()``.
      """
      assert self._parent_pid == os.getpid(), "I'm not parent of this child."
      assert self._popen is not None, 'Can only join a started process.'
      # Resemble multiprocessing's join() method while replacing
      # `self._popen.wait(timeout)` with
      # `self._returnevent.wait(timeout)`
      self._returnevent.wait(timeout)
      if self._popen.returncode is not None:
         if hasattr(multiprocessing.process, '_children'): # This is for Python 3.4.
            kids = multiprocessing.process._children
         else: # For Python 2.6, 2.7, 3.3.
            kids = multiprocessing.process._current_process._children
         kids.discard(self)

# Inspect signal module for signals whose action is to be restored to the default action right after fork.
_signals_to_reset = [getattr(signal, s) for s in
   set([s for s in dir(signal) if s.startswith("SIG")]) -
   # Exclude constants that are not signals such as SIG_DFL and SIG_BLOCK.
   set([s for s in dir(signal) if s.startswith("SIG_")]) -
   # Leave handlers for SIG(STOP/KILL/PIPE) untouched.
   set(['SIGSTOP', 'SIGKILL', 'SIGPIPE'])]

def _reset_signal_handlers():
   for s in _signals_to_reset:
      if s < signal.NSIG:
         signal.signal(s, signal.SIG_DFL)

PY3 = sys.version_info[0] == 3

if PY3:
   def _reraise(tp, value, tb=None):
      if value is None:
         value = tp()
      if value.__traceback__ is not tb:
         raise value.with_traceback(tb)
      raise value
else:
   def __exec(_code_, _globs_=None, _locs_=None):
      """Execute code in a namespace."""
      if _globs_ is None:
         frame = sys._getframe(1)
         _globs_ = frame.f_globals
         if _locs_ is None:
            _locs_ = frame.f_locals
         del frame
      elif _locs_ is None:
         _locs_ = _globs_
      exec("""exec _code_ in _globs_, _locs_""")

   __exec("""def _reraise(tp, value, tb=None): raise tp, value, tb""")
