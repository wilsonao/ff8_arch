-- Archipelago autotracking: connect PopTracker's AP autotracker to the room.
ScriptHost:LoadScript("scripts/mapping.lua")

CUR_INDEX = -1

function onClear(slot_data)
    CUR_INDEX = -1
    for _, code in ipairs(RESET_TOGGLES) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Active = false end
    end
    local p = Tracker:FindObjectForCode("progress")
    if p then p.AcquiredCount = 0 end
    for _, m in pairs(LOCATION_MAPPING) do
        local o = Tracker:FindObjectForCode(m.section)
        if o then o.AvailableChestCount = o.ChestCount end
    end
    AP_GF_THRESHOLD = nil
    if slot_data then
        local thr = slot_data["gfs_required_for_disc3"]
        if thr then AP_GF_THRESHOLD = tonumber(thr) end
        local function set_opt(code, key)
            local o = Tracker:FindObjectForCode(code)
            if o then
                o.Active = slot_data[key] == 1 or slot_data[key] == true
            end
        end
        set_opt("opt_draw_points", "draw_point_checks")
        set_opt("opt_tt", "triple_triad_checks")
        set_opt("opt_boss", "optional_boss_checks")
        set_opt("opt_cards", "rare_card_checks")
        set_opt("opt_sq", "sidequest_checks")
        set_opt("opt_mags", "magazine_checks")
        set_opt("opt_stats", "stat_checks")
        set_opt("opt_abil", "gf_ability_checks")
    end
end

function onItem(index, item_id, item_name, player_number)
    if index <= CUR_INDEX then return end
    CUR_INDEX = index
    local code = ITEM_MAPPING[item_id]
    if not code then return end
    local o = Tracker:FindObjectForCode(code)
    if o then o.Active = true end
end

function bumpProgress(n)
    local p = Tracker:FindObjectForCode("progress")
    if p and p.AcquiredCount < n then p.AcquiredCount = n end
end

function onLocation(location_id, location_name)
    local m = LOCATION_MAPPING[location_id]
    if not m then return end
    local o = Tracker:FindObjectForCode(m.section)
    if o and o.AvailableChestCount > 0 then
        o.AvailableChestCount = o.AvailableChestCount - 1
    end
    if m.progress then bumpProgress(m.progress) end
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
