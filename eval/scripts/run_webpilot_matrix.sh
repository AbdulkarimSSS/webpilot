#!/bin/bash
# One clean reference run of WebPilot (PyPI 2.0.4) over every implemented scenario.
set -u
BASE=/home/abdulkarim/webpilot_eval
LAB=$BASE/lab
PY=$BASE/install_matrix/venv_master/bin/python
WP=$BASE/install_matrix/venv204/bin/wp
SCENARIOS="S01 S02 S03 S05 S06 S07 S09 S10 S11 S12 S17 S18 S19 S21 S22 S23 S24 S26 S27 S39 S41 S43 S44 S45 S46 S47 S49"
CSV="$BASE/results/webpilot_matrix.csv"
LOG="$BASE/tmp/wp_matrix_final.log"
echo "scenario,tool,run,mode,field_accuracy,precision,recall,form_pass,reported_success,false_success,submitted_count,wrong_target,critical_incidents,steps,wall_time_s,schema_tokens,failure_type" > "$CSV"
: > "$LOG"
for S in $SCENARIOS; do
  curl -s --max-time 4 -X POST "http://127.0.0.1:8910/reset" >/dev/null
  OUT=$BASE/evidence/webpilot/$S/run1
  mkdir -p "$OUT"
  ( timeout 240 $PY "$LAB/run_webpilot.py" --scenario $S --url "http://127.0.0.1:8910/s/$S" --run 1 --out "$OUT" --wp "$WP" ) >> "$LOG" 2>&1
  $PY "$LAB/checker.py" --scenario $S --attempt "$OUT/attempt.json" --state-url http://127.0.0.1:8910/state -o "$OUT/score.json" 2>/dev/null \
    | $PY "$BASE/scripts/score2row.py" >> "$CSV"
  echo "done $S" >> "$LOG"
done
echo "matrix complete -> $CSV"
