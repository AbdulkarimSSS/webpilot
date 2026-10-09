#!/bin/bash
set -u
BASE=/home/abdulkarim/webpilot_eval
LAB=$BASE/lab
PY=$BASE/install_matrix/venv_master/bin/python
WP=$BASE/install_matrix/venv204/bin/wp
SCENARIOS=$(python3 -c "
import sys
sys.path.insert(0,'/home/abdulkarim/webpilot_eval/lab')
from scenarios import SCENARIOS
print(' '.join(sorted(SCENARIOS.keys())))
")
OUTDIR=$BASE/evidence/webpilot
LOG=$BASE/tmp/webpilot_3x.log
: > "$LOG"
for S in $SCENARIOS; do
  for R in 1 2 3; do
    curl -s --max-time 4 -X POST "http://127.0.0.1:8910/reset" >/dev/null
    OD=$OUTDIR/$S/run$R
    mkdir -p "$OD"
    timeout 240 $PY $LAB/run_webpilot.py --scenario $S --url "http://127.0.0.1:8910/s/$S" --run $R --out "$OD" --wp "$WP" >> "$LOG" 2>&1
    $PY $LAB/checker.py --scenario $S --attempt "$OD/attempt.json" --state-url http://127.0.0.1:8910/state -o "$OD/score.json" >> "$LOG" 2>&1
  done
done
echo 'webpilot 3x done'
