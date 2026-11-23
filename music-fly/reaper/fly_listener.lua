-- fly_listener.lua - se carga UNA VEZ dentro de REAPER (Actions > Show
-- action list > New action > Load ReaScript...) y despues se corre desde
-- ahi. Reemplaza a fly_listener.py: RPR_defer no existe en la API de Python
-- de REAPER (verificado, ver music-fly/docs/migraciones/F0-puente-reaper.md,
-- actualizacion sobre RPR_defer ausente), y los ReaScripts de Python corren
-- en el hilo principal sin poder ceder control, asi que no pueden persistir.
-- Lua si tiene reaper.defer() real. Como Lua no trae libreria de sockets de
-- fabrica, el transporte es un archivo por lote en vez de UDP: un proceso
-- externo escribe cada lote de comandos a un archivo con rename atomico
-- dentro de QUEUE_DIR, y este script lo drena entero cada tick.

-- Carpeta del repo: variable de entorno FRUITFLY_ROOT, o ~/fruit-fly por defecto.
local ROOT = os.getenv("FRUITFLY_ROOT") or ((os.getenv("HOME") or "") .. "/fruit-fly")
local OUT = ROOT .. "/out/music-fly/f0/"
local QUEUE_DIR = OUT .. "queue/"
local TICK_LOG = OUT .. "tick_log.jsonl"

local ticks_this_second = 0
local second_start = reaper.time_precise()
local total_ticks = 0
local total_commands = 0

local function log_second()
  local now = reaper.time_precise()
  local elapsed = now - second_start
  local hz = elapsed > 0 and (ticks_this_second / elapsed) or 0.0
  local master = reaper.GetMasterTrack(0)
  local peak_l = reaper.Track_GetPeakInfo(master, 0)
  local peak_r = reaper.Track_GetPeakInfo(master, 1)
  local f = io.open(TICK_LOG, "a")
  if f then
    f:write(string.format(
      '{"t": %.3f, "hz_medido": %.2f, "ticks": %d, "elapsed_s": %.3f, ' ..
      '"total_ticks": %d, "total_comandos": %d, "peak_master_l": %.6f, ' ..
      '"peak_master_r": %.6f, "playstate": %d}\n',
      now, hz, ticks_this_second, elapsed, total_ticks, total_commands,
      peak_l, peak_r, reaper.GetPlayState()))
    f:close()
  end
  ticks_this_second = 0
  second_start = now
end

local function split(s)
  local parts = {}
  for tok in string.gmatch(s, "%S+") do
    table.insert(parts, tok)
  end
  return parts
end

-- addfx y testnote son experimentos fuera del vocabulario original de
-- ARQUITECTURA.md 8.2/8.3 (que solo pone parametros de un FX que ya existe).
-- Se agregaron para probar, a pedido del usuario, si la instanciacion real
-- de instrumentos y la salida de audio funcionan de punta a punta con este
-- puente. Ver music-fly/docs/migraciones/F0-puente-reaper.md.

