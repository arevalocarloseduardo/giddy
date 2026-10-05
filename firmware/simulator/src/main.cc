// Simulador de la pantalla de Giddy.
//
// Compila el lcd_display.cc REAL del firmware y lo dibuja en una ventana SDL
// de 240x240 (con zoom). Sirve para iterar la cara, los subtítulos y los
// estados sin flashear la placa, y para sacar capturas PNG en modo headless.
//
//   ./giddy_simulator                      ventana interactiva
//   ./giddy_simulator --script demo.txt    corre un guion (ver README)
//   ./giddy_simulator --headless --script demo.txt   sin ventana, solo PNGs

#include <lvgl.h>
#include <SDL2/SDL.h>
#include <src/drivers/sdl/lv_sdl_window.h>
#include <src/drivers/sdl/lv_sdl_mouse.h>
#define LODEPNG_NO_COMPILE_CPP
#include <src/libs/lodepng/lodepng.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "application.h"
#include "board.h"
#include "esp_log.h"
#include "giddy_display.h"
#include "lcd_display.h"
#include "lvgl_theme.h"

void sim_set_lvgl_display(lv_display_t* disp);

namespace fs = std::filesystem;

#define TAG "Sim"

static const int kWidth = 240;
static const int kHeight = 240;

// ---------------- GiddyDisplay sobre SDL ----------------
// Construye la GiddyDisplay real (la de la placa Touch-LCD-1.54, con su boot,
// sus "momentos" y sus timers). El constructor de SpiLcdDisplay pide la
// pantalla a lvgl_port_add_disp(), que en el simulador devuelve la ventana SDL.
class SimDisplay : public GiddyDisplay {
public:
    SimDisplay()
        : GiddyDisplay(nullptr, nullptr, kWidth, kHeight, 0, 0, false, false, false) {}
    using GiddyDisplay::PlayFarewellSequence;
    using GiddyDisplay::PlaySleepSequence;
    using GiddyDisplay::PlayWakeSequence;
    using GiddyDisplay::SetFaceRotation;
};

// ---------------- Avatar: cargar GIFs/PNGs de un directorio ----------------
static std::vector<std::string> g_emotions;

static bool LoadEmojiDir(const std::string& dir) {
    if (!fs::is_directory(dir)) return false;
    auto collection = std::make_shared<EmojiCollection>();
    int count = 0;
    for (auto& entry : fs::directory_iterator(dir)) {
        if (!entry.is_regular_file()) continue;
        auto ext = entry.path().extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (ext != ".gif" && ext != ".png") continue;
        std::ifstream f(entry.path(), std::ios::binary);
        std::vector<char> bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        if (bytes.empty()) continue;
        void* buf = malloc(bytes.size());
        memcpy(buf, bytes.data(), bytes.size());
        auto name = entry.path().stem().string();
        collection->AddEmoji(name, new LvglRawImage(buf, bytes.size()));
        g_emotions.push_back(name);
        count++;
    }
    std::sort(g_emotions.begin(), g_emotions.end());
    auto& tm = LvglThemeManager::GetInstance();
    if (auto t = tm.GetTheme("light")) t->set_emoji_collection(collection);
    if (auto t = tm.GetTheme("dark")) t->set_emoji_collection(collection);
    ESP_LOGI(TAG, "Avatar: %d caras desde %s", count, dir.c_str());
    return count > 0;
}

// ---------------- Captura PNG ----------------
static bool Screenshot(const std::string& path) {
    lv_draw_buf_t* buf = lv_snapshot_take(lv_screen_active(), LV_COLOR_FORMAT_ARGB8888);
    if (!buf) {
        ESP_LOGE(TAG, "snapshot falló");
        return false;
    }
    uint32_t w = buf->header.w, h = buf->header.h, stride = buf->header.stride;
    std::vector<unsigned char> rgba(w * h * 4);
    for (uint32_t y = 0; y < h; y++) {
        const uint8_t* src = buf->data + y * stride;
        unsigned char* dst = rgba.data() + y * w * 4;
        for (uint32_t x = 0; x < w; x++) {
            // LVGL ARGB8888 en memoria = B,G,R,A  ->  PNG quiere R,G,B,A
            dst[0] = src[2];
            dst[1] = src[1];
            dst[2] = src[0];
            dst[3] = 0xFF;
            src += 4;
            dst += 4;
        }
    }
    lv_draw_buf_destroy(buf);
    // El lodepng de LVGL usa lv_fs para archivos (sin driver acá): codificamos
    // en memoria y escribimos con stdio.
    unsigned char* png = nullptr;
    size_t png_size = 0;
    unsigned err = lodepng_encode32(&png, &png_size, rgba.data(), w, h);
    if (err) {
        ESP_LOGE(TAG, "PNG %s: %s", path.c_str(), lodepng_error_text(err));
        return false;
    }
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) {
        ESP_LOGE(TAG, "no puedo escribir %s", path.c_str());
        lv_free(png);
        return false;
    }
    fwrite(png, 1, png_size, f);
    fclose(f);
    lv_free(png);
    printf("captura -> %s\n", path.c_str());
    return true;
}

