#!/usr/bin/env python3
"""
Copies Tr4 + Tr1_2 WAV files from session folders into Google Drive
under a 'AudioTraining/' folder so the Windows machine can download them.
"""
import os
import shutil
from pathlib import Path

# All sessions with the same director — more Tr4 data = better speaker model
SESSIONS = {
    # March 2026
    "RiverLynn-DannySteele":         "/Volumes/StorageWhore/VRH-March-2026/RiverLynn-DannySteele",
    "DellaCate-DannySteele-March":   "/Volumes/StorageWhore/VRH-March-2026/DellaCate-DannySteele",
    # Feb 2026 — same director, more voice data
    "DellaCate-DannySteele-Feb":     "/Volumes/StorageWhore/Archive/FebruaryVRH2026Render/DellaCate-DannySteele",
    "CassieDelisla-DannySteele-Feb": "/Volumes/StorageWhore/Archive/FebruaryFPVR2026Render/CassieDelisla-DannySteele",
}

# Use Dropbox (syncs automatically, no manual intervention needed)
cloud = Path.home() / "Library" / "CloudStorage"
dropbox_root = cloud / "Dropbox"

if not dropbox_root.exists():
    print("Dropbox not found at", dropbox_root)
    exit(1)

dest_root = dropbox_root / "AudioTraining"
dest_root.mkdir(exist_ok=True)
print(f"Destination: {dest_root}\n")

total_copied = 0
total_bytes  = 0

for session_name, src_root in SESSIONS.items():
    src_path = Path(src_root)
    print(f"── {session_name}")
    for take_dir in sorted(src_path.rglob("*.TAKE")):
        if not take_dir.is_dir():
            continue
        dest_take = dest_root / session_name / take_dir.name
        dest_take.mkdir(parents=True, exist_ok=True)
        for pattern in ("*_Tr1_2.WAV", "*_Tr4.WAV"):
            for f in sorted(take_dir.glob(pattern)):
                dest_file = dest_take / f.name
                sz = f.stat().st_size
                szm = sz // 1048576
                # Skip if already there and same size
                if dest_file.exists() and dest_file.stat().st_size == sz:
                    print(f"  skip  {take_dir.name}/{f.name}  ({szm}MB)")
                    continue
                print(f"  copy  {take_dir.name}/{f.name}  ({szm}MB) ...", end="", flush=True)
                shutil.copy2(f, dest_file)
                print(" done")
                total_copied += 1
                total_bytes  += sz

print(f"\n{'='*50}")
print(f"Copied {total_copied} files  ({total_bytes // 1048576} MB)")
print(f"Dropbox is syncing automatically.")
print(f"\nOn Windows: C:\\Users\\andre\\Dropbox\\AudioTraining")
