-- Mechsound widget — minimal mute/unmute toggle icon in the bar.
-- The actual sound logic runs in the [[service]] (mechsound.luau).
-- This widget only exists to make Noctalia load the plugin.

noctalia.setUpdateInterval(1000)

local muted = false

local function refreshIcon()
  if muted then
    barWidget.setText("󰖁")   -- nf-md-volume_off
  else
    barWidget.setText("󰕾")   -- nf-md-volume_high
  end
end

refreshIcon()

-- Sync mute state from service via shared state
noctalia.state.watch("mechsound_muted", function(val)
  muted = (val == true)
  refreshIcon()
end)

-- Click toggles mute
function onClick()
  muted = not muted
  noctalia.state.set("mechsound_muted", muted)
  refreshIcon()
end

function update()
  -- nothing to poll, state.watch handles updates
end