// ---------------- Guion ----------------
struct Step {
    std::string cmd;
    std::string arg;
};

static std::deque<Step> g_script;
static uint32_t g_wait_until = 0;
static bool g_quit = false;
static SimDisplay* g_display = nullptr;

static const char* kSampleUser = "Giddy, ¿qué hora es en Buenos Aires?";
static const char* kSampleBot = "Son las tres y media de la tarde. ¿Querés que te recuerde algo?";
static const char* kSampleLong =
    "Mirá, la receta lleva dos tazas de harina, una de azúcar, tres huevos y manteca derretida. "
    "Se mezcla todo y va al horno cuarenta minutos.";

static void SetState(const std::string& name) {
    static const std::map<std::string, DeviceState> states = {
        {"idle", kDeviceStateIdle},           {"listening", kDeviceStateListening},
        {"speaking", kDeviceStateSpeaking},   {"connecting", kDeviceStateConnecting},
        {"starting", kDeviceStateStarting},   {"upgrading", kDeviceStateUpgrading},
    };
    auto it = states.find(name);
    if (it == states.end()) {
        ESP_LOGW(TAG, "estado desconocido: %s", name.c_str());
        return;
    }
    Application::GetInstance().SetDeviceState(it->second);
}

static void RunStep(const Step& s) {
    if (s.cmd == "emotion") {
        g_display->SetEmotion(s.arg.c_str());
    } else if (s.cmd == "user") {
        g_display->SetChatMessage("user", s.arg.empty() ? kSampleUser : s.arg.c_str());
    } else if (s.cmd == "bot" || s.cmd == "assistant") {
        g_display->SetChatMessage("assistant", s.arg.empty() ? kSampleBot : s.arg.c_str());
    } else if (s.cmd == "system") {
        g_display->SetChatMessage("system", s.arg.c_str());
    } else if (s.cmd == "clear") {
        g_display->ClearChatMessages();
    } else if (s.cmd == "status") {
        g_display->SetStatus(s.arg.c_str());
    } else if (s.cmd == "notify") {
        g_display->ShowNotification(s.arg.c_str());
    } else if (s.cmd == "state") {
        SetState(s.arg);
        // En la placa, Application::SetDeviceState llama a SetStatus(), y ahí
        // GiddyDisplay decide la cara de actividad (listening/speaking/...).
        g_display->SetStatus(s.arg.c_str());
    } else if (s.cmd == "sleep") {
        g_display->SetPowerSaveMode(true);
    } else if (s.cmd == "wake") {
        g_display->SetPowerSaveMode(false);
    } else if (s.cmd == "farewell") {
        g_display->PlayFarewellSequence();
    } else if (s.cmd == "rotate") {
        g_display->SetFaceRotation(atoi(s.arg.c_str()));
    } else if (s.cmd == "battery") {
        int lvl = atoi(s.arg.c_str());
        Board::GetInstance().SetBattery(lvl, s.arg.find("charging") != std::string::npos);
        g_display->UpdateStatusBar(true);
    } else if (s.cmd == "wait") {
        g_wait_until = SDL_GetTicks() + (uint32_t)atoi(s.arg.c_str());
    } else if (s.cmd == "shot") {
        Screenshot(s.arg.empty() ? "giddy.png" : s.arg);
    } else if (s.cmd == "quit") {
        g_quit = true;
    } else if (!s.cmd.empty() && s.cmd[0] != '#') {
        ESP_LOGW(TAG, "comando desconocido en el guion: %s", s.cmd.c_str());
    }
}

