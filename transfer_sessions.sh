#!/bin/bash
# Fast parallel transfer — 4 simultaneous SCP streams, skip-check done in one SSH call

WINDOWS="andre@100.90.90.68"
PASS="qwerasdf53"
DEST="audio_sessions"
PARALLEL=6   # simultaneous transfers

SSH_BASE="sshpass -p ${PASS} ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR ${WINDOWS}"
SCP_BASE="sshpass -p ${PASS} scp -C -o StrictHostKeyChecking=no -o LogLevel=ERROR"

declare -A SESSIONS=(
  ["RiverLynn-DannySteele"]="/Volumes/StorageWhore/VRH-March-2026/RiverLynn-DannySteele"
  ["DellaCate-DannySteele-March"]="/Volumes/StorageWhore/VRH-March-2026/DellaCate-DannySteele"
)

# ── Build full file list ───────────────────────────────────────────────────────
declare -a SRC_FILES=()
declare -a DST_PATHS=()
declare -a FILE_SIZES=()
total_bytes=0

for SESSION_NAME in "${!SESSIONS[@]}"; do
  SRC_ROOT="${SESSIONS[$SESSION_NAME]}"
  while IFS= read -r -d '' take_dir; do
    take_name="$(basename "$take_dir")"
    remote_path="${DEST}/${SESSION_NAME}/${take_name}"
    while IFS= read -r -d '' f; do
      sz=$(stat -f%z "$f" 2>/dev/null || echo 0)
      SRC_FILES+=("$f")
      DST_PATHS+=("$remote_path")
      FILE_SIZES+=("$sz")
      total_bytes=$((total_bytes + sz))
    done < <(find "$take_dir" -maxdepth 1 \
      \( -name "*_Tr1_2.WAV" -o -name "*_Tr4.WAV" \) -print0 2>/dev/null)
  done < <(find "$SRC_ROOT" -name "*.TAKE" -type d -print0 2>/dev/null)
done

total_files=${#SRC_FILES[@]}
total_mb=$(( total_bytes / 1048576 ))

printf "┌──────────────────────────────────────────────────────────────┐\n"
printf "│  Transfer → Windows  │  %d files  /  %d MB\n" "$total_files" "$total_mb"
printf "└──────────────────────────────────────────────────────────────┘\n\n"

# ── Create all remote directories in one SSH call ─────────────────────────────
echo "Creating remote directories..."
MKDIRS=""
for SESSION_NAME in "${!SESSIONS[@]}"; do
  SRC_ROOT="${SESSIONS[$SESSION_NAME]}"
  while IFS= read -r -d '' take_dir; do
    take_name="$(basename "$take_dir")"
    remote_path="${DEST}/${SESSION_NAME}/${take_name}"
    MKDIRS+="New-Item -ItemType Directory -Force -Path '${remote_path}' | Out-Null; "
  done < <(find "$SRC_ROOT" -name "*.TAKE" -type d -print0 2>/dev/null)
done
$SSH_BASE "powershell -command \"${MKDIRS}\"" 2>/dev/null
echo "Done."
echo ""

# ── Get already-transferred files in one SSH call ────────────────────────────
echo "Checking existing files on Windows..."
REMOTE_FILES=$($SSH_BASE \
  "powershell -command \"Get-ChildItem -Recurse ${DEST} | Where-Object { -not \$_.PSIsContainer } | ForEach-Object { \$_.Name + ':' + \$_.Length }\"" 2>/dev/null)

declare -A REMOTE_SIZES
while IFS=: read -r name size; do
  name="$(echo "$name" | tr -d '\r')"
  size="$(echo "$size" | tr -d '\r ')"
  REMOTE_SIZES["$name"]="$size"
done <<< "$REMOTE_FILES"
echo "Found ${#REMOTE_SIZES[@]} existing files."
echo ""

# ── Parallel transfer ─────────────────────────────────────────────────────────
done_bytes=0
ok=0; skip=0; fail=0
declare -a PIDS=()
declare -a PID_IDX=()

cleanup_pids() {
  # Wait for a slot to free up
  while [ ${#PIDS[@]} -ge $PARALLEL ]; do
    wait "${PIDS[0]}" 2>/dev/null
    PIDS=("${PIDS[@]:1}")
    PID_IDX=("${PID_IDX[@]:1}")
  done
}

for idx in "${!SRC_FILES[@]}"; do
  f="${SRC_FILES[$idx]}"
  remote_path="${DST_PATHS[$idx]}"
  sz="${FILE_SIZES[$idx]}"
  fname="$(basename "$f")"
  fmb=$(( sz / 1048576 ))
  pct=$(( done_bytes * 100 / (total_bytes + 1) ))

  remote_sz="${REMOTE_SIZES[$fname]}"
  if [ "$remote_sz" = "$sz" ] && [ "$sz" -gt 0 ]; then
    printf "  [%3d%%] %d/%d  %-38s %4dMB  skip\n" \
      "$pct" "$((idx+1))" "$total_files" "$fname" "$fmb"
    skip=$((skip + 1))
    done_bytes=$((done_bytes + sz))
    continue
  fi

  printf "  [%3d%%] %d/%d  %-38s %4dMB  →\n" \
    "$pct" "$((idx+1))" "$total_files" "$fname" "$fmb"

  # Launch SCP in background
  cleanup_pids
  (
    $SCP_BASE "$f" "${WINDOWS}:${remote_path}/" 2>/dev/null
    if [ $? -eq 0 ]; then
      echo "  ✓  $fname"
    else
      echo "  ✗  $fname  FAILED"
    fi
  ) &
  PIDS+=($!)
  PID_IDX+=($idx)
  done_bytes=$((done_bytes + sz))
done

# Wait for all remaining transfers
wait

echo ""
done_mb=$(( done_bytes / 1048576 ))
printf "══════════════════════════════════════════════════════════════\n"
printf "  ✓ transferred: %d   skip: %d   ✗ failed: %d   total: %d MB\n" \
  "$ok" "$skip" "$fail" "$done_mb"
printf "══════════════════════════════════════════════════════════════\n"
