# shellcheck shell=bash
# Source from deploy scripts: source "$(dirname "$0")/lib-app-user.sh"

resolve_anamnes_app_user() {
  local root="${1:-/opt/anamnes}"

  if [[ -n "${ANAMNES_USER:-}" ]]; then
    if id "${ANAMNES_USER}" &>/dev/null; then
      echo "${ANAMNES_USER}"
      return 0
    fi
    echo "ERROR: ANAMNES_USER=${ANAMNES_USER} does not exist on this host." >&2
    return 1
  fi

  local owner=""
  if [[ -d "${root}" ]]; then
    owner=$(stat -c '%U' "${root}" 2>/dev/null || true)
    if [[ -n "${owner}" && "${owner}" != "root" ]] && id "${owner}" &>/dev/null; then
      echo "${owner}"
      return 0
    fi
  fi

  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]] && id "${SUDO_USER}" &>/dev/null; then
    echo "${SUDO_USER}"
    return 0
  fi

  echo "ERROR: Cannot detect app user. Set ANAMNES_USER (e.g. export ANAMNES_USER=ikorsa)." >&2
  return 1
}

resolve_anamnes_app_group() {
  local user="$1"
  local root="${2:-/opt/anamnes}"
  if [[ -n "${ANAMNES_GROUP:-}" ]] && getent group "${ANAMNES_GROUP}" &>/dev/null; then
    echo "${ANAMNES_GROUP}"
    return 0
  fi
  local group
  group=$(id -gn "${user}" 2>/dev/null || true)
  if [[ -n "${group}" ]]; then
    echo "${group}"
    return 0
  fi
  stat -c '%G' "${root}" 2>/dev/null || echo "${user}"
}
