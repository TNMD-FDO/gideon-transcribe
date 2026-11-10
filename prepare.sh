#!/usr/bin/env bash
#
# Gideon Transcribe: prepare a fresh Ubuntu server for the install.
#
#   bash prepare.sh                look, then ask before each change
#   bash prepare.sh --check-only   look only; nothing is changed
#   bash prepare.sh --tag v1.2.3   fetch that Release rather than the newest
#   bash prepare.sh --data DIR     the app data folder (on the data drive)
#   bash prepare.sh --home DIR     the install home (/opt/gideon-transcribe)
#
# What the install guide's Steps 0 to 2 do by hand (docs/install.md), in the
# same order and with the same commands: Docker with the Compose plugin from
# Docker's own repository; where Docker's images are kept; with an NVIDIA
# card, its driver and the container toolkit with CDI; the app's account and
# its two folders; a Release fetched into the install home. Then it starts
# ./transcribe install.
#
# It asks before every change and prints every command before it runs it. It
# never restarts Docker on a server that has images or running containers,
# never touches a driver that is already working, and on anything but Ubuntu
# Server 24.04 or newer it only looks.
#
# NOT YET PROVEN ON A CLEAN SERVER (v1.231.0). It is written from the guide
# and tested against stand-ins for the system's commands; its look-only mode
# has run on a real server. Until it has been run end to end on a fresh
# machine, the guide's Steps 0 to 2, by hand, remain the documented way.

set -uo pipefail

REPO_URL="${PREPARE_REPO_URL:-https://github.com/TNMD-FDO/gideon-transcribe.git}"
OS_RELEASE="${PREPARE_OS_RELEASE:-/etc/os-release}"
CONTAINERD_CONFIG="${PREPARE_CONTAINERD_CONFIG:-/etc/containerd/config.toml}"
APP_USER=transcribe
# The oldest driver the pinned stack runs under (docs/research/graphics-cards.md).
DRIVER_FLOOR=570

CHECK_ONLY=no
TAG=""
DATA_DIR=""
HOME_DIR="/opt/gideon-transcribe"
TO_DO=0
STOPPED=0
NEEDS_RESTART=no
ME="${USER:-$(id -un 2>/dev/null || echo you)}"

green() { printf '\033[32m%s\033[0m\n' "$1"; }
amber() { printf '\033[33m%s\033[0m\n' "$1"; }
red() { printf '\033[31m%s\033[0m\n' "$1"; }
pass() { green "  pass  $1"; }
note() { amber "  note  $1"; }
to_do() { red "  to do $1"; TO_DO=$((TO_DO + 1)); }

while [ $# -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=yes ;;
    --tag) TAG="${2:-}"; shift ;;
    --data) DATA_DIR="${2:-}"; shift ;;
    --home) HOME_DIR="${2:-}"; shift ;;
    -h | --help)
      awk 'NR >= 3 { if ($0 == "") exit; print }' "${BASH_SOURCE[0]:-$0}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      red "prepare.sh takes --check-only, --tag, --data and --home, and nothing else."
      exit 1
      ;;
  esac
  shift
done

ask_yes_no() {
  # yes or no by the first letter, Enter for what is in brackets.
  local question="$1" usual="$2" answer
  while true; do
    printf '%s (yes/no)\n  [%s]: ' "$question" "$usual" >&2
    read -r answer || answer=""
    answer="${answer%$'\r'}"
    answer="$(printf '%s' "${answer:-$usual}" | tr '[:upper:]' '[:lower:]')"
    case "$answer" in
      y | ye | yes) return 0 ;;
      n | no) return 1 ;;
    esac
    echo "  Please answer yes or no." >&2
  done
}

run() {
  # Every change goes through here: said first, then done. A command that
  # fails stops the step it is part of, and the step says so.
  printf '  running: %s\n' "$*"
  "$@"
}

gave_up() {
  red "  That did not work: $1"
  echo "  Nothing after it in this step was run. When it is put right, run"
  echo "  prepare.sh again: it carries on from what is already done."
  STOPPED=$((STOPPED + 1))
}

os_value() {
  [ -r "$OS_RELEASE" ] || return 0
  sed -n "s/^$1=//p" "$OS_RELEASE" | tr -d '"' | tail -1
}

docker_works() { docker --version >/dev/null 2>&1; }
compose_works() { docker compose version >/dev/null 2>&1; }
driver_works() { nvidia-smi -L >/dev/null 2>&1; }
account_exists() { id "$APP_USER" >/dev/null 2>&1; }

has_a_card() {
  driver_works && return 0
  lspci 2>/dev/null | grep -qi 'nvidia'
}

