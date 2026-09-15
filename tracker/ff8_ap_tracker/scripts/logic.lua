-- Access-rule helpers. Mirrors the region gating in ff8/__init__.py:
-- a linear chain of story beats, each entered at its story progress index
-- AND the gate ladder for it (regions.gate_requirements), plus the three
-- travel hubs (vanilla grant beat OR the vehicle item).

-- Seed options, set from slot_data by autotracking.lua (defaults = the
-- apworld defaults, so an unconnected tracker shows the default logic).
AP_OPTS = {
    story_gates = "normal",
    gfs_required_for_disc3 = 6,
    character_locks = true,
    junction_locks = true,
    command_locks = true,
    vehicle_unlocks = false,
    vehicle_gates = false,
    story_keys = "off",
}
STORY_GATE_MODES = {[0] = "off", [1] = "normal", [2] = "tight"}
STORY_KEY_MODES = {[0] = "off", [1] = "areas", [2] = "story"}

function at_progress(n)
    local o = Tracker:FindObjectForCode("progress")
    return o ~= nil and o.AcquiredCount >= tonumber(n)
end

COUNTER_CODES = {char_unlocks = true, junction_unlocks = true, command_unlocks = true}

local function count(code)
    local o = Tracker:FindObjectForCode(code)
    if o == nil then return 0 end
    if COUNTER_CODES[code] then return o.AcquiredCount end
    return o.Active and 1 or 0
end

-- regions.gate_requirements: item counts needed to ENTER beat `idx`.
function beat_requirements(idx)
    local anchor = tonumber(AP_OPTS.gfs_required_for_disc3) or 0
    local mode = AP_OPTS.story_gates
    local gfs, chars, junctions, commands = 0, 0, 0, 0
    if mode == "off" then
        if idx == FIRST_DISC3_BEAT then gfs = anchor end
        return gfs, 0, 0, 0
    end
    local row = GATE_LADDER[mode] and GATE_LADDER[mode][BEAT_NAMES[idx]]
    if row == nil then return 0, 0, 0, 0 end
    if anchor > 0 then
        gfs = math.floor((row[1] * anchor * 2 + GF_ANCHOR) / (2 * GF_ANCHOR))
        if gfs > GF_TOTAL then gfs = GF_TOTAL end
    end
    if AP_OPTS.character_locks then chars = row[2] end
    if AP_OPTS.junction_locks then junctions = row[3] end
    if AP_OPTS.command_locks then commands = row[4] end
    return gfs, chars, junctions, commands
end

function beat_access(n)
    local idx = tonumber(n)
    if not at_progress(idx) then return false end
    local gfs, chars, junctions, commands = beat_requirements(idx)
    if Tracker:ProviderCountForCode("gf") < gfs then return false end
    -- one character, one junction right and the Draw command are always
    -- precollected; the server sends them on connect, so counts include them.
    if count("char_unlocks") < chars then return false end
    if count("junction_unlocks") < junctions then return false end
    if count("command_unlocks") < commands then return false end
    if AP_OPTS.vehicle_unlocks and AP_OPTS.vehicle_gates then
        local vehicle = VEHICLE_BEATS[BEAT_NAMES[idx]]
        if vehicle and count(vehicle) < 1 then return false end
    end
    if AP_OPTS.story_keys == "story" then
        for _, code in ipairs(STORY_KEY_BEATS[BEAT_NAMES[idx]] or {}) do
            if count(code) < 1 then return false end
        end
    end
    return true
end

-- A check inside a keyed area: needs the door's key while story keys are on.
function key_access(code)
    if AP_OPTS.story_keys == "off" then return true end
    return count(code) >= 1
end

function hub_access(grant_idx, vehicle_code)
    if AP_OPTS.vehicle_unlocks and count(vehicle_code) >= 1 then return true end
    return beat_access(grant_idx)
end

-- An early-entry area: its first beat, or the ship (vehicle_unlocks); a door
-- the game gates on the story moment also needs story keys on, since only
-- then does the client lower the gate. The area's key is a separate rule on
-- each check (key_access).
function early_access(first_idx, vehicle_code, gated)
    if AP_OPTS.vehicle_unlocks and count(vehicle_code) >= 1
            and (tonumber(gated) == 0 or AP_OPTS.story_keys ~= "off") then
        return true
    end
    return beat_access(first_idx)
end
