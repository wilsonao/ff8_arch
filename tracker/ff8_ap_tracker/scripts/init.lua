Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

-- mapping.lua carries the beat names and gate ladder logic.lua reads, so it
-- loads first, AP or not (a manual tracker still needs the access rules).
ScriptHost:LoadScript("scripts/mapping.lua")
ScriptHost:LoadScript("scripts/logic.lua")

if _G.Archipelago then
    ScriptHost:LoadScript("scripts/autotracking.lua")
end