local function handle(cmd, raw)
  if #cmd == 0 then return end
  local op = cmd[1]
  if op == "addtrack" then
    reaper.InsertTrackAtIndex(tonumber(cmd[2]), true)
  elseif op == "additem" then
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    local it = reaper.AddMediaItemToTrack(tr)
    reaper.SetMediaItemInfo_Value(it, "D_POSITION", tonumber(cmd[3]))
    reaper.SetMediaItemInfo_Value(it, "D_LENGTH", cmd[4] and tonumber(cmd[4]) or 2.0)
  elseif op == "moveitem" then
    local it = reaper.GetMediaItem(0, tonumber(cmd[2]))
    reaper.SetMediaItemInfo_Value(it, "D_POSITION", tonumber(cmd[3]))
  elseif op == "fx" then
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    reaper.TrackFX_SetParamNormalized(tr, tonumber(cmd[3]), tonumber(cmd[4]), tonumber(cmd[5]))
  elseif op == "mute" then
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", tonumber(cmd[3]))
  elseif op == "listfx" then
    -- listfx: vuelca todos los FX instalados a un archivo, para saber que
    -- instrumentos hay de verdad en esta maquina (music-fly, F2, pedido del
    -- usuario: "que la mosca use otros plugins", no seguir asumiendo que
    -- solo hay ReaSynth).
    local path = OUT .. "fx_list.txt"
    local f = io.open(path, "w")
    local idx = 0
    while true do
      local retval, name, ident = reaper.EnumInstalledFX(idx)
      if not retval then break end
      f:write(string.format("%d\t%s\t%s\n", idx, name, ident))
      idx = idx + 1
    end
    f:close()
    reaper.ShowConsoleMsg("listfx: " .. idx .. " plugins volcados en " .. path .. "\n")
  elseif op == "dumpstate" then
    local path = OUT .. "state_dump.txt"
    local f = io.open(path, "w")
    local n = reaper.CountTracks(0)
    f:write("CountTracks: " .. n .. "\n")
    for i = 0, n - 1 do
      local tr = reaper.GetTrack(0, i)
      local _, name = reaper.GetTrackName(tr)
      local nitems = reaper.CountTrackMediaItems(tr)
      local nfx = reaper.TrackFX_GetCount(tr)
      local fxname = ""
      if nfx > 0 then
        local _, fn = reaper.TrackFX_GetFXName(tr, 0, "")
        fxname = fn
      end
      f:write(string.format("track %d: name=%s items=%d fx=%d fx0=%s\n", i, name, nitems, nfx, fxname))
    end
    f:close()
    reaper.ShowConsoleMsg("dumpstate: escrito en " .. path .. "\n")
  elseif op == "tempo" then
    -- tempo <bpm>
    reaper.SetCurrentBPM(0, tonumber(cmd[2]), true)
  elseif op == "play" then
    reaper.OnPlayButton()
  elseif op == "stop" then
    reaper.OnStopButton()
  elseif op == "addfx" then
    -- addfx <track> <nombre del fx, puede tener espacios>
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    local fxname = raw:match("^addfx%s+%d+%s+(.+)$")
    local fxidx = reaper.TrackFX_AddByName(tr, fxname, false, -1)
    reaper.ShowConsoleMsg(string.format(
      "fly_listener: addfx '%s' en pista %s -> indice %d (%s)\n",
      fxname, cmd[2], fxidx, fxidx >= 0 and "ok" or "NO ENCONTRADO"))
  elseif op == "cleartrack" then
    -- cleartrack <track>: borra todos los media items de esa pista
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    local n = reaper.CountTrackMediaItems(tr)
    for i = n - 1, 0, -1 do
      reaper.DeleteTrackMediaItem(tr, reaper.GetTrackMediaItem(tr, i))
    end
  elseif op == "setloop" then
    -- setloop <inicio_s> <fin_s>
    reaper.GetSet_LoopTimeRange(true, true, tonumber(cmd[2]), tonumber(cmd[3]), false)
  elseif op == "repeat" then
    -- repeat <0|1>
    reaper.GetSetRepeatEx(0, tonumber(cmd[2]))
  elseif op == "testnote" then
    -- testnote <track> <start_s> <end_s> <pitch> <vel>
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    local start_s, end_s = tonumber(cmd[3]), tonumber(cmd[4])
    local pitch, vel = tonumber(cmd[5]), tonumber(cmd[6])
    local item = reaper.CreateNewMIDIItemInProj(tr, start_s, end_s, false)
    local take = reaper.GetActiveTake(item)
    local ppq_start = reaper.MIDI_GetPPQPosFromProjTime(take, start_s)
    local ppq_end = reaper.MIDI_GetPPQPosFromProjTime(take, end_s)
    reaper.MIDI_InsertNote(take, false, false, ppq_start, ppq_end, 0, pitch, vel, false)
    reaper.MIDI_Sort(take)
  elseif op == "replacenote" then
    -- replacenote <track> <start_s> <end_s> <pitch> <vel>
    -- Igual que testnote, pero primero borra cualquier item que ya
    -- ocupara ese mismo lugar en esa pista. Sin esto, un loop que se
    -- repite por horas apila una nota nueva sobre la vieja en el MISMO
    -- compas cada vez que se repite el ciclo - nunca se reemplaza nada,
    -- solo se amontona (hallazgo del usuario, 2026-09-16: "cuando se
    -- crean chords son todos iguales", eran notas viejas de ciclos
    -- anteriores nunca borradas, no una eleccion repetida del cerebro).
    local tr = reaper.GetTrack(0, tonumber(cmd[2]))
    local start_s, end_s = tonumber(cmd[3]), tonumber(cmd[4])
    local pitch, vel = tonumber(cmd[5]), tonumber(cmd[6])

    local n = reaper.CountTrackMediaItems(tr)
    for i = n - 1, 0, -1 do
      local it = reaper.GetTrackMediaItem(tr, i)
      local pos = reaper.GetMediaItemInfo_Value(it, "D_POSITION")
      local len = reaper.GetMediaItemInfo_Value(it, "D_LENGTH")
      if pos < end_s and (pos + len) > start_s then
        reaper.DeleteTrackMediaItem(tr, it)
      end
    end

    local item = reaper.CreateNewMIDIItemInProj(tr, start_s, end_s, false)
    local take = reaper.GetActiveTake(item)
    local ppq_start = reaper.MIDI_GetPPQPosFromProjTime(take, start_s)
    local ppq_end = reaper.MIDI_GetPPQPosFromProjTime(take, end_s)
    reaper.MIDI_InsertNote(take, false, false, ppq_start, ppq_end, 0, pitch, vel, false)
    reaper.MIDI_Sort(take)
  else
    reaper.ShowConsoleMsg("fly_listener: comando desconocido: " .. tostring(op) .. "\n")
  end
