-- =================================================================================================
-- Настройки LUA
-- =================================================================================================
config = {
    paths = {
        folder_scripts = './nix/scripts/',
        folder_lua = './nix/scripts/kensoLUA/',
    },
    sounds = {
        click = 'sounds/kensosfx/click.vsnd',
        loader_final = 'sounds/ui/xp_star_full_03.vsnd',
        loader_loads = 'sounds/ui/xp_remaining.vsnd',
        respawn = 'sounds/kensosfx/click.vsnd',
    },
    links = {
        apis = {
            github = {
                files_lua = 'https://raw.githubusercontent.com/lisikme/Nixware-allowed/master/',
            },
        },
    },
}
gui = {}

-- =================================================================================================
-- Цвета
-- =================================================================================================
local Color = {}
Color.__index = Color
function t_new_color(r, g, b, a) return
    setmetatable({r = r or 0, g = g or 0, b = b or 0, a = a or 1}, Color) end
function Color:hex() return string.format(
    "#%02x%02x%02x%02x",
    math.floor(self.r*255+0.5), math.floor(self.g*255+0.5), math.floor(self.b*255+0.5), math.floor(self.a*255+0.5)) end
function Color:rgb() return {
    math.floor(self.r*255+0.5), math.floor(self.g*255+0.5), math.floor(self.b*255+0.5)} end
function Color:rgba() return {
    math.floor(self.r*255+0.5), math.floor(self.g*255+0.5), math.floor(self.b*255+0.5), math.floor(self.a*255+0.5)} end
function Color:color_t()
    return color_t(self.r, self.g, self.b, self.a)
end
function get_color(a, b, c, d)
    if type(a) == "string" then
        local hex = a:gsub("^#", "")
        local r, g, bl, al = 0, 0, 0, 1
        if #hex == 3 then
            r = tonumber(hex:sub(1,1):rep(2), 16)
            g = tonumber(hex:sub(2,2):rep(2), 16)
            bl = tonumber(hex:sub(3,3):rep(2), 16)
        elseif #hex == 4 then
            r = tonumber(hex:sub(1,1):rep(2), 16)
            g = tonumber(hex:sub(2,2):rep(2), 16)
            bl = tonumber(hex:sub(3,3):rep(2), 16)
            al = tonumber(hex:sub(4,4):rep(2), 16)/255
        elseif #hex == 6 then
            r = tonumber(hex:sub(1,2), 16)
            g = tonumber(hex:sub(3,4), 16)
            bl = tonumber(hex:sub(5,6), 16)
        elseif #hex == 8 then
            r = tonumber(hex:sub(1,2), 16)
            g = tonumber(hex:sub(3,4), 16)
            bl = tonumber(hex:sub(5,6), 16)
            al = tonumber(hex:sub(7,8), 16)/255
        else
            error("Invalid hex color format: " .. a)
        end
        if b ~= nil then
            al = (b > 1) and (b / 255) or b
        end
        return t_new_color(r / 255, g / 255, bl / 255, al)
    end
    if type(a) == "number" then
        local r, g, bl, al = a, b or 0, c or 0, d
        al = al > 1 and al/255 or 1
        return t_new_color(r/255, g/255, bl/255, al)
    end
    error("get_color: unsupported arguments")
end

local orig_calc_text_size = render.calc_text_size
local orig_text = render.text
local orig_chat_print = engine.chat_print
local orig_vec2_t = vec2_t

render.calc_text_size = function(text, font, size)
    local clean = text
        :gsub("{%#[%x]+}", "")
        :gsub("{A#%x+}", "")
        :gsub("{T#%x+}", "")
        :gsub("{/#}", "")
    if clean:find("\n", 1, true) then
        local max_w = 0
        local total_h = 0
        local line_h = 0
        local start = 1
        while true do
            local nl = clean:find("\n", start, true)
            local line
            if nl then
                line = clean:sub(start, nl - 1)
                start = nl + 1
            else
                line = clean:sub(start)
            end
            local sz = orig_calc_text_size(line ~= "" and line or "A", font, size)
            if sz.x > max_w then max_w = sz.x end
            line_h = sz.y
            total_h = total_h + line_h
            if not nl then break end
        end
        return vec2_t(max_w, total_h)
    end

    return orig_calc_text_size(clean, font, size)
end