docker_is_in_use() {
  # Images or containers already on this server, ours or anybody's: then
  # Docker is never restarted and the image store is never moved here.
  local seen
  seen="$( (docker ps -aq; docker images -q) 2>/dev/null || true)"
  if [ -z "$seen" ]; then
    seen="$( (sudo -n docker ps -aq; sudo -n docker images -q) 2>/dev/null || true)"
  fi
  [ -n "$seen" ]
}

image_store_root() {
  [ -r "$CONTAINERD_CONFIG" ] || return 0
  grep -E '^\s*root\s*=' "$CONTAINERD_CONFIG" 2>/dev/null | sed 's/.*=\s*//' | tr -d "\"'" | sed -n '1p' || true
}

largest_other_drive() {
  # The roomiest real filesystem that is not the operating system's, as
  # "GB mountpoint"; nothing when the root filesystem is all there is.
  df -BG --output=avail,target -x tmpfs -x devtmpfs -x overlay -x squashfs -x efivarfs 2>/dev/null |
    awk 'NR > 1 { gsub("G", "", $1); if ($2 != "/" && $2 !~ /^\/(boot|snap|run|dev|sys|proc|var\/lib\/docker)/ && $1 + 0 > best) { best = $1 + 0; where = $2 } } END { if (where != "") print best " " where }'
}

propose_the_data_folder() {
  # Where recordings will live: the account's own home when the account is
  # already there; else a folder on the data volume, or on the roomiest
  # drive that is not the operating system's. Nothing when there is none.
  local home found
  if account_exists; then
    home="$(getent passwd "$APP_USER" 2>/dev/null | cut -d: -f6 || true)"
    case "$home" in "" | / | /nonexistent | /home/*) ;; *) printf '%s' "$home"; return 0 ;; esac
  fi
  if mountpoint -q /data 2>/dev/null; then
    printf '%s' "/data/transcribe"
    return 0
  fi
  found="$(largest_other_drive || true)"
  if [ -n "$found" ]; then printf '%s' "${found#* }/transcribe"; fi
}

# The steps ---------------------------------------------------------------------

step_system() {
  local id version pretty
  id="$(os_value ID)"
  version="$(os_value VERSION_ID)"
  pretty="$(os_value PRETTY_NAME)"
  if [ "$id" = "ubuntu" ] && [ "${version%%.*}" -ge 24 ] 2>/dev/null; then
    pass "Ubuntu $version"
    return 0
  fi
  note "this is ${pretty:-a system this script does not know}: the prepare step changes nothing here. It is written for Ubuntu Server 24.04 or newer; the guide's Steps 0 to 2 are the by-hand way, and on another system their commands are yours to translate."
  CHECK_ONLY=yes
}

step_docker() {
  if docker_works && compose_works; then
    pass "docker $(docker --version 2>/dev/null | sed 's/Docker version //; s/,.*//'), the compose plugin $(docker compose version --short 2>/dev/null)"
    return 0
  fi
  if docker_works; then
    note "Docker is here without its Compose plugin, or this account is not in the docker group yet: nothing is changed, since this Docker was installed another way (the guide's failure table has the fix)"
    return 0
  fi
  to_do "Docker with the Compose plugin, from Docker's own repository"
  [ "$CHECK_ONLY" = "no" ] || return 0
  ask_yes_no "Install Docker with the Compose plugin from Docker's own repository?" yes || return 0
  local codename arch
  codename="$(os_value UBUNTU_CODENAME)"
  [ -n "$codename" ] || codename="$(os_value VERSION_CODENAME)"
  arch="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
  run sudo apt-get update || { gave_up "apt could not refresh its lists"; return 0; }
  run sudo apt-get install -y ca-certificates curl || { gave_up "ca-certificates and curl could not be installed"; return 0; }
  run sudo install -m 0755 -d /etc/apt/keyrings || { gave_up "the keyrings folder could not be made"; return 0; }
  run sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc || { gave_up "Docker's key could not be fetched (is download.docker.com reachable?)"; return 0; }
  run sudo chmod a+r /etc/apt/keyrings/docker.asc || { gave_up "Docker's key could not be made readable"; return 0; }
  echo "  running: sudo tee /etc/apt/sources.list.d/docker.sources  (Docker's repository for $codename, $arch)"
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$codename" "$arch" |
    sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null || { gave_up "Docker's repository could not be written"; return 0; }
  run sudo apt-get update || { gave_up "apt could not read Docker's repository"; return 0; }
  run sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || { gave_up "Docker could not be installed"; return 0; }
  run sudo usermod -aG docker "$ME" || { gave_up "your account could not be added to the docker group"; return 0; }
  if docker_works; then
    pass "Docker is installed; $ME is in the docker group from the next sign-in"
  else
    gave_up "Docker was installed but does not answer"
  fi
}

