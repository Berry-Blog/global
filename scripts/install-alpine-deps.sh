#!/bin/sh
# Bounded, signature-verified Alpine dependency installer for Global Home.
set -eu

LOG_DIR=/var/log/global-home-nodes
LOG_FILE="$LOG_DIR/apk-dependencies.log"
WORK_DIR="/tmp/global-home-apk-deps.$$"
SUCCESS=0

mkdir -p "$LOG_DIR" "$WORK_DIR"
: > "$LOG_FILE"

cleanup() {
    if [ "$SUCCESS" -eq 1 ]; then
        rm -rf "$WORK_DIR"
    else
        echo "[Global Home] Temporary package cache retained: $WORK_DIR" >&2
        echo "[Global Home] Diagnostic log: $LOG_FILE" >&2
    fi
}
trap cleanup EXIT HUP INT TERM

fail() {
    echo "[Global Home][ERROR] $*" | tee -a "$LOG_FILE" >&2
    echo "----- Last dependency log lines -----" >&2
    tail -n 80 "$LOG_FILE" >&2 || true
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "Run this installer as root."
command -v apk >/dev/null 2>&1 || fail "apk is not installed."
command -v curl >/dev/null 2>&1 || fail "curl is required for the bounded package downloader."
command -v timeout >/dev/null 2>&1 || fail "BusyBox timeout is required; refusing an unbounded package operation."

if pidof apk >/dev/null 2>&1; then
    fail "Another apk process is active. Wait for it to finish before continuing."
fi

if ! ls /var/cache/apk/APKINDEX.*.tar.gz >/dev/null 2>&1; then
    echo "[Global Home] No cached APK indexes; refreshing indexes with a 60-second limit." | tee -a "$LOG_FILE"
    timeout 60 apk update >> "$LOG_FILE" 2>&1 || fail "apk update failed or timed out."
fi

ARCH="$(apk --print-arch 2>/dev/null)" || fail "Unable to detect Alpine architecture."
[ -n "$ARCH" ] || fail "Alpine architecture is empty."

fetch_package() {
    package_id="$1"
    target="$WORK_DIR/$package_id.apk"
    part="$target.part"

    if [ -s "$target" ]; then
        apk verify "$target" >> "$LOG_FILE" 2>&1 || fail "Cached APK signature verification failed: $package_id"
        return 0
    fi

    echo "[Global Home] Fetching $package_id from configured Alpine repositories." | tee -a "$LOG_FILE"
    rm -f "$part"

    found=0
    while IFS= read -r repository || [ -n "$repository" ]; do
        repository="$(printf '%s' "$repository" | sed 's/[[:space:]]*#.*$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$repository" ] || continue
        case "$repository" in
            http://*|https://*) ;;
            *) continue ;;
        esac

        url="${repository%/}/$ARCH/$package_id.apk"
        if timeout 75 curl -4 -fL --connect-timeout 10 --max-time 60 --retry 1 \
            -o "$part" "$url" >> "$LOG_FILE" 2>&1; then
            if apk verify "$part" >> "$LOG_FILE" 2>&1; then
                actual_name="$(tar -xOzf "$part" .PKGINFO 2>/dev/null | sed -n 's/^pkgname = //p' | head -n 1)"
                actual_version="$(tar -xOzf "$part" .PKGINFO 2>/dev/null | sed -n 's/^pkgver = //p' | head -n 1)"
                if [ "$actual_name-$actual_version" = "$package_id" ]; then
                    mv -f "$part" "$target"
                    found=1
                    break
                fi
                echo "[Global Home] Package identity mismatch for $package_id from $repository." >> "$LOG_FILE"
            fi
        fi
        rm -f "$part"
    done < /etc/apk/repositories

    [ "$found" -eq 1 ] || fail "Unable to download and verify $package_id from configured repositories."
}

package_id_for_name() {
    package_name="$1"
    package_id="$(apk search -x "$package_name" 2>/dev/null | sed -n '1p' | tr -d '\r')"
    case "$package_id" in
        "$package_name"-*) printf '%s' "$package_id" ;;
        *) return 1 ;;
    esac
}

echo "[Global Home] Preparing required packages for Alpine $ARCH." | tee -a "$LOG_FILE"

for package_name in python3 curl expect strace coreutils ca-certificates; do
    if apk info -e "$package_name" >/dev/null 2>&1; then
        echo "[Global Home] Already installed: $package_name" | tee -a "$LOG_FILE"
        continue
    fi
    package_id="$(package_id_for_name "$package_name")" || fail "Package not found in the cached APK indexes: $package_name"
    fetch_package "$package_id"
done

ready=0
round=1
while [ "$round" -le 15 ]; do
    echo "[Global Home] Offline dependency resolution round $round/15." | tee -a "$LOG_FILE"
    set +e
    timeout 45 apk add --simulate --no-network "$WORK_DIR"/*.apk > "$WORK_DIR/simulate.log" 2>&1
    simulate_rc=$?
    set -e

    if [ "$simulate_rc" -eq 0 ]; then
        ready=1
        break
    fi

    cat "$WORK_DIR/simulate.log" >> "$LOG_FILE"
    missing="$(awk '
        /^  [A-Za-z0-9_.+-]+-[0-9][A-Za-z0-9_.+-]*:$/ {
            item=$0
            sub(/^  /, "", item)
            sub(/:$/, "", item)
            print item
        }
    ' "$WORK_DIR/simulate.log" | sort -u)"

    [ -n "$missing" ] || fail "Offline dependency resolution failed without a downloadable package list."

    while IFS= read -r package_id; do
        [ -n "$package_id" ] || continue
        fetch_package "$package_id"
    done <<EOF
$missing
EOF

    round=$((round + 1))
done

[ "$ready" -eq 1 ] || fail "Dependency resolution did not converge after 15 rounds."

echo "[Global Home] All dependencies are locally available and signature-verified." | tee -a "$LOG_FILE"
echo "[Global Home] Installing the verified local APK set (network disabled)." | tee -a "$LOG_FILE"
timeout 180 apk add --no-network "$WORK_DIR"/*.apk >> "$LOG_FILE" 2>&1 || fail "Local APK installation failed or timed out."

for command_name in python3 curl expect strace sha256sum; do
    command -v "$command_name" >/dev/null 2>&1 || fail "Required command is still missing after installation: $command_name"
done

python3 --version >> "$LOG_FILE" 2>&1
echo "[Global Home] Alpine dependencies installed successfully." | tee -a "$LOG_FILE"
SUCCESS=1