render.text = function(text, font, pos, color)
    local color = color or color_t(200/255, 200/255, 200/255, 1)
    local x = pos.x
    local y = pos.y
    local start_x = pos.x
    local curr_color = color
    local i = 1
    local len = #text
    local ga = gui.alpha and gui.alpha or 1
    local line_height = orig_calc_text_size("A", font, nil).y
    while i <= len do
        if text:sub(i, i) == "\n" then
            x = start_x
            y = y + line_height
            i = i + 1
        elseif text:sub(i, i) == "{" and text:sub(i+1, i+2) == "/#" then
            local close = text:find("}", i, true)
            if close then
                curr_color = color
                i = close + 1
            else
                orig_text(text:sub(i, i), font, vec2_t(x, y), curr_color)
                x = x + render.calc_text_size(text:sub(i, i), font).x
                i = i + 1
            end
        elseif text:sub(i, i) == "{" and text:sub(i+1, i+1) == "A" and text:sub(i+2, i+2) == "#" then
            local close = text:find("}", i, true)
            if close then
                local hex = text:sub(i+3, close-1)
                local c = get_color("#" .. hex)
                curr_color = color_t(c.r, c.g, c.b, c.a * ga)
                i = close + 1
            else
                orig_text(text:sub(i, i), font, vec2_t(x, y), curr_color)
                x = x + render.calc_text_size(text:sub(i, i), font).x
                i = i + 1
            end
        elseif text:sub(i, i) == "{" and text:sub(i+1, i+1) == "T" and text:sub(i+2, i+2) == "#" then
            local close = text:find("}", i, true)
            if close then
                local hex = text:sub(i+3, close-1)
                local c = get_color("#" .. hex)
                curr_color = color_t(c.r, c.g, c.b, curr_color.a)
                i = close + 1
            else
                orig_text(text:sub(i, i), font, vec2_t(x, y), curr_color)
                x = x + render.calc_text_size(text:sub(i, i), font).x
                i = i + 1
            end
        elseif text:sub(i, i) == "{" and text:sub(i+1, i+1) == "#" then
            local close = text:find("}", i, true)
            if close then
                local hex = text:sub(i+2, close-1)
                local c = get_color("#" .. hex)
                curr_color = color_t(c.r, c.g, c.b, c.a)
                i = close + 1
            else
                orig_text(text:sub(i, i), font, vec2_t(x, y), curr_color)
                x = x + render.calc_text_size(text:sub(i, i), font).x
                i = i + 1
            end
        else
            local next_tag = text:find("{#", i, true)
            local next_alpha_tag = text:find("{A#", i, true)
            local next_transparent_tag = text:find("{T#", i, true)
            local next_reset = text:find("{/#}", i, true)
            local next_newline = text:find("\n", i, true)
            local next_tag_pos = next_tag
            if next_alpha_tag and (not next_tag_pos or next_alpha_tag < next_tag_pos) then next_tag_pos = next_alpha_tag end
            if next_transparent_tag and (not next_tag_pos or next_transparent_tag < next_tag_pos) then next_tag_pos = next_transparent_tag end
            if next_reset and (not next_tag_pos or next_reset < next_tag_pos) then next_tag_pos = next_reset end
            if next_newline and (not next_tag_pos or next_newline < next_tag_pos) then next_tag_pos = next_newline end
            local chunk
            if next_tag_pos then
                chunk = text:sub(i, next_tag_pos - 1)
                i = next_tag_pos
            else
                chunk = text:sub(i)
                i = len + 1
            end
            if #chunk > 0 then
                orig_text(chunk, font, vec2_t(x, y), curr_color)
                x = x + render.calc_text_size(chunk, font).x
            end
        end
    end
end
vec2_t = function(x, y) return orig_vec2_t(math.floor(x), math.floor(y)) end

function str(str, context)
    return (str:gsub("%${([^}]+)}", function(path)
        local parts = {}
        for part in path:gmatch("[^.]+") do table.insert(parts, part) end
        local value = context
        for _, part in ipairs(parts) do
            if type(value) ~= "table" then return '${'..part..'}' end
            value = value[part]
            if value == nil then return '${'..part..'}' end
        end
        return tostring(value)
    end))
end

timestamp = "?t="..tostring(os.clock())
config_files = {
    [config.paths.folder_lua..'fonts/Unbounded-Medium.ttf'] = {config.links.apis.github.files_lua..'Unbounded-Medium.ttf'..timestamp, false},
    [config.paths.folder_lua..'images/loader/nanally.png'] = {'https://kensohub.ru/resources/images/global/nanally.png'..timestamp, false}
}
engine.execute_client_cmd("stopsound")

-- =================================================================================================
-- Глобальные переменные / FFI
-- =================================================================================================
ffi = require("ffi")
bit = require("bit")
user32 = ffi.load("user32")
winhttp = ffi.load("WinHttp")
advapi32 = ffi.load("advapi32")
kernel32 = ffi.load("kernel32")
MAX_RESPONSE = 5000000

-- =================================================================================================
-- FFI: POINT + WinAPI
-- =================================================================================================
pcall(function()
    ffi.cdef[[
        typedef struct { long x; long y; } POINT;
        int GetCursorPos(POINT* lpPoint);
        int ScreenToClient(void* hWnd, POINT* lpPoint);
        short GetAsyncKeyState(int vKey);
        void* GetForegroundWindow();
        int GetWindowTextA(void*, char*, int);
        int GetWindowThreadProcessId(void* hWnd, unsigned long* lpdwProcessId);
        unsigned long GetCurrentProcessId();
        unsigned long GetTickCount();
    ]]
end)

