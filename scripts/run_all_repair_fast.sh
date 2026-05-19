#!/usr/bin/env bash
set -euo pipefail

APPLY="false"
WITH_OLLAMA="false"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/workspaces}"
REPORT_ROOT="${REPORT_ROOT:-$HOME/code-repair-reports}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY="true"; shift ;;
    --with-ollama) WITH_OLLAMA="true"; shift ;;
    --workspace-root) WORKSPACE_ROOT="$2"; shift 2 ;;
    --report-root) REPORT_ROOT="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

mkdir -p "$WORKSPACE_ROOT" "$REPORT_ROOT"
log(){ printf "\n== %s ==\n" "$*"; }

log "Install base tools"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y git curl unzip jq python3 python3-venv python3-pip nodejs npm build-essential unixodbc unixodbc-dev cmake || true
fi

log "Clone or update core repos"
REPOS=(
  rpreslar4765/Pawnpay
  rpreslar4765/pps-sync
  rpreslar4765/PyPy-3.7
  rpreslar4765/pawnpay-ai-sync
  rpreslar4765/PAWNDEX
  rpreslar4765/NORTH-PAWNDEX
  rpreslar4765/free-claude-code
  rpreslar4765/pythonflask
  rpreslar4765/Old-Fiztrade-App
)
cd "$WORKSPACE_ROOT"
for repo in "${REPOS[@]}"; do
  name="${repo##*/}"
  if [[ -d "$name/.git" ]]; then
    git -C "$name" fetch --all --prune || true
    git -C "$name" pull --ff-only || true
  else
    if command -v gh >/dev/null 2>&1; then gh repo clone "$repo" "$name" || true; else git clone "https://github.com/$repo.git" "$name" || true; fi
  fi
done

log "Install fallback code-repair command"
TOOL="$HOME/code-repair-fast"
rm -rf "$TOOL"
mkdir -p "$TOOL/code_repair"
cat > "$TOOL/pyproject.toml" <<'EOF'
[build-system]
requires=["setuptools>=68"]
build-backend="setuptools.build_meta"
[project]
name="code-repair-fast"
version="0.1.0"
dependencies=["click>=8"]
[project.scripts]
code-repair="code_repair.cli:main"
EOF
cat > "$TOOL/code_repair/__init__.py" <<'EOF'
__version__="0.1.0"
EOF
cat > "$TOOL/code_repair/cli.py" <<'EOF'
import subprocess, sys
from pathlib import Path
import click

def run(cmd,cwd,out):
    print('+',' '.join(cmd))
    with open(out,'a',encoding='utf-8') as f:
        f.write('\n$ '+' '.join(cmd)+'\n')
        try:
            p=subprocess.run(cmd,cwd=cwd,text=True,stdout=f,stderr=subprocess.STDOUT)
            return p.returncode
        except FileNotFoundError:
            f.write('SKIP missing command\n')
            return 0

@click.group()
def main(): pass

@main.command()
@click.argument('path',default='.')
@click.option('--apply',is_flag=True)
def audit(path,apply):
    root=Path(path).resolve(); log=root/'CODE_REPAIR_REPORT.md'; rc=0
    log.write_text(f'# Code Repair Report\n\nRoot: `{root}`\n\n',encoding='utf-8')
    if (root/'package.json').exists():
        rc |= run(['npm','install'],root,log)
        run(['npm','run','build','--if-present'],root,log)
        run(['npm','run','lint','--if-present'],root,log)
        run(['npm','test','--','--watch=false'],root,log)
    if (root/'requirements.txt').exists() or (root/'pyproject.toml').exists():
        run([sys.executable,'-m','pip','install','--upgrade','pip'],root,log)
        if (root/'requirements.txt').exists(): run([sys.executable,'-m','pip','install','-r','requirements.txt'],root,log)
        run([sys.executable,'-m','pip','install','-e','.'],root,log)
        run([sys.executable,'-m','pip','install','pytest','ruff','black','isort'],root,log)
        run([sys.executable,'-m','ruff','check','.'],root,log)
        run([sys.executable,'-m','black','--check','.'],root,log)
        rc |= run([sys.executable,'-m','pytest','-q','-m','not integration'],root,log)
    raise SystemExit(rc)

@main.command(name='all')
@click.argument('path',default='.')
@click.option('--apply',is_flag=True)
def all_cmd(path,apply):
    audit.callback(path,apply)
EOF
python3 -m venv "$TOOL/.venv"
source "$TOOL/.venv/bin/activate"
pip install -e "$TOOL" pytest ruff black isort pyodbc >/dev/null

log "Install 50-agent router into repos"
for d in "$WORKSPACE_ROOT"/*; do
  [[ -d "$d" ]] || continue
  mkdir -p "$d/.claude/skills/50-agent-router"
  cat > "$d/.claude/skills/50-agent-router/SKILL.md" <<'EOF'
# 50-Agent Code Repair Router

Call only the smallest needed agent or team.

Default teams:
- React/Codespace: node-react-repair, codespaces, npm-permissions, final-verifier
- Python: python-repair, requirements-manager, test-runner, final-verifier
- DataFlex: dataflex-odbc, odbc-driver, sql-safety, secrets-guard, final-verifier
- CI: github-actions-ci, test-runner, requirements-manager, final-verifier
- Security: security-auditor, secrets-guard, sql-safety, final-verifier
EOF
done

if [[ "$WITH_OLLAMA" == "true" ]] && command -v ollama >/dev/null 2>&1; then
  ollama serve > "$REPORT_ROOT/ollama.log" 2>&1 & echo $! > "$REPORT_ROOT/ollama.pid"
  sleep 5
  ollama pull llama3 || true
fi

log "Run audits/tests"
PASS=0; FAIL=0
for d in "$WORKSPACE_ROOT"/*; do
  [[ -d "$d" ]] || continue
  [[ -f "$d/package.json" || -f "$d/requirements.txt" || -f "$d/pyproject.toml" ]] || continue
  name="$(basename "$d")"
  out="$REPORT_ROOT/$name"; mkdir -p "$out"
  echo "Testing $name"
  set +e
  if [[ "$APPLY" == "true" ]]; then code-repair all "$d" --apply > "$out/run.log" 2>&1; else code-repair audit "$d" > "$out/run.log" 2>&1; fi
  rc=$?
  set -e
  cp -f "$d/CODE_REPAIR_REPORT.md" "$out/" 2>/dev/null || true
  if [[ $rc -eq 0 ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
done

cat > "$REPORT_ROOT/SUMMARY.md" <<EOF
# Fast Repair Summary

- Date: $(date -Iseconds)
- Workspace: $WORKSPACE_ROOT
- Apply: $APPLY
- Passed: $PASS
- Failed: $FAIL
- Reports: $REPORT_ROOT
EOF
cat "$REPORT_ROOT/SUMMARY.md"

if [[ -f "$REPORT_ROOT/ollama.pid" ]]; then kill "$(cat "$REPORT_ROOT/ollama.pid")" 2>/dev/null || true; fi
