-- Archipelago autotracking: connect PopTracker's AP autotracker to the room.
-- (scripts/mapping.lua is already loaded by init.lua.)

CUR_INDEX = -1
AREA_KEY = nil   -- data-storage key the FF8 client publishes the area under
HINTS_KEY = nil  -- server-managed data-storage key with the slot's hints
HIGHLIGHTED = {} -- section codes currently carrying a hint highlight

function updateAreaTab(area)
    local opt = Tracker:FindObjectForCode("opt_autotab")
    if opt and not opt.Active then return end
    local tab = AREA_TABS[area]
    if not tab then return end
    Tracker:UiHint("ActivateTab", "World Map")
    Tracker:UiHint("ActivateTab", tab)
end

-- AP hint status -> PopTracker section highlight (Highlight is nil on
-- PopTracker builds without section-highlight support; everything guards on it).
local function hintHighlight(hint)
    if hint.found then return Highlight.NONE end
    local by_status = {
        [1] = Highlight.UNSPECIFIED,   -- HINT_UNSPECIFIED
        [10] = Highlight.NO_PRIORITY,  -- HINT_NO_PRIORITY
        [20] = Highlight.AVOID,        -- HINT_AVOID
        [30] = Highlight.PRIORITY,     -- HINT_PRIORITY
    }
    return by_status[hint.status] or Highlight.UNSPECIFIED
end

function updateHints(hints)
    if not Highlight or type(hints) ~= "table" then return end
    for code in pairs(HIGHLIGHTED) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Highlight = Highlight.NONE end
    end
    HIGHLIGHTED = {}
    for _, hint in ipairs(hints) do
        -- Only hints whose location is in this world can be pinned on our maps.
        local m = hint.finding_player == Archipelago.PlayerNumber
                  and LOCATION_MAPPING[hint.location]
        if m then
            local o = Tracker:FindObjectForCode(m.section)
            if o then
                local hl = hintHighlight(hint)
                o.Highlight = hl
                if hl ~= Highlight.NONE then HIGHLIGHTED[m.section] = true end
            end
        end
    end
end

function onClear(slot_data)
    CUR_INDEX = -1
    -- 580 locations reset at once: batch so logic/UI recalculate only once.
    Tracker.BulkUpdate = true
    for _, code in ipairs(RESET_TOGGLES) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Active = false end
    end
    local p = Tracker:FindObjectForCode("progress")
    if p then p.AcquiredCount = 0 end
    for _, code in ipairs({"char_unlocks", "junction_unlocks", "command_unlocks"}) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.AcquiredCount = 0 end
    end
    for _, m in pairs(LOCATION_MAPPING) do
        local o = Tracker:FindObjectForCode(m.section)
        if o then o.AvailableChestCount = o.ChestCount end
    end
    if Highlight then
        for code in pairs(HIGHLIGHTED) do
            local o = Tracker:FindObjectForCode(code)
            if o then o.Highlight = Highlight.NONE end
        end
    end
    HIGHLIGHTED = {}
    Tracker.BulkUpdate = false
    if slot_data then
        local thr = slot_data["gfs_required_for_disc3"]
        if thr then AP_OPTS.gfs_required_for_disc3 = tonumber(thr) end
        local mode = slot_data["story_gates"]
        if mode ~= nil then
            AP_OPTS.story_gates = STORY_GATE_MODES[tonumber(mode)] or tostring(mode)
        end
        for _, key in ipairs({"character_locks", "junction_locks", "command_locks",
                              "vehicle_unlocks", "vehicle_gates"}) do
            if slot_data[key] ~= nil then
                AP_OPTS[key] = slot_data[key] == 1 or slot_data[key] == true
            end
        end
        local function set_opt(code, key)
            local o = Tracker:FindObjectForCode(code)
            if o and slot_data[key] ~= nil then
                o.Active = slot_data[key] == 1 or slot_data[key] == true
            end
        end
        set_opt("opt_draw_points", "draw_point_checks")
        set_opt("opt_wdraw", "world_draw_point_checks")
        set_opt("opt_tt", "triple_triad_checks")
        set_opt("opt_boss", "optional_boss_checks")
        set_opt("opt_cards", "rare_card_checks")
        set_opt("opt_sq", "sidequest_checks")
        set_opt("opt_mags", "magazine_checks")
        set_opt("opt_stats", "stat_checks")
        set_opt("opt_abil", "gf_ability_checks")
    end
    -- Follow-the-player: the FF8 client publishes the party's map area here;
    -- subscribe and fetch the current value so the map opens on it. The hints
    -- key is server-managed and drives section highlights on the maps.
    AREA_KEY = string.format("ff8_area_%d_%d",
                             Archipelago.TeamNumber or 0,
                             Archipelago.PlayerNumber or 0)
    HINTS_KEY = string.format("_read_hints_%d_%d",
                              Archipelago.TeamNumber or 0,
                              Archipelago.PlayerNumber or 0)
    Archipelago:SetNotify({AREA_KEY, HINTS_KEY})
    Archipelago:Get({AREA_KEY, HINTS_KEY})
end

function onItem(index, item_id, item_name, player_number)
    if index <= CUR_INDEX then return end
    CUR_INDEX = index
    local code = ITEM_MAPPING[item_id]
    if not code then return end
    local o = Tracker:FindObjectForCode(code)
    if not o then return end
    if COUNTER_CODES[code] then
        -- counters (character / junction / command unlocks)
        if o.AcquiredCount < o.MaxCount then o.AcquiredCount = o.AcquiredCount + 1 end
    else
        o.Active = true
    end
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

function onSetReply(key, value, old_value)
    if key == AREA_KEY then updateAreaTab(value) end
    if key == HINTS_KEY then updateHints(value) end
end

function onRetrieved(key, value)
    if key == AREA_KEY then updateAreaTab(value) end
    if key == HINTS_KEY then updateHints(value) end
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
Archipelago:AddSetReplyHandler("set reply handler", onSetReply)
Archipelago:AddRetrievedHandler("retrieved handler", onRetrieved)
