-- Mechanical Sounds — joue des sons de switches mécaniques à chaque frappe.
--
-- Architecture : start_daemon.sh pipe evtest → daemon.py directement.
-- Pas de spawn par touche, pas de FIFO. Latence minimale.

noctalia.setUpdateInterval(2000)

local PLUGIN_DIR = "/home/cleboost/Projects/noctalia/custom-plugins/mechsound"

local lastSoundpack  = ""
local lastVolume     = 0
local lastPlayKeyup  = nil
local lastDevice     = ""
local daemonRunning  = false
local isMuted        = false

-- ── Config ────────────────────────────────────────────────────────────────────

local function getConfig()
  return {
    pack       = noctalia.getConfig("soundpack")          or "mxbrown",
    volume     = tonumber(noctalia.getConfig("volume"))   or 85,
    playKeyup  = noctalia.getConfig("play_keyup_sounds")  ~= false,
    device     = noctalia.getConfig("input_device")       or "",
  }
end

-- ── Daemon ────────────────────────────────────────────────────────────────────

local function startDaemon(cfg)
  if not cfg.device or cfg.device == "" then return end
  if not cfg.device:match("^/dev/input/event%d+$") then
    noctalia.notifyError("Mechsound", `Périphérique invalide: {cfg.device}`)
    return
  end
  if not noctalia.commandExists("evtest") then
    noctalia.notifyError("Mechsound", "evtest manquant — pacman -S evtest")
    return
  end

  local soundDir   = `{PLUGIN_DIR}/sounds_extracted/{cfg.pack}`
  local vol        = cfg.volume / 100.0
  local playKeyup  = tostring(cfg.playKeyup)

  -- start_daemon.sh : pkill ancien → evtest | python3 daemon.py
  noctalia.runStream(
    `bash '{PLUGIN_DIR}/start_daemon.sh' '{soundDir}' {vol} '{cfg.device}' {playKeyup}`,
    function(_line) end
  )

  lastSoundpack = cfg.pack
  lastVolume    = cfg.volume
  lastPlayKeyup = cfg.playKeyup
  lastDevice    = cfg.device
  daemonRunning = true
end

local cfg = getConfig()
startDaemon(cfg)

-- ── State watches ─────────────────────────────────────────────────────────────

noctalia.state.watch("mechsound_muted", function(val)
  isMuted = (val == true)
end)

-- ── Update : redémarre le daemon si config change ────────────────────────────

function update()
  local cfg = getConfig()
  if cfg.pack    ~= lastSoundpack
  or cfg.volume  ~= lastVolume
  or cfg.playKeyup ~= lastPlayKeyup
  or cfg.device  ~= lastDevice then
    startDaemon(cfg)
  end
end
