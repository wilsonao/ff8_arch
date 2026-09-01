-- Access-rule helpers. Mirrors the region gating in ff8/__init__.py:
-- a linear story chain, plus a GF-count threshold in front of Disc 3.

GF_THRESHOLD_DEFAULT = 6
AP_GF_THRESHOLD = nil  -- set from slot_data by autotracking.lua

function at_progress(n)
    local o = Tracker:FindObjectForCode("progress")
    return o ~= nil and o.AcquiredCount >= tonumber(n)
end

function disc3_access()
    if not at_progress(7) then
        return false
    end
    local need = AP_GF_THRESHOLD or GF_THRESHOLD_DEFAULT
    return Tracker:ProviderCountForCode("gf") >= need
end
