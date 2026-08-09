-- BizHawk Lua half of the in-game verification harness.
--
-- Reads a job file written by tools/ingame_verify.py, injects the save under
-- test straight into the CARTRAM domain, boots to the file-select screen,
-- loads the save, and dumps each character's live inventory out of WRAM.
--
-- Injecting into CARTRAM rather than dropping a file in BizHawk's SaveRAM
-- directory keeps the harness independent of the emulator's path config.
--
-- Nothing here knows what "correct" means; it reports what the game loaded
-- and the Python side does the comparing.

local JOB = os.getenv("EBBR_JOB")
assert(JOB, "EBBR_JOB not set")

local function load_job()
  local t = {}
  for line in io.lines(JOB) do
    -- Trim trailing CR: a job file written on Windows arrives CRLF, and a
    -- stray \r on a path makes io.open fail in a way that only shows up as
    -- the emulator hanging on an error dialog.
    local k, v = line:match("^(%w+)=(.-)%s*$")
    if k then t[k] = v end
  end
  return t
end

local job = load_job()
local out = io.open(job.out, "w")
local function say(s) out:write(tostring(s) .. "\n") out:flush() end

local f = assert(io.open(job.srm, "rb"))
local blob = f:read("*all"); f:close()

local function press(btn, n)
  for _ = 1, (n or 3) do joypad.set({ [btn] = true }, 1); emu.frameadvance() end
  for _ = 1, 12 do emu.frameadvance() end
end
local function wait(n) for _ = 1, n do emu.frameadvance() end end
local function shot(tag)
  if job.shots and job.shots ~= "" then
    client.screenshot(job.shots .. "/" .. tag .. ".png")
  end
end

-- Run as fast as the host allows; nothing here is timing sensitive.
pcall(function() client.speedmode(800) end)
pcall(function() client.SetSoundOn(false) end)

-- 1. Inject during the splash. The game reads SRAM when file-select opens,
--    so it does not matter that the core booted with whatever was there.
wait(120)
memory.usememorydomain("CARTRAM")
for i = 1, #blob do memory.write_u8(i - 1, blob:byte(i)) end
say("injected=" .. #blob)

-- 2. Intro -> file select -> load slot 1.
for _ = 1, 8 do press("Start", 4); wait(70) end
shot("01_fileselect")
press("A", 4); wait(150)
for _ = 1, 5 do press("A", 4); wait(80) end
shot("02_ingame")

-- 3. Dismiss the opening dialogue and open Goods for the first character.
for _ = 1, 6 do press("B", 3); wait(30) end
wait(60)
press("A", 3); wait(40)
press("Right", 3); wait(30)
press("A", 3); wait(60)
shot("03_pick_char")
press("A", 3); wait(80)
shot("04_bag")

-- 4. Report the live inventories. Each character's bag is located by its own
--    byte signature rather than a hardcoded address, so this keeps working if
--    the layout shifts between builds.
memory.usememorydomain("WRAM")
local size = memory.getmemorydomainsize("WRAM")
local wram = memory.readbyterange(0, size)

-- Collect the needles, then sweep WRAM once looking for all of them at each
-- position. One pass over 128 KB rather than one pass per character; the
-- per-character version was slow enough to blow the harness timeout.
local wanted = {}
for cid = 0, 3 do
  local spec = job["bag" .. cid]
  if spec and spec ~= "" then
    local needle = {}
    for byte in spec:gmatch("%x%x") do needle[#needle + 1] = tonumber(byte, 16) end
    -- A bag of all-zeros would match almost anywhere; skip those.
    if #needle > 0 and needle[1] ~= 0 then
      wanted[#wanted + 1] = { cid = cid, needle = needle, at = nil }
    end
  end
end

local longest = 0
for _, w in ipairs(wanted) do
  if #w.needle > longest then longest = #w.needle end
end

for a = 0, size - longest do
  local byte = wram[a]
  for _, w in ipairs(wanted) do
    if w.at == nil and byte == w.needle[1] then
      local ok = true
      for k = 2, #w.needle do
        if wram[a + k - 1] ~= w.needle[k] then ok = false break end
      end
      if ok then w.at = a end
    end
  end
end

for _, w in ipairs(wanted) do
  if w.at then
    local got = {}
    for i = 0, 13 do got[#got + 1] = string.format("%02X", wram[w.at + i]) end
    say(string.format("bag%d=FOUND@%05X %s", w.cid, w.at, table.concat(got, "")))
  else
    say(string.format("bag%d=MISSING", w.cid))
  end
end

say("done")
out:close()
client.exit()
