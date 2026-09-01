Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

ScriptHost:LoadScript("scripts/logic.lua")

if _G.Archipelago then
    ScriptHost:LoadScript("scripts/autotracking.lua")
end
