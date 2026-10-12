# Arena Frame on an ESP32-S3

A port of [arena-frame](https://github.com/k-sdm/arena-frame) (Raspberry Pi) to an
ESP32-S3 driving a Pimoroni Inky Impression 7.3" Spectra 6 panel. It connects to WiFi,
pulls blocks from an Are.na channel, fits and dithers images to the panel's six inks,
and draws the block title and channel line beneath.

## Layout

    device/        MicroPython modules that live on the board
      inky.py      panel driver (SPI, full refresh ~29 s)
      image.py     fetch, JPEG decode, scale, Floyd-Steinberg dither, rotate
      render.py    portrait 480x800 canvas, text layout, overlay, rotation
      font.py      1bpp bitmap fonts built from ABC Areal
      arena.py     Are.na API v3 client
      wifi.py      station-mode connection
      main.py      scheduler loop (deployed as frame.py)
      main_boot.py launcher (deployed as main.py, runs on power-up)
      fonts/       generated bitmap fonts
    config-tool/   Web Serial setup page (Chrome/Edge) — configure over USB
    build_font.py  renders a TTF into the bitmap font format
    mpr            mpremote wrapper, finds the board automatically
    flash           esptool wrapper for firmware

## Wiring

| Inky header pin | Signal | ESP32-S3 |
|---|---|---|
| 19 | MOSI | GPIO 11 |
| 23 | SCLK | GPIO 12 |
| 24 | Chip select | GPIO 10 |
| 15 | Data/command | GPIO 9 |
| 13 | Reset | GPIO 8 |
| 11 | Busy | GPIO 7 |
| 2 / 1 / 6 | 5V / 3V3 / GND | 5V / 3V3 / GND |

MISO is unused. Avoid GPIO 26-37 (flash and octal PSRAM), 0/3/45/46 (strapping),
19/20 (USB), 43/44 (UART) and 38 (RGB LED).

## Firmware

MicroPython with a JPEG decoder: the prebuilt
[mp_jpeg](https://github.com/cnadler86/mp_jpeg) build for `ESP32_GENERIC_S3-SPIRAM_OCT`.
Flash it over the board's UART port (the native USB port will not enter download mode):

    ./flash firmware/firmware.bin

## Deploying the code

    ./mpr fs cp device/*.py :
    ./mpr fs cp device/main.py :frame.py
    ./mpr fs cp device/main_boot.py :main.py
    ./mpr fs mkdir fonts && ./mpr fs cp device/fonts/*.bin :fonts/

Then open `config-tool/index.html` in Chrome (over https or localhost) to set WiFi,
the channel and display options. Settings live in `config.json` on the board; position
in the channel is kept in `state.json`.

## Notes on the panel

This is the 2026 "AC waveform" Spectra 6 panel (EEPROM variant 26). A full refresh takes
about 29 s. Partial refresh via the 0x83 window register does not confine the waveform on
this revision — the whole panel cycles — so the frame uses full refreshes only.
