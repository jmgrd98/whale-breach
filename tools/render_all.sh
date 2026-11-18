#!/bin/sh
# Renders the film as eight short Blender jobs (27 frames each), four at a time.
cd "$(dirname "$0")/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
job() { $B -b -P film/whale_breach.py -- --anim $1 $2 > logs/job_$1.log 2>&1; }
(job 0 26;  job 108 134) &
(job 27 53; job 135 161) &
(job 54 80; job 162 188) &
(job 81 107; job 189 215) &
wait