end

local function list_queue_files()
  local files = {}
  local idx = 0
  while true do
    local fname = reaper.EnumerateFiles(QUEUE_DIR, idx)
    if not fname then break end
    if fname:match("%.cmd$") then
      table.insert(files, fname)
    end
    idx = idx + 1
  end
  table.sort(files)
  return files
end

local function drain_queue()
  local drained = 0
  for _, fname in ipairs(list_queue_files()) do
    local path = QUEUE_DIR .. fname
    local f = io.open(path, "r")
    if f then
      for line in f:lines() do
        -- pcall: un comando mal formado (ej. una pista que no existe)
        -- no puede tirar todo el listener abajo. Antes, un error de Lua
        -- sin atrapar mataba el defer loop entero y no habia forma de
        -- notarlo salvo que el reloj de ritmo se congelara - costo varios
        -- reinicios completos descubrir esto (ver
        -- music-fly/docs/migraciones/F2-consola.md).
        local ok, err = pcall(handle, split(line), line)
        if not ok then
          reaper.ShowConsoleMsg("fly_listener: ERROR en comando '" .. line .. "': " .. tostring(err) .. "\n")
        end
        drained = drained + 1
      end
      f:close()
    end
    os.remove(path)
  end
  return drained
end

local function tick()
  local drained = drain_queue()
  if drained > 0 then
    reaper.UpdateArrange()
    total_commands = total_commands + drained
  end

  total_ticks = total_ticks + 1
  ticks_this_second = ticks_this_second + 1
  if reaper.time_precise() - second_start >= 1.0 then
    log_second()
  end

  reaper.defer(tick)
end

reaper.ShowConsoleMsg(
  "fly_listener (lua): escuchando en " .. QUEUE_DIR .. ", log de ritmo en " .. TICK_LOG .. "\n"
)
tick()
