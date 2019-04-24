#!/root/Sync/Ubuntu-Practice-Machine/env/lib/python3.6

import cProfile
import pstats
import io
import logging
import os
import time
'''
An older profiler script found here:
https://medium.com/@maxmaxmaxmax/measuring-performance-of-python-based-apps-using-gunicorn-and-cprofile-ee4027b2be41

This is modified jst a bit for python 3, and might be the easiest way for a broad level view of memory use.
The main culprit appears to be '_pickle.dump' (builtin method?), but where is that being called and is it
avoidable?
'''

PROFILE_LIMIT = int(os.environ.get("PROFILE_LIMIT", 30))
PROFILER = bool(int(os.environ.get("PROFILER", 1)))

print("""
# ** USAGE:
$ PROFILE_LIMIT=100 gunicorn -c ./wsgi_profiler.py wsgi
# ** TIME MEASUREMENTS ONLY:
$ PROFILER=0 gunicorn -c ./wsgi_profiler.py wsgi
""")


def profiler_enable(worker, req):
    worker.profile = cProfile.Profile()
    worker.profile.enable()
    worker.log.info("PROFILING %d: %s" % (worker.pid, req.uri))


def profiler_summary(worker, req):
    s = io.StringIO()
    worker.profile.disable()
    ps = pstats.Stats(worker.profile, stream=s).sort_stats('time', 'cumulative')
    ps.print_stats(PROFILE_LIMIT)

    logging.error("\n[%d] [INFO] [%s] URI %s" % (worker.pid, req.method, req.uri))
    logging.error("[%d] [INFO] %s" % (worker.pid, str(s.getvalue())))


def pre_request(worker, req):
    worker.start_time = time.time()
    if PROFILER is True:
        profiler_enable(worker, req)


def post_request(worker, req, *args):
    total_time = time.time() - worker.start_time
    logging.error("\n[%d] [INFO] [%s] Load Time: %.3fs\n" % (
        worker.pid, req.method, total_time))
    if PROFILER is True:
        profiler_summary(worker, req)