static bool LoadScript(const std::string& path) {
    std::ifstream f(path);
    if (!f) {
        fprintf(stderr, "no puedo abrir el guion %s\n", path.c_str());
        return false;
    }
    std::string line;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == '#') continue;
        auto sp = line.find(' ');
        Step s;
        s.cmd = line.substr(0, sp);
        if (sp != std::string::npos) s.arg = line.substr(sp + 1);
        g_script.push_back(s);
    }
    return true;
}

static void PumpScript() {
    while (!g_script.empty() && SDL_GetTicks() >= g_wait_until) {
        Step s = g_script.front();
        g_script.pop_front();
        RunStep(s);
    }
}

// ---------------- Teclado (hotkeys del simulador) ----------------
static int g_emotion_idx = 0;
static int g_shot_counter = 0;
static std::deque<Step> g_key_queue;  // se procesa en el hilo principal

static void PrintHelp() {
    printf(
        "\nGiddy simulator — teclas:\n"
        "  ← / →       cara anterior / siguiente (se imprime el nombre)\n"
        "  1..9        caras 1..9 de la lista\n"
        "  u           subtítulo del usuario      b  subtítulo del bot\n"
        "  l           texto largo (marquee)      c  limpiar subtítulo\n"
        "  i / e / h   estado idle / escuchando / hablando\n"
        "  z           dormir / despertar         f  despedida (goodnight)\n"
        "  r           rotar la cara 90°          n  notificación de prueba\n"
        "  s           captura giddy-N.png        q / Esc  salir\n\n");
    printf("Caras disponibles (%zu):", g_emotions.size());
    for (size_t i = 0; i < g_emotions.size(); i++) printf(" %zu=%s", i + 1, g_emotions[i].c_str());
    printf("\n\n");
}

static int EventWatch(void*, SDL_Event* ev) {
    if (ev->type == SDL_QUIT) {
        g_quit = true;
        return 0;
    }
    if (ev->type != SDL_KEYDOWN) return 0;
    SDL_Keycode k = ev->key.keysym.sym;
    auto emo = [](int idx) {
        if (g_emotions.empty()) return;
        g_emotion_idx = ((idx % (int)g_emotions.size()) + (int)g_emotions.size()) % (int)g_emotions.size();
        printf("cara: %s\n", g_emotions[g_emotion_idx].c_str());
        g_key_queue.push_back({"emotion", g_emotions[g_emotion_idx]});
    };
    switch (k) {
        case SDLK_ESCAPE:
        case SDLK_q: g_quit = true; break;
        case SDLK_LEFT: emo(g_emotion_idx - 1); break;
        case SDLK_RIGHT: emo(g_emotion_idx + 1); break;
        case SDLK_u: g_key_queue.push_back({"user", kSampleUser}); break;
        case SDLK_b: g_key_queue.push_back({"bot", kSampleBot}); break;
        case SDLK_l: g_key_queue.push_back({"bot", kSampleLong}); break;
        case SDLK_c: g_key_queue.push_back({"clear", ""}); break;
        case SDLK_i: g_key_queue.push_back({"state", "idle"}); break;
        case SDLK_e: g_key_queue.push_back({"state", "listening"}); break;
        case SDLK_h: g_key_queue.push_back({"state", "speaking"}); break;
        case SDLK_z: {
            static bool asleep = false;
            asleep = !asleep;
            g_key_queue.push_back({asleep ? "sleep" : "wake", ""});
            break;
        }
        case SDLK_f: g_key_queue.push_back({"farewell", ""}); break;
        case SDLK_r: {
            static int rot = 0;
            rot = (rot + 90) % 360;
            g_key_queue.push_back({"rotate", std::to_string(rot)});
            break;
        }
        case SDLK_n: g_key_queue.push_back({"notify", "Modo silencioso"}); break;
        case SDLK_s: {
            char name[64];
            snprintf(name, sizeof(name), "giddy-%d.png", ++g_shot_counter);
            g_key_queue.push_back({"shot", name});
            break;
        }
        default:
            if (k >= SDLK_1 && k <= SDLK_9) emo(k - SDLK_1);
            break;
    }
    return 0;
}

