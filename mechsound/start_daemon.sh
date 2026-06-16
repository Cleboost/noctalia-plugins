#!/bin/bash
# Démarre mechsound : pipe evtest directement dans le daemon Python.
# Aucun spawn par touche — latence minimale.
# Args: $1=sound_dir $2=volume $3=device $4=play_keyup (true/false)

PLUGIN_DIR="$(dirname "$(realpath "$0")")"

pkill -f 'mechsound/daemon.py' 2>/dev/null
pkill -f "evtest $3" 2>/dev/null
sleep 0.1

# stdbuf -oL force le line-buffering d'evtest dans le pipe (évite la latence de 4KB buffer).
stdbuf -oL evtest "$3" 2>/dev/null | python3 -u "$PLUGIN_DIR/daemon.py" "$1" "$2" "$4"
