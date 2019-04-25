#!/root/Sync/Ubuntu-Practice-Machine/env/lib/python3.6

import cProfile
import pstats
import io
import logging
import os
import time
'''
An older profiler script found here:
    
    https://medium.com/@maxmaxmaxmax/measuring-performance-of-python-
                            based-apps-using-gunicorn-and-cprofile-ee4027b2be41

This is modified jst a bit for python 3, and might be the easiest way for a
broad level view of memory use.  The main culprit appears to be '_pickle.dump'
(builtin method?), but where is that being called and is it avoidable?
'''

profile_limit = int(os.environ.get("profile_limit", 30))
profiler = bool(int(os.environ.get("profiler", 1)))
profile_method = os.environ.get("profile_method")
profile_file = os.environ.get("profile_file")

print("""
      The basic call:
      gunicorn -c ./profile.py app:server

      To limit the profile printout:
      profile_limt=100 gunicorn -c ./profiler.py app:server

      To filter for a particular method and limit printout:
      profile_limit=10 profile_method=methodName gunicorn -c ./profiler.py app:server

      To filter for a particular file:
      profile_file=functions.py gunicorn -c ./profiler.py app:server

      To restrict printouts to element times only:
      profiler=0 gunicorn -c ./profiler.py app:server
""")

if profile_method is not None:
    print("Profiled Method: " + profile_method + '\n')
    method_expr = '\(' + profile_method
if profile_file is not None:
    print("Profiled file: " + profile_file + '\n')
    
    
def profiler_enable(worker, req):
    worker.profile = cProfile.Profile()
    worker.profile.enable()
    worker.log.info("PROFILING %d: %s" % (worker.pid, req.uri))


def profiler_summary(worker, req):
    s = io.StringIO()
    worker.profile.disable()
    ps = pstats.Stats(worker.profile, stream=s).sort_stats('cumulative', 'tottime')
    ps.print_stats(profile_limit, profile_method, profile_file)
    logging.error("\n[%d] [INFO] [%s] URI %s" % (worker.pid, req.method, req.uri))
    logging.error("[%d] [INFO] %s" % (worker.pid, str(s.getvalue())))


def pre_request(worker, req):
    worker.start_time = time.time()
    if profiler is True:
        profiler_enable(worker, req)


def post_request(worker, req, *args):
    total_time = time.time() - worker.start_time
    logging.error("\n[%d] [INFO] [%s] Load Time: %.3fs\n" % (
        worker.pid, req.method, total_time))
    if profiler is True:
        profiler_summary(worker, req)