step_image_store() {
  docker_works || return 0
  local root
  root="$(image_store_root)"
  if [ -n "$root" ] && [ "$root" != "/var/lib/containerd" ]; then
    pass "containerd's image store is at $root"
    return 0
  fi
  if docker_is_in_use; then
    note "containerd's image store is at its package default and Docker already holds images or containers: it is left alone, since it moves only by hand (the install guide's Step 0)"
    return 0
  fi
  to_do "containerd's image store on the Docker volume, set before the first image"
  [ "$CHECK_ONLY" = "no" ] || return 0
  echo "  A server shared with another project needs this, and it can only be"
  echo "  set now, while no image has been fetched; a server that is this app's"
  echo "  alone may leave it. It restarts Docker, which holds nothing yet."
  ask_yes_no "Keep Docker's images on the Docker volume (/var/lib/docker/containerd)?" yes || return 0
  run sudo mkdir -p /etc/containerd || { gave_up "/etc/containerd could not be made"; return 0; }
  echo "  running: containerd config default | sudo tee $CONTAINERD_CONFIG"
  containerd config default | sudo tee "$CONTAINERD_CONFIG" >/dev/null || { gave_up "containerd's default config could not be written"; return 0; }
  run sudo sed -i 's|^root = .*|root = "/var/lib/docker/containerd"|' "$CONTAINERD_CONFIG" || { gave_up "the image store's place could not be set"; return 0; }
  run sudo systemctl restart containerd docker || { gave_up "containerd and Docker did not restart"; return 0; }
  pass "containerd's image store is on the Docker volume"
}

step_card() {
  if ! has_a_card; then
    note "no NVIDIA card: the app installs without transcription, added later with one command (./transcribe add transcription)"
    return 0
  fi
  if driver_works; then
    local driver
    driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | sed -n '1p')"
    if [ "${driver%%.*}" -lt "$DRIVER_FLOOR" ] 2>/dev/null; then
      note "the nvidia driver is $driver; the transcription stack needs $DRIVER_FLOOR or newer. It is left alone: the guide's Step 0 shows how to pick a newer one"
    else
      pass "the nvidia driver $driver"
    fi
  else
    to_do "the NVIDIA driver, which needs a restart of the server afterwards"
    if [ "$CHECK_ONLY" = "no" ] && ask_yes_no "Install the NVIDIA driver? (The server must be restarted afterwards; no means install without transcription for now)" yes; then
      if run sudo ubuntu-drivers install --gpgpu; then
        NEEDS_RESTART=yes
        pass "the driver is installed; it works after a restart"
      else
        gave_up "the driver could not be installed"
      fi
    fi
    return 0
  fi

  # The container toolkit with CDI: only once the driver answers.
  if nvidia-ctk cdi list 2>/dev/null | grep -q '^nvidia.com/gpu='; then
    pass "the container toolkit's CDI list names the card"
    return 0
  fi
  to_do "the NVIDIA container toolkit with CDI, so Docker can hand the card to a container"
  [ "$CHECK_ONLY" = "no" ] || return 0
  ask_yes_no "Install the NVIDIA container toolkit and write the CDI list?" yes || return 0
  local release deb="cuda-keyring_1.1-1_all.deb"
  release="$(os_value VERSION_ID | tr -d '.')"
  run sudo curl -fsSL "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${release}/x86_64/${deb}" -o "/tmp/${deb}" || { gave_up "NVIDIA's keyring could not be fetched (is developer.download.nvidia.com reachable?)"; return 0; }
  run sudo dpkg -i "/tmp/${deb}" || { gave_up "NVIDIA's keyring could not be installed"; return 0; }
  run sudo apt-get update || { gave_up "apt could not read NVIDIA's repository"; return 0; }
  run sudo apt-get install -y nvidia-container-toolkit || { gave_up "the container toolkit could not be installed"; return 0; }
  run sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml || { gave_up "the CDI list could not be written"; return 0; }
  pass "the container toolkit is installed and the CDI list is written"
}

step_account_and_folders() {
  [ -n "$DATA_DIR" ] || DATA_DIR="$(propose_the_data_folder || true)"
  if account_exists && [ -n "$DATA_DIR" ] && [ -d "$HOME_DIR" ]; then
    pass "the $APP_USER account, its data folder $DATA_DIR and the install home $HOME_DIR"
    return 0
  fi
  if [ -z "$DATA_DIR" ]; then
    to_do "the $APP_USER account and its folders: no drive apart from the operating system's was found, so say where recordings should live with --data DIR (recordings fill a drive, and a full operating system drive stops the whole server)"
    return 0
  fi
  to_do "the $APP_USER account, the data folder $DATA_DIR and the install home $HOME_DIR"
  [ "$CHECK_ONLY" = "no" ] || return 0
  ask_yes_no "Make the $APP_USER account, the data folder $DATA_DIR and the install home $HOME_DIR? (no, then run again with --data or --home, to name other folders)" yes || return 0
  if ! account_exists; then
    run sudo useradd --system --no-create-home --home-dir "$DATA_DIR" --shell /usr/sbin/nologin --user-group "$APP_USER" || { gave_up "the account could not be made"; return 0; }
  fi
  run sudo install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DATA_DIR" || { gave_up "the data folder could not be made"; return 0; }
  run sudo install -d -o "$ME" -g "$ME" -m 0755 "$HOME_DIR" || { gave_up "the install home could not be made"; return 0; }
  pass "the $APP_USER account, $DATA_DIR and $HOME_DIR"
}