-- =================================================================================================
-- API: чат / числа
-- =================================================================================================
chat = {
    Colors = function(text)
        local color_map = {
            ['default']     = '\x01', ['white']       = '\x01',
            ['darkred']     = '\x02', ['lightpurple'] = '\x03',
            ['green']       = '\x04', ['lightgreen']  = '\x05',
            ['slimegreen']  = '\x06', ['red']         = '\x07',
            ['grey']        = '\x08', ['yellow']      = '\x09',
            ['invisible']   = '\x0A', ['lightblue']   = '\x0B',
            ['blue']        = '\x0C', ['purple']      = '\x0D',
            ['pink']        = '\x0E', ['fadedred']    = '\x0F',
            ['gold']        = '\x10',
        }
        return text:gsub('{(%w+)}', function(color)
            return color_map[color:lower()] or '{'..color..'}'
        end)
    end,
}
number = {
    DecimalFormat = function(value, sub)
        local str = tostring(math.floor(value))
        local f = ""
        local dc = 0
        str = (sub and #str > sub) and str:sub(1, sub) or str
        for i = #str, 1, -1 do
            dc = dc+1
            f = str:sub(i, i)..f
            if dc % 3 == 0 and i > 1 then f = ","..f end
        end
        return f
    end,
}

-- =================================================================================================
-- Системные команды
-- =================================================================================================
ffi.cdef[[
    int WinExec(const char *lpCmdLine, unsigned int uCmdShow)
]]
ffi.cdef[[
    typedef void* HANDLE;
    typedef unsigned long DWORD;
    typedef int BOOL;
    BOOL CreateProcessA(
        const char* lpApplicationName,
        char* lpCommandLine,
        void* lpProcessAttributes,
        void* lpThreadAttributes,
        BOOL bInheritHandles,
        DWORD dwCreationFlags,
        void* lpEnvironment,
        const char* lpCurrentDirectory,
        void* lpStartupInfo,
        void* lpProcessInformation
    );
    DWORD GetLastError(void);
    void CloseHandle(HANDLE hObject);
    static const DWORD STARTF_USESHOWWINDOW = 0x00000001;
    static const DWORD CREATE_NO_WINDOW = 0x08000000;
    static const DWORD SW_HIDE = 0;
]]
local STARTUPINFO = ffi.typeof[[
    struct {
        DWORD cb;
        char* lpReserved;
        char* lpDesktop;
        char* lpTitle;
        DWORD dwX;
        DWORD dwY;
        DWORD dwXSize;
        DWORD dwYSize;
        DWORD dwXCountChars;
        DWORD dwYCountChars;
        DWORD dwFillAttribute;
        DWORD dwFlags;
        DWORD wShowWindow;
        DWORD cbReserved2;
        char* lpReserved2;
        HANDLE hStdInput;
        HANDLE hStdOutput;
        HANDLE hStdError;
    }
]]
local PROCESS_INFORMATION = ffi.typeof[[struct {
    HANDLE hProcess;
    HANDLE hThread;
    DWORD dwProcessId;
    DWORD dwThreadId;
}]]

function run_cmd(cmd)
    if not cmd or cmd == "" then return false end
    local si = ffi.new(STARTUPINFO)
    si.cb = ffi.sizeof(si)
    si.dwFlags = ffi.C.STARTF_USESHOWWINDOW
    si.wShowWindow = ffi.C.SW_HIDE
    local pi = ffi.new(PROCESS_INFORMATION)
    local cmd_buf = ffi.new("char[?]", #cmd + 1)
    ffi.copy(cmd_buf, cmd)
    local result = ffi.C.CreateProcessA(nil, cmd_buf, nil, nil, false, ffi.C.CREATE_NO_WINDOW, nil, nil, si, pi)
    if result == 0 then print("[KensoLUA] CreateProcessA error: "..ffi.C.GetLastError()); return false end
    if pi.hProcess then ffi.C.CloseHandle(pi.hProcess) end
    if pi.hThread then ffi.C.CloseHandle(pi.hThread) end
    return true
end
function exit_app(cmd)
    run_cmd('taskkill /f /im '..cmd)
end

-- =================================================================================================
-- Звуки
-- =================================================================================================
function PlaySound(path, volume, mode)
    if type(path) ~= "string" or path == "" then return end
    local original_sound_vol = 1
    if cvars and cvars.snd_toolvolume then
        local val = cvars.snd_toolvolume:get_float()
        if val then original_sound_vol = val end
    end
    if mode == true then
        engine.execute_client_cmd('snd_toolvolume '..volume)
        engine.execute_client_cmd('play '..path)
    else
        engine.execute_client_cmd('snd_toolvolume 1')
        engine.play_sound(path, volume)
    end
end

-- =================================================================================================
-- RGB / HSV
-- =================================================================================================
function HSVToRGB(h, s, v)
    h = h%360
    c = v*s
    h_prime = h/60
    x = c*(1-math.abs(h_prime%2-1))
    m = v-c
    r, g, b = 0, 0, 0
    if h_prime < 1 then r, g, b = c, x, 0
    elseif h_prime < 2 then r, g, b = x, c, 0
    elseif h_prime < 3 then r, g, b = 0, c, x
    elseif h_prime < 4 then r, g, b = 0, x, c
    elseif h_prime < 5 then r, g, b = x, 0, c
    else r, g, b = c, 0, x
    end
    return color_t(r + m, g+m, b+m, 1)
end

function color_from_hsv(h, s, v, a)
    local r, g, b
    local i = math.floor(h * 6)
    local f = h * 6 - i
    local p = v * (1 - s)
    local q = v * (1 - f * s)
    local t = v * (1 - (1 - f) * s)
    i = i % 6
    if i == 0 then r, g, b = v, t, p
    elseif i == 1 then r, g, b = q, v, p
    elseif i == 2 then r, g, b = p, v, t
    elseif i == 3 then r, g, b = p, q, v
    elseif i == 4 then r, g, b = t, p, v
    elseif i == 5 then r, g, b = v, p, q
    end
    return color_t(r, g, b, a or 1)
end

-- =================================================================================================
-- Мышь
-- =================================================================================================
function get_mouse_pos()
    local point = ffi.new("POINT[1]")
    user32.GetCursorPos(point)
    local hwnd = user32.GetForegroundWindow()
    if hwnd then
        user32.ScreenToClient(hwnd, point)
    end
    return vec2_t(point[0].x, point[0].y)
end

cgf = color_t(1, 1, 1, 1)

-- ВАЖНО: Защита от кликов по меню Nixware
function isCursorOutsideMenu()
    local rect = ui.get_menu_rect()
    local m_pos = get_mouse_pos()
    return not (
        m_pos.x >= rect.x and
        m_pos.x <= rect.z and
        m_pos.y >= rect.y and
        m_pos.y <= rect.w
    )
end

-- =================================================================================================
-- Активное окно игры
-- =================================================================================================
local active = false
register_callback("paint", function()
    local hwnd = user32.GetForegroundWindow()
    if hwnd == nil then active = false return end
    local buf = ffi.new("char[256]")
    active = user32.GetWindowTextA(hwnd, buf, 256) > 0 and string.find(ffi.string(buf), "Counter%-Strike 2") ~= nil
end)
function isGameActive_CS2Monitor() return active end

-- =================================================================================================
-- Файлы
-- =================================================================================================
function file_exists(path)
    local f = io.open(path, "r")
    if f then f:close() return true end
    return false
end
function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    return content
end
function write_file(path, content)
    local f = io.open(path, "w")
    if not f then return false end
    f:write(content)
    f:close()
    return true
end
function download_file(path, url, force_download)
    force_download = force_download or false
    if file_exists(path) and not force_download then return false end
    local folder_path = path:match("(.*)[\\/]")
    if folder_path and not file_exists(folder_path) then create_dir(folder_path) end
    local normalized_path = path:gsub("\\", "/")
    run_cmd(string.format([[powershell -WindowStyle Hidden -Command "Invoke-WebRequest -Uri '%s' -OutFile '%s'"]], url, normalized_path))
    return true
end
function download_files(files_table)
    for file_path, file_info in pairs(files_table) do
        local url, force = nil, false
        if type(file_info) == 'table' then
            url = file_info[1]
            force = file_info[2] or false
        elseif type(file_info) == 'string' then
            url = file_info
        end
        local folder_path = file_path:match("(.*)[\\/]")
        if folder_path and not file_exists(folder_path) then
            create_dir(folder_path)
        end
        download_file(file_path, url, force)
    end
    print("[KensoLUA] Загрузка завершена!")
end
function fileExists(path)
    local ok, res = pcall(function()
        local file = io.open(path, "r")
        if file then file:close() return true end
        return false
    end)
    return ok and res or false
end
function create_dir(path)
    path = path:gsub('^"?(.-)"?$', '%1'):gsub('/', '\\')
    run_cmd(string.format('cmd /c md "%s" 2>nul', path))
    return true
end

create_dir(config.paths.folder_lua)
create_dir(config.paths.folder_lua..'images/loader')
create_dir(config.paths.folder_lua..'images/rangs')
create_dir(config.paths.folder_lua..'fonts/')
download_files(config_files)

-- =================================================================================================
-- Шрифты
-- =================================================================================================
calibrib = "C:/windows/fonts/calibrib.ttf"
fontpatch130 = "C:/windows/fonts/consola.ttf"
customFont = config.paths.folder_lua.."fonts/Rubik-SemiBold.ttf"
customFont2 = config.paths.folder_lua.."fonts/Unbounded-Medium.ttf"
DefaultFont = config.paths.folder_lua.."fonts/Rubik-SemiBold.ttf"
customFont = config.paths.folder_lua.."fonts/Rubik-SemiBold.ttf"
experFont = config.paths.folder_lua.."fonts/Stratum2-Black.ttf"
if fileExists(experFont) then experFont = customFont else experFont = experFont end
if fileExists(customFont) then fontpatch = customFont else fontpatch = calibrib end
if fileExists(customFont2) then fontpatch2 = customFont2 else fontpatch2 = calibrib end

ffi.cdef[[
    short GetAsyncKeyState(int vKey);
    void keybd_event(unsigned char bVk, unsigned char bScan, unsigned long dwFlags, unsigned long dwExtraInfo);
]]

-- =================================================================================================
-- Экран загрузки (loader)
-- =================================================================================================
terminal_phrases = {
    "menu_force_thirdperson = false",
    "menu_colision_thirdperson = false",
    "menu_skip_intro_team = false",
    "menu_killschat_enabled = false",
    "menu_buy_bot = true",
    "menu_preserve_killfeed = false",
    "menu_respawn_enabled = false",
    "menu_hitmarker_enabled = false",
    "menu_mvp_enabled = false",
    "menu_fakeaa_enabled = false",
    "menu_custom_pitch_yaw = false",
    "menu_random_yaw_enabled = false",
    "menu_manual_aa_enabled = false",
    "menu_air_flick_enabled = false",
    "menu_manual_aa_offset = 90",
    "menu_disable_ragebot_in_air_enabled = false",
    "menu_wallbang_helper_enabled = false",
    "menu_savemode = false",
    "menu_watermark_enabled = false",
    "menu_velocity_indicator = false",
    "menu_hitlogs_enabled = true",
    "manualaa_text_enabled = false",
    "menu_guiseed = false",
    "menu_guihp = false",
    "menu_stattrack_enabled = false",
    "menu_guiplayers_enabled = false",
    "menu_mvp_ui = false",
    "menu_speed_indicator = false",
    "menu_rgbscreen = false",
    "menu_fov_enabled = false",
}
fxcmdtext = 'KensoLUA - Loadings...\n'
fxcmdfont = render.setup_font(fontpatch, 14, 000)
final_font = render.setup_font(fontpatch, 120, 000)
current_phrase_index = 1
last_update_time = os.clock() * 1000
update_interval_ms = 2
pause_interval = 0
pause_duration_ms = 0
pause_start_time = 0
is_paused = false
show_final_message = false
final_message_duration_ms = 1000
final_message_start_time = 0
fxcmdcolor = color_t(170/255, 220/255, 255/255, 1)
final_color = color_t(200/255, 255/255, 123/255, 1)
fxs = 0
fxsold = 0
showconsolefx = true
finate = 0
idslash = false
bg_alpha = 0
bg_fade_in_duration = 700
bg_fade_out_duration = 700
bg_fade_start_time = 0
is_fading_in = false
is_fading_out = false
final_font = render.setup_font(fontpatch, 120, 000)
final_font2 = render.setup_font(fontpatch, 20, 000)

local LOADER_CONFIG = {
    CMD_DELAY_MS = 0.009 * 1000,
    FINAL_SHOW_MS = 1.3 * 1000,
    FADE_IN_MS = 0.3 * 1000,
    FADE_OUT_MS = 0.3 * 1000,
    TEXT_FLY_SPEED = 5,
    BAR_WIDTH = 250,
    BAR_HEIGHT = 12,
    BAR_Y_OFFSET = 70,
    LOG_START_OFFSET = 15,
    LINE_HEIGHT = 14,
    LOG_ALPHAS = {1.0, 0.93, 0.86, 0.79, 0.72, 0.65, 0.58, 0.51, 0.44, 0.37, 0.30, 0.23, 0.16, 0.09, 0.02},
    BG_COLOR = {6/255, 8/255, 12/255},
    ACCENT_COLOR = {215/255, 254/255, 123/255},
    TEXT_COLOR = {170/255, 220/255, 255/255},
}

local loader_state = {
    log_lines = {},
    current_phrase_index = 1,
    total_phrases = 0,
    last_update_time = 0,
    is_paused = false,
    pause_start_time = 0,
    show_final_message = false,
    final_message_start_time = 0,
    showconsolefx = true,
    idslash = false,
    finate = 0,
    bg_alpha = 0,
    is_fading_in = false,
    is_fading_out = false,
    bg_fade_start_time = 0,
    text_y_offset = -100,
    has_animation_played = false,
    is_animation_playing = false,
    phase = "idle",
}

for i = 1, 15 do
    loader_state.log_lines[i] = {text = "", alpha = 0}
end

function clear_logs()
    for i = 1, 15 do
        loader_state.log_lines[i].text = ""
        loader_state.log_lines[i].alpha = 0
    end
end

local slashfont = render.setup_font(fontpatch2, 70, 000)
local slashverfont = render.setup_font(fontpatch2, 20, 000)
local slashauthorfont = render.setup_font(fontpatch2, 16, 000)
local slashloadfont = render.setup_font(fontpatch2, 14, 000)
local slashcmdfont = render.setup_font(fontpatch2, 14, 000)

function fxscreen()
    if loader_state.has_animation_played then return end
    local current_time = os.clock() * 1000

    if not loader_state.idslash then
        if loader_state.is_animation_playing then return end
        loader_state.menu_was_open = ui.is_menu_opened()
        if loader_state.menu_was_open then
            local VK_ALT = 0x12
            local VK_INSERT = 0x2D
            ffi.C.keybd_event(VK_ALT, 0, 0, 0)
            ffi.C.keybd_event(VK_INSERT, 0, 0, 0)
            ffi.C.keybd_event(VK_ALT, 0, 2, 0)
            ffi.C.keybd_event(VK_INSERT, 0, 2, 0)
        end
        loader_state.is_animation_playing = true
        is_active = true
        loader_state.idslash = true
        loader_state.phase = "loading"
        loader_state.is_fading_in = true
        loader_state.bg_fade_start_time = current_time
        loader_state.total_phrases = #terminal_phrases
        loader_state.current_phrase_index = 1
        loader_state.show_final_message = false
        loader_state.showconsolefx = true
        loader_state.text_y_offset = -100
        clear_logs()
    end

    if not is_active then return end
    local screen = render.screen_size()
    local center_x = screen.x / 2
    local center_y = screen.y / 2

    if loader_state.is_fading_in then
        local elapsed = current_time - loader_state.bg_fade_start_time
        if elapsed >= LOADER_CONFIG.FADE_IN_MS then
            loader_state.bg_alpha = 0.85
            loader_state.is_fading_in = false
        else
            loader_state.bg_alpha = 0.85 * (elapsed / LOADER_CONFIG.FADE_IN_MS)
        end
    elseif loader_state.is_fading_out then
        local elapsed = current_time - loader_state.bg_fade_start_time
        if elapsed >= LOADER_CONFIG.FADE_OUT_MS then
            loader_state.bg_alpha = 0
            loader_state.is_fading_out = false
            is_active = false
            clear_logs()
            loader_state.has_animation_played = true
            loader_state.is_animation_playing = false
            loader_state.phase = "idle"
            loader_state.menu_was_open = ui.is_menu_opened()
            if not loader_state.menu_was_open then
                local VK_ALT = 0x12
                local VK_INSERT = 0x2D
                ffi.C.keybd_event(VK_ALT, 0, 0, 0)
                ffi.C.keybd_event(VK_INSERT, 0, 0, 0)
                ffi.C.keybd_event(VK_ALT, 0, 2, 0)
                ffi.C.keybd_event(VK_INSERT, 0, 2, 0)
            end
        else
            loader_state.bg_alpha = 0.85 * (1 - (elapsed / LOADER_CONFIG.FADE_OUT_MS))
        end
    end

    if is_active and loader_state.bg_alpha > 0 then
        engine.execute_client_cmd('snd_mute_losefocus "0"')
        render.rect_filled(
            vec2_t(0, 0),
            vec2_t(screen.x, screen.y),
            color_t(LOADER_CONFIG.BG_COLOR[1], LOADER_CONFIG.BG_COLOR[2], LOADER_CONFIG.BG_COLOR[3], loader_state.bg_alpha), 0
        )
    end

    if loader_state.phase == "loading" then
        local bar_x = center_x - LOADER_CONFIG.BAR_WIDTH / 2
        local bar_y = center_y + LOADER_CONFIG.BAR_Y_OFFSET
        local real_progress = 0
        if loader_state.total_phrases > 0 then
            local loaded_commands = loader_state.current_phrase_index - 1
            real_progress = loaded_commands / loader_state.total_phrases
            if real_progress > 1 then real_progress = 1 end
            if real_progress < 0 then real_progress = 0 end
        end
        render.rect_filled(
            vec2_t(bar_x, bar_y),
            vec2_t(bar_x + LOADER_CONFIG.BAR_WIDTH, bar_y + LOADER_CONFIG.BAR_HEIGHT),
            color_t(0, 0, 0, 1), 2
        )
        render.rect(
            vec2_t(bar_x, bar_y),
            vec2_t(bar_x + LOADER_CONFIG.BAR_WIDTH, bar_y + LOADER_CONFIG.BAR_HEIGHT),
            color_t(40/255, 40/255, 40/255, 1), 2, 1
        )
        render.rect_filled(
            vec2_t(bar_x+2, bar_y+2),
            vec2_t((bar_x + LOADER_CONFIG.BAR_WIDTH * real_progress)-2, (bar_y + LOADER_CONFIG.BAR_HEIGHT)-2),
            color_t(LOADER_CONFIG.ACCENT_COLOR[1], LOADER_CONFIG.ACCENT_COLOR[2], LOADER_CONFIG.ACCENT_COLOR[3], 1), 2
        )
        local percent_text = 'Загрузка: '..math.floor(real_progress * 100).."%"
        local percent_size = render.calc_text_size(percent_text, slashloadfont)
        render.text(percent_text, slashloadfont,
            vec2_t(center_x - percent_size.x / 2, bar_y - 18),
            color_t(LOADER_CONFIG.ACCENT_COLOR[1], LOADER_CONFIG.ACCENT_COLOR[2], LOADER_CONFIG.ACCENT_COLOR[3], 0.8)
        )
        local log_start_y = center_y + LOADER_CONFIG.BAR_Y_OFFSET + LOADER_CONFIG.LOG_START_OFFSET
        for i = 1, 15 do
            local line = loader_state.log_lines[i]
            if line and line.text ~= "" then
                local line_width = render.calc_text_size(line.text, slashcmdfont)
                local line_x = center_x - line_width.x / 2
                local line_y = log_start_y + (i - 1) * LOADER_CONFIG.LINE_HEIGHT
                render.text(line.text, slashcmdfont,
                    vec2_t(line_x, line_y),
                    color_t(LOADER_CONFIG.TEXT_COLOR[1], LOADER_CONFIG.TEXT_COLOR[2], LOADER_CONFIG.TEXT_COLOR[3], line.alpha)
                )
            end
        end
    end

    if loader_state.phase == "final" or loader_state.show_final_message then
        local elapsed_time = current_time - loader_state.final_message_start_time
        if loader_state.text_y_offset < 0 then
            loader_state.text_y_offset = loader_state.text_y_offset + LOADER_CONFIG.TEXT_FLY_SPEED
            if loader_state.text_y_offset > 0 then loader_state.text_y_offset = 0 end
        end
        if elapsed_time >= LOADER_CONFIG.FINAL_SHOW_MS then
            loader_state.phase = "fading_out"
            loader_state.is_fading_out = true
            loader_state.bg_fade_start_time = current_time
            loader_state.showconsolefx = false
            loader_state.show_final_message = false
            clear_logs()
        else
            local logo_text = "KENSOHUB"
            local author_text = "Разработано: kelix.me / Универсальные скрипт"
            local final_fade_progress = math.min(1, elapsed_time / 500)
            local logo_size = render.calc_text_size(logo_text, slashfont)
            local author_size = render.calc_text_size(author_text, slashauthorfont)
            local logo_y = center_y - logo_size.y / 2 - 30 + loader_state.text_y_offset
            local version_y = center_y + 10 + loader_state.text_y_offset * 0.7
            local author_y = center_y - 5 + loader_state.text_y_offset * 0.5
            render.text(logo_text, slashfont,
                vec2_t(center_x - logo_size.x / 2, logo_y),
                color_t(LOADER_CONFIG.ACCENT_COLOR[1], LOADER_CONFIG.ACCENT_COLOR[2], LOADER_CONFIG.ACCENT_COLOR[3], final_fade_progress)
            )
            render.text(author_text, slashauthorfont,
                vec2_t(center_x - author_size.x / 2, author_y),
                color_t(150/255, 150/255, 150/255, 0.6 * final_fade_progress)
            )
            if loader_state.finate == 0 and final_fade_progress >= 0.5 then
                PlaySound(config.sounds.loader_final, 0.3)
                loader_state.finate = 1
            end
        end
        return
    end

    if loader_state.phase ~= "loading" then return end
    if not loader_state.showconsolefx then return end
    if loader_state.is_paused then
        local pause_elapsed = current_time - loader_state.pause_start_time
        if pause_elapsed >= LOADER_CONFIG.CMD_DELAY_MS then
            loader_state.is_paused = false
        end
    end
    local time_since_last_update = current_time - loader_state.last_update_time
    if time_since_last_update >= LOADER_CONFIG.CMD_DELAY_MS and not loader_state.is_paused then
        loader_state.last_update_time = current_time
        if loader_state.current_phrase_index <= loader_state.total_phrases then
            local new_line = terminal_phrases[loader_state.current_phrase_index]
            for i = 15, 2, -1 do
                if loader_state.log_lines[i-1] then
                    loader_state.log_lines[i].text = loader_state.log_lines[i-1].text
                    loader_state.log_lines[i].alpha = loader_state.log_lines[i-1].alpha
                end
            end
            loader_state.log_lines[1].text = new_line
            loader_state.log_lines[1].alpha = 1.0
            for i = 1, 15 do
                loader_state.log_lines[i].alpha = LOADER_CONFIG.LOG_ALPHAS[i]
            end
            PlaySound(config.sounds.loader_loads, 0.05)
            loader_state.current_phrase_index = loader_state.current_phrase_index + 1
        else
            loader_state.showconsolefx = false
            loader_state.show_final_message = true
            loader_state.phase = "final"
            loader_state.final_message_start_time = current_time
            loader_state.text_y_offset = -100
        end
    end
end

register_callback("paint", function()
    fxscreen()
end)

-- =================================================================================================
-- Аватар
-- =================================================================================================
function DrawAvatarFit(avatarcache, original_width, original_height, center_width, center_height, max_size)
    local scale = math.min(max_size / original_width, max_size / original_height)
    local size_width  = original_width  * scale
    local size_height = original_height * scale
    render.texture(
        avatarcache,
        vec2_t(center_width - size_width/2,  center_height - size_height/2),
        vec2_t(center_width + size_width/2,  center_height + size_height/2),
        0, 5
    )
end

render_preload = false

-- =================================================================================================
-- Шрифты для окна "Хостинг недоступен"
-- =================================================================================================
font_title  = render.setup_font(fontpatch2, 30, 055)
font_text   = render.setup_font(fontpatch2, 16, 055)
font_button = render.setup_font(fontpatch2, 18, 055)

local button_hovered    = false
local button_pressed    = false
local button_press_time = 0
local was_mouse_down    = false

register_callback("paint", function()
    if not loader_state.menu_was_open then 
        local screen        = render.screen_size()
        local size          = {width = 720, height = 445}
        local center_width  = screen.x / 2
        local center_height = screen.y / 2
        local win_left      = center_width  - (size.width  / 2)
        local win_top       = center_height - (size.height / 2)
        local win_right     = center_width  + (size.width  / 2)
        local win_bottom    = center_height + (size.height / 2)

        if not render_preload then
            avatarcache    = render.setup_texture('./nix/scripts/kensoLUA/images/loader/nanally.png')
            render_preload = true
        end

        -- Фон окна
        render.rect_filled(
            vec2_t(win_left, win_top),
            vec2_t(win_right, win_bottom),
            get_color('#0E0E0E'):color_t(), 0
        )

        -- Заголовок
        render.text('Хостинг недоступен', font_title,
            vec2_t(win_left + 30, win_top + 30),
            color_t(230/255, 80/255, 80/255, 1))

        -- ===== Текстовые блоки =====
        local text_left    = win_left + 30
        local text_start_y = win_top + 90
        local line_height  = 26

        render.text('Хостинг не доступен или отключён', font_text,
            vec2_t(text_left, text_start_y),
            color_t(230/255, 80/255, 80/255, 1))

        render.text('Свяжитесь с админом\nдля уточнения деталей', font_text,
            vec2_t(text_left, text_start_y + line_height),
            color_t(120/255, 120/255, 120/255, 1))

        local info_y = text_start_y + line_height * 4
        render.text('или проверьте новости', font_text,
            vec2_t(text_left, info_y),
            color_t(215/255, 254/255, 123/255, 1))

        -- ===== Аватарка (справа) =====
        local av_w, av_h = 300, 355
        DrawAvatarFit(
            avatarcache,
            av_w, av_h,
            win_right - av_w / 2,
            win_bottom - av_h / 2,
            av_h
        )

        -- ===== Кнопка снизу слева =====
        local btn_w, btn_h = 160, 40
        local btn_x     = win_left + 30
        local btn_y     = win_bottom - btn_h - 25
        local btn_right = btn_x + btn_w
        local btn_bottom= btn_y + btn_h

        -- ВАЖНО: клики игнорируются, если курсор в меню Nixware
        local outside_nixware = isCursorOutsideMenu()
        local mouse_down      = ffi.C.GetAsyncKeyState(0x01) ~= 0
        local mouse           = get_mouse_pos()

        button_hovered = outside_nixware and
            mouse.x >= btn_x and mouse.x <= btn_right and
            mouse.y >= btn_y and mouse.y <= btn_bottom

        -- Детект клика только ВНЕ меню Nixware
        if button_hovered and outside_nixware and mouse_down and not was_mouse_down then
            button_pressed    = true
            button_press_time = os.clock() * 1000
            PlaySound(config.sounds.click, 0.3)
            unload_script()
        end
        was_mouse_down = mouse_down

        if button_pressed and (os.clock() * 1000 - button_press_time) > 150 then
            button_pressed = false
        end

        -- Цвета кнопки
        local bg_color, border_color, text_color
        if button_pressed then
            bg_color     = color_t(215/255, 254/255, 123/255, 1)
            border_color = color_t(215/255, 254/255, 123/255, 1)
            text_color   = color_t(14/255, 14/255, 14/255, 1)
        elseif button_hovered then
            bg_color     = color_t(215/255, 254/255, 123/255, 0.15)
            border_color = color_t(215/255, 254/255, 123/255, 1)
            text_color   = color_t(215/255, 254/255, 123/255, 1)
        else
            bg_color     = color_t(215/255, 254/255, 123/255, 0.05)
            border_color = color_t(215/255, 254/255, 123/255, 0.6)
            text_color   = color_t(200/255, 200/255, 200/255, 1)
        end

        render.rect_filled(vec2_t(btn_x, btn_y), vec2_t(btn_right, btn_bottom), bg_color, 4)
        render.rect(vec2_t(btn_x, btn_y), vec2_t(btn_right, btn_bottom), border_color, 4, 1)

        local btn_label = 'Понятно'
        local text_w    = render.calc_text_size(btn_label, font_button).x
        local text_x    = btn_x + (btn_w - text_w) / 2
        local text_y    = btn_y + (btn_h - 18) / 2
        render.text(btn_label, font_button, vec2_t(text_x, text_y), text_color)

        -- Рамка окна
        render.rect(
            vec2_t(win_left, win_top),
            vec2_t(win_right, win_bottom),
            get_color('#D7FE7B'):color_t(), 0, 1
        )
    end
end)