// ---------------- main ----------------
static void Usage(const char* argv0) {
    printf(
        "Uso: %s [--headless] [--script FILE] [--emoji-dir DIR] [--zoom N] [--emotion NAME]\n"
        "          [--run-ms N] [--shot FILE.png] [--quiet]\n",
        argv0);
}

int main(int argc, char** argv) {
    std::string script, emoji_dir, shot;
    std::string emotion = "neutral";
    float zoom = 2.0f;
    bool headless = false;
    int run_ms = -1;

    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto next = [&](std::string& out) {
            if (i + 1 >= argc) { Usage(argv[0]); exit(2); }
            out = argv[++i];
        };
        std::string v;
        if (a == "--headless") headless = true;
        else if (a == "--script") next(script);
        else if (a == "--emoji-dir") next(emoji_dir);
        else if (a == "--zoom") { next(v); zoom = (float)atof(v.c_str()); }
        else if (a == "--emotion") next(emotion);
        else if (a == "--run-ms") { next(v); run_ms = atoi(v.c_str()); }
        else if (a == "--shot") next(shot);
        else if (a == "--quiet") sim_log_set_level(ESP_LOG_WARN);
        else if (a == "--help" || a == "-h") { Usage(argv[0]); return 0; }
        else { Usage(argv[0]); return 2; }
    }

    if (headless) {
        setenv("SDL_VIDEODRIVER", "dummy", 1);
        setenv("SDL_AUDIODRIVER", "dummy", 1);
        if (run_ms < 0 && script.empty() && shot.empty()) run_ms = 1000;
    }

    lv_init();
    lv_tick_set_cb([]() -> uint32_t { return SDL_GetTicks(); });
    lv_delay_set_cb([](uint32_t ms) { SDL_Delay(ms); });

    lv_display_t* disp = lv_sdl_window_create(kWidth, kHeight);
    if (!disp) {
        fprintf(stderr, "no pude crear la ventana SDL\n");
        return 1;
    }
    lv_sdl_window_set_title(disp, "Giddy 240x240");
    if (!headless) lv_sdl_window_set_zoom(disp, zoom);
    lv_sdl_mouse_create();
    SDL_AddEventWatch(EventWatch, nullptr);

    // El display real del firmware
    sim_set_lvgl_display(disp);
    g_display = new SimDisplay();
    Board::GetInstance().SetDisplay(g_display);

    // Avatar
    bool loaded = false;
    if (!emoji_dir.empty()) loaded = LoadEmojiDir(emoji_dir);
    if (!loaded) {
        std::string dirs = SIM_EMOJI_DIRS;
        std::stringstream ss(dirs);
        std::string d;
        while (!loaded && std::getline(ss, d, '|')) loaded = LoadEmojiDir(d);
    }
    if (!loaded) ESP_LOGW(TAG, "sin GIFs del avatar: se usarán los íconos de fuente");

    g_display->SetupUI();  // GiddyDisplay arranca con su secuencia de boot
    if (emotion != "neutral") g_display->SetEmotion(emotion.c_str());
    auto it = std::find(g_emotions.begin(), g_emotions.end(), emotion);
    if (it != g_emotions.end()) g_emotion_idx = (int)(it - g_emotions.begin());

    if (!script.empty() && !LoadScript(script)) return 1;
    if (!shot.empty()) {
        // --shot sin guion: espera un poco a que el GIF arranque y captura
        g_script.push_back({"wait", std::to_string(run_ms > 0 ? run_ms : 600)});
        g_script.push_back({"shot", shot});
        g_script.push_back({"quit", ""});
    }
    if (!headless) PrintHelp();

    uint32_t start = SDL_GetTicks();
    while (!g_quit) {
        uint32_t sleep_ms = lv_timer_handler();
        PumpScript();
        while (!g_key_queue.empty()) {
            RunStep(g_key_queue.front());
            g_key_queue.pop_front();
        }
        if (run_ms >= 0 && shot.empty() && SDL_GetTicks() - start >= (uint32_t)run_ms && g_script.empty()) break;
        if (headless && g_script.empty() && shot.empty() && run_ms < 0) break;
        SDL_Delay(std::min<uint32_t>(sleep_ms, 10));
    }
    return 0;
}