newest_release() {
  # Read to the end and sorted here: nothing in this pipeline quits early.
  git ls-remote --tags --refs "$REPO_URL" 'v*' 2>/dev/null | sed 's|.*refs/tags/||' | sort -V | tail -1
}

step_release() {
  if [ -e "$HOME_DIR/transcribe" ]; then
    pass "a Release is in $HOME_DIR ($(git -C "$HOME_DIR" describe --tags --exact-match 2>/dev/null || echo "not at a tag"))"
    return 0
  fi
  if ! git --version >/dev/null 2>&1; then
    to_do "git, to fetch a Release"
    [ "$CHECK_ONLY" = "no" ] || return 0
    run sudo apt-get install -y git || { gave_up "git could not be installed"; return 0; }
  fi
  local tag="$TAG"
  [ -n "$tag" ] || tag="$(newest_release || true)"
  if [ -z "$tag" ]; then
    to_do "a Release in $HOME_DIR: the newest could not be read from $REPO_URL (no access to the repository yet, or github.com does not answer); name one with --tag"
    return 0
  fi
  to_do "the Release $tag fetched into $HOME_DIR"
  [ "$CHECK_ONLY" = "no" ] || return 0
  if [ ! -d "$HOME_DIR" ]; then
    note "the install home $HOME_DIR is not there yet, so the Release is not fetched"
    return 0
  fi
  ask_yes_no "Fetch the Release $tag into $HOME_DIR?" yes || return 0
  run git clone --branch "$tag" "$REPO_URL" "$HOME_DIR" || { gave_up "the Release could not be fetched"; return 0; }
  pass "$tag is in $HOME_DIR"
}

# The run ------------------------------------------------------------------------

echo "Gideon Transcribe: preparing this server"
if [ "$CHECK_ONLY" = "yes" ]; then
  echo "Looking only: nothing is changed."
else
  echo "Nothing is changed until you say yes, and every command is shown before"
  echo "it runs. To look only: bash prepare.sh --check-only"
  amber "This step is new and has not yet been run on a clean server (v1.231.0)."
  amber "The install guide's Steps 0 to 2, by hand, remain the documented way."
fi
echo

step_system
if [ "$CHECK_ONLY" = "no" ]; then
  if [ "$(id -u)" = "0" ]; then
    red "Run this as the account that will look after the app, not as root: it uses sudo where it needs it, and that account is the one put in the docker group."
    exit 1
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    red "There is no sudo on this server, and this step needs it."
    exit 1
  fi
fi
step_docker
step_image_store
step_card
step_account_and_folders
step_release

echo
if [ "$CHECK_ONLY" = "yes" ]; then
  if [ "$TO_DO" -eq 0 ]; then
    echo "Nothing to do: this server is prepared."
  else
    echo "$TO_DO to do. Run it without --check-only to be asked about each, or"
    echo "follow the install guide's Steps 0 to 2 by hand."
  fi
  exit 0
fi
if [ "$STOPPED" -gt 0 ]; then
  red "$STOPPED step(s) stopped part way; the lines above say where and why."
  exit 1
fi
if [ "$NEEDS_RESTART" = "yes" ]; then
  echo "The driver needs a restart before it works:"
  echo
  echo "  sudo reboot"
  echo
  echo "Then run prepare.sh again. It carries on from here: the container"
  echo "toolkit, and the install."
  exit 0
fi
if [ ! -e "$HOME_DIR/transcribe" ]; then
  echo "The install is not started: there is no Release in $HOME_DIR yet."
  echo "Run prepare.sh again when what is left above is settled."
  exit 0
fi

echo "This server is prepared. Starting the install: ./transcribe install"
echo
cd "$HOME_DIR" || exit 1
if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
  exec ./transcribe install
fi
# The docker group was added in this run and does not reach this shell until
# the next sign-in; sg runs the install under it now.
echo "  (Your account joined the docker group in this run. Sign out and in"
echo "  again afterwards, so that ./transcribe works from a new shell.)"
exec sg docker -c "cd '$HOME_DIR' && ./transcribe install"
