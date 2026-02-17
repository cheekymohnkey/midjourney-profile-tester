#!/usr/bin/env zsh
# Helper to setup and run the midjourney-profile-tester Streamlit app
# Usage: ./scripts/run_app.zsh setup | start-local [--port 60080] [--bg] [--headful] | start-s3 [--port N] [--bg] | stop | logs

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
VENV_DIR=".venv"
PID_FILE="/tmp/streamlit_server_pid"
OUT_LOG="/tmp/streamlit_stdout.log"
ERR_LOG="/tmp/streamlit_stderr.log"
DEFAULT_PORT=60080

show_help() {
  cat <<-EOF
Usage: $0 <command> [options]

Commands:
  setup               Create virtualenv and install requirements
  start-local         Run with local filesystem (USE_S3=false TEST_AI=true)
    Options: --port N    Port (default $DEFAULT_PORT)
             --bg        Run in background (writes pid to $PID_FILE)
             --headful   Run with Streamlit headful mode (opens browser)
  start-s3            Run with S3 enabled (USE_S3=true TEST_AI=false)
    Options: --port N --bg
  stop                Stop background Streamlit started by this script
  stop-port           Stop any process listening on a port (default 8555)
  logs                Tail app debug logs
  help                Show this message

Examples:
  $0 setup
  $0 start-local --port 60080 --bg
  $0 start-s3 --port 60080

EOF
}

stop_port() {
  local port="${1:-8555}"
  echo "Stopping processes listening on port $port"

  # Try macOS-style lsof filter first, fallback to generic lsof
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
  fi

  # If lsof didn't find anything, try ss (Linux) to extract pids from users(...) field
  if [[ -z "$pids" ]] && command -v ss >/dev/null 2>&1; then
    pids=$(ss -ltnp 2>/dev/null | awk -v P=":$port" '
      $0 ~ P { for(i=1;i<=NF;i++) if($i ~ /pid=/) { pid=$i; sub(/.*pid=/,"",pid); sub(/,.*/,"",pid); printf "%s ", pid } }
    ' | tr -s ' ')
  fi

  # If still not found, try fuser (common on many Linuxes)
  if [[ -z "$pids" ]] && command -v fuser >/dev/null 2>&1; then
    # fuser prints PIDs separated by whitespace
    pids=$(fuser -n tcp "$port" 2>/dev/null || true)
  fi

  if [[ -z "$pids" ]]; then
    echo "No process found listening on port $port"
    return 0
  fi

  echo "Found PIDs: $pids"
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "Sending SIGTERM to $pid"
      kill "$pid" || true
    fi
  done

  # Allow graceful shutdown
  sleep 1

  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "PID $pid still alive; sending SIGKILL"
      kill -9 "$pid" || true
    fi
  done
  return 0
}

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtualenv in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
  fi
}

run_pip_install() {
  ensure_venv
  echo "Installing requirements..."
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  if [[ -f requirements.txt ]]; then
    "$VENV_DIR/bin/python" -m pip install -r requirements.txt
  else
    echo "No requirements.txt found"
  fi
}

start_streamlit() {
  local use_s3="$1"
  local test_ai="$2"
  local port="$3"
  local bg="$4"
  local headful="$5"

  ensure_venv

  export USE_S3="$use_s3"
  export TEST_AI="$test_ai"

  echo "Starting app: USE_S3=$USE_S3 TEST_AI=$TEST_AI port=$port headful=$headful"

  CMD=("$VENV_DIR/bin/python" -m streamlit run midjourney_profile_tester.py --server.port "$port")
  if [[ "$headful" == "true" ]]; then
    CMD+=(--server.headless false)
  else
    CMD+=(--server.headless true)
  fi

  if [[ "$bg" == "true" ]]; then
    echo "Logging stdout -> $OUT_LOG, stderr -> $ERR_LOG"
    nohup "${CMD[@]}" > "$OUT_LOG" 2> "$ERR_LOG" &
    echo $! > "$PID_FILE"
    echo "Started streamlit pid $(cat $PID_FILE)"
  else
    exec "${CMD[@]}"
  fi
}

stop_streamlit() {
  if [[ -f "$PID_FILE" ]]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping pid $pid"
      kill "$pid" || true
      sleep 0.5
      if kill -0 "$pid" 2>/dev/null; then
        echo "PID still alive, sending SIGKILL"
        kill -9 "$pid" || true
      fi
    else
      echo "No process $pid running"
    fi
    rm -f "$PID_FILE"
  else
    echo "No pid file ($PID_FILE) found"
  fi
}

tail_logs() {
  tail -f /tmp/save_analysis_debug.log /tmp/ai_handler.log /tmp/ai_click.log "$OUT_LOG" "$ERR_LOG" 2>/dev/null || true
}

# parse args
if [[ $# -lt 1 ]]; then
  show_help
  exit 1
fi

cmd="$1"
shift || true

case "$cmd" in
  help)
    show_help
    ;;

  setup)
    run_pip_install
    ;;

  start-local)
    PORT=$DEFAULT_PORT
    BG=false
    HEADFUL=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --port)
          PORT="$2"; shift 2;;
        --bg)
          BG=true; shift;;
        --headful)
          HEADFUL=true; shift;;
        *) echo "Unknown option $1"; exit 1;;
      esac
    done
    start_streamlit false true "$PORT" "$BG" "$HEADFUL"
    ;;

  start-s3)
    PORT=$DEFAULT_PORT
    BG=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --port)
          PORT="$2"; shift 2;;
        --bg)
          BG=true; shift;;
        *) echo "Unknown option $1"; exit 1;;
      esac
    done
    start_streamlit true false "$PORT" "$BG" false
    ;;

  stop)
    stop_streamlit
    ;;
  stop-port)
    PORT_ARG=$DEFAULT_PORT
    if [[ $# -gt 0 ]]; then
      case "$1" in
        --port)
          PORT_ARG="$2"; shift 2;;
        *) PORT_ARG="$1"; shift;;
      esac
    fi
    stop_port "$PORT_ARG"
    ;;

  logs)
    tail_logs
    ;;

  *)
    echo "Unknown command: $cmd"
    show_help
    exit 1
    ;;
esac
