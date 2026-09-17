#!/usr/bin/env bash
# Pin the Jetson CPU to a fixed frequency so Equation 2's fixed-f assumption
# holds during measurement. Run with sudo:
#
#   sudo bash prep_device.sh pin      # before a measurement session
#   sudo bash prep_device.sh status   # check what is currently set
#   sudo bash prep_device.sh restore  # afterwards
#
# The default target is 1497600 kHz, the available step closest to the paper's
# f = 1.5 GHz. MAXN_SUPER (nvpmodel 2) is selected first because the 25 W mode
# caps the CPU at 1344000 kHz.
set -euo pipefail

TARGET_KHZ="${TARGET_KHZ:-1497600}"
NVPMODEL_ID="${NVPMODEL_ID:-2}"
STATE=/var/lib/energy_model_validation.state
FAN=/sys/class/hwmon/hwmon0/pwm1

cpus() { ls -d /sys/devices/system/cpu/cpu[0-9]*/cpufreq 2>/dev/null; }

# "pmode:0001" -> 1. Plain zero-stripping turns "pmode:0000" into the empty
# string, which would silently restore the wrong power mode.
nvpmodel_id() {
  local raw
  raw=$(cat /var/lib/nvpmodel/status 2>/dev/null || echo "pmode:0001")
  raw=${raw#pmode:}
  printf '%d' "$((10#${raw:-1}))"
}

status() {
  echo "nvpmodel: $(cat /var/lib/nvpmodel/status 2>/dev/null || echo '?')"
  echo "fan pwm1: $(cat ${FAN} 2>/dev/null || echo 'n/a')"
  printf "%-6s %-10s %-9s %-9s %-9s\n" cpu governor cur_khz min_khz max_khz
  for d in $(cpus); do
    printf "%-6s %-10s %-9s %-9s %-9s\n" \
      "$(basename "$(dirname "$d")")" \
      "$(cat "$d/scaling_governor")" \
      "$(cat "$d/scaling_cur_freq")" \
      "$(cat "$d/scaling_min_freq")" \
      "$(cat "$d/scaling_max_freq")"
  done
}

case "${1:-status}" in
  pin)
    if [[ ! -f ${STATE} ]]; then
      {
        echo "NVPMODEL=$(nvpmodel_id)"
        echo "GOVERNOR=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
        echo "MIN_KHZ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq)"
        echo "MAX_KHZ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)"
        echo "FAN_PWM=$(cat ${FAN} 2>/dev/null || echo '')"
      } > ${STATE}
      echo "Saved original state to ${STATE}"
    fi

    echo "Setting nvpmodel ${NVPMODEL_ID} (MAXN_SUPER)"
    nvpmodel -m "${NVPMODEL_ID}" || true
    sleep 3

    cap=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
    if (( TARGET_KHZ > cap )); then
      echo "ERROR: target ${TARGET_KHZ} kHz exceeds cap ${cap} kHz" >&2
      exit 1
    fi

    for d in $(cpus); do
      echo userspace       > "$d/scaling_governor"
      cat "$d/cpuinfo_min_freq" > "$d/scaling_min_freq"
      echo "${TARGET_KHZ}" > "$d/scaling_max_freq"
      echo "${TARGET_KHZ}" > "$d/scaling_min_freq"
      echo "${TARGET_KHZ}" > "$d/scaling_setspeed"
    done

    # Full fan so thermal state does not drift across a multi-hour session.
    [[ -w ${FAN} ]] && echo 255 > ${FAN} || true

    sleep 1
    status
    ;;

  restore)
    if [[ ! -f ${STATE} ]]; then
      echo "No saved state at ${STATE}; restoring defaults." >&2
      NVPMODEL=1; GOVERNOR=schedutil; MIN_KHZ=""; MAX_KHZ=""; FAN_VAL=""
    else
      # shellcheck disable=SC1090
      source ${STATE}
      FAN_VAL="${FAN_PWM:-}"
    fi
    for d in $(cpus); do
      cat "$d/cpuinfo_min_freq" > "$d/scaling_min_freq"
      cat "$d/cpuinfo_max_freq" > "$d/scaling_max_freq"
      echo "${GOVERNOR:-schedutil}" > "$d/scaling_governor"
    done
    nvpmodel -m "${NVPMODEL:-1}" || true
    [[ -n "${FAN_VAL}" && -w ${FAN} ]] && echo "${FAN_VAL}" > ${FAN} || true
    rm -f ${STATE}
    sleep 1
    status
    ;;

  status) status ;;
  *) echo "usage: sudo bash prep_device.sh {pin|status|restore}" >&2; exit 2 ;;
esac
