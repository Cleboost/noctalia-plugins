local label = barWidget.getConfig("label")
local clicks = 0

local function render()
  barWidget.setGlyph("flask")
  barWidget.setText(label)
  barWidget.setTooltip(`Plugin de test — {clicks} clic(s)`)
end

function update()
  noctalia.setUpdateInterval(5000)
  render()
end

function onClick()
  clicks += 1
  noctalia.notify("Test Plugin", `Cliqué {clicks} fois !`)
  render()
end
