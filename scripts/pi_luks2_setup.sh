#!/usr/bin/env bash
# Pi data-partition encryption (LUKS2) for O Iris. Idempotent; --dry-run prints every command
# and changes nothing. Encrypts a DATA partition/USB disk that holds ~/.oiris, not the root fs.
#
#   sudo scripts/pi_luks2_setup.sh --device /dev/sda1 [--name oiris_data] [--mount /var/lib/oiris] [--dry-run] [--yes]
#
# Steps (each skipped if already done): luksFormat (argon2id, aes-xts-plain64, 512-bit key)
# -> open -> mkfs.ext4 -> crypttab/fstab entries (noauto: unlocked by the operator at boot,
# passphrase never stored on disk) -> mount -> chmod 700. FORMATTING ERASES THE DEVICE:
# without --yes the script asks you to type the device path back.
set -euo pipefail
DEV=""; NAME="oiris_data"; MNT="/var/lib/oiris"; DRY=0; YES=0
CRYPTTAB="${OIRIS_CRYPTTAB:-/etc/crypttab}"; FSTAB="${OIRIS_FSTAB:-/etc/fstab}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --device) DEV="$2"; shift 2;; --name) NAME="$2"; shift 2;; --mount) MNT="$2"; shift 2;;
    --dry-run) DRY=1; shift;; --yes) YES=1; shift;;
    -h|--help) sed -n 2,11p "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
[[ -n "$DEV" ]] || { echo "--device is required" >&2; exit 2; }
[[ "$NAME" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "bad --name" >&2; exit 2; }
run() { if [[ $DRY == 1 ]]; then echo "DRY-RUN: $*"; else echo "+ $*"; "$@"; fi; }
need() { command -v "$1" >/dev/null || { echo "missing tool: $1 (apt install $2)" >&2; exit 3; }; }
need cryptsetup cryptsetup; need blkid util-linux; need mkfs.ext4 e2fsprogs
if [[ $DRY == 0 && $EUID -ne 0 ]]; then echo "run as root (or use --dry-run)" >&2; exit 4; fi
[[ -b "$DEV" || $DRY == 1 ]] || { echo "not a block device: $DEV" >&2; exit 2; }
if mount | grep -q "^$DEV "; then echo "refusing: $DEV is mounted" >&2; exit 5; fi

if cryptsetup isLuks "$DEV" 2>/dev/null; then
  echo "ok: $DEV is already LUKS ($(cryptsetup luksDump "$DEV" 2>/dev/null | awk '/^Version:/{print "v"$2}'))"
else
  if [[ -n "$(blkid -o value -s TYPE "$DEV" 2>/dev/null || true)" && $YES == 0 && $DRY == 0 ]]; then
    echo "WARNING: $DEV has a filesystem; formatting ERASES it."
  fi
  if [[ $YES == 0 && $DRY == 0 ]]; then
    read -r -p "Type the device path ($DEV) to erase and encrypt it: " ans
    [[ "$ans" == "$DEV" ]] || { echo "aborted"; exit 6; }
  fi
  run cryptsetup luksFormat --type luks2 --pbkdf argon2id --cipher aes-xts-plain64 --key-size 512 --batch-mode "$DEV"
fi
if [[ -e "/dev/mapper/$NAME" ]]; then echo "ok: /dev/mapper/$NAME already open"; else run cryptsetup open "$DEV" "$NAME"; fi
if [[ $DRY == 1 ]] || [[ -z "$(blkid -o value -s TYPE "/dev/mapper/$NAME" 2>/dev/null || true)" ]]; then
  if [[ $DRY == 1 ]]; then echo "DRY-RUN: mkfs.ext4 -L oiris /dev/mapper/$NAME (only if it has no filesystem)"
  else run mkfs.ext4 -L oiris "/dev/mapper/$NAME"; fi
else echo "ok: /dev/mapper/$NAME already has a filesystem"; fi
UUID=$( [[ $DRY == 1 ]] && echo "<luks-uuid>" || cryptsetup luksUUID "$DEV")
CT="$NAME UUID=$UUID none luks,noauto"
FS="/dev/mapper/$NAME $MNT ext4 noauto,nofail,nodev,nosuid,noexec 0 2"
add_line() { # file line
  if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then echo "ok: $1 already has entry"
  elif [[ $DRY == 1 ]]; then echo "DRY-RUN: append to $1: $2"
  else echo "$2" >> "$1"; echo "+ appended to $1"; fi
}
add_line "$CRYPTTAB" "$CT"; add_line "$FSTAB" "$FS"
run mkdir -p "$MNT"
if mountpoint -q "$MNT" 2>/dev/null; then echo "ok: $MNT mounted"; else run mount "/dev/mapper/$NAME" "$MNT"; fi
run chmod 700 "$MNT"
echo "done. Point O Iris at it: set data_dir to $MNT in config.json. Unlock after boot: cryptsetup open $DEV $NAME && mount $MNT"
