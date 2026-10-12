# Arena Frame setup page

A Web Serial page for configuring the ESP32-S3 frame over USB: WiFi, Are.na channel,
order, refresh interval, title/channel/dark-mode toggles. It drives MicroPython's raw
REPL to read and write `config.json` on the board, draw a block, or reset it.

Chrome or Edge on desktop only — Safari and Firefox have no Web Serial. The page needs
a secure context, so serve it over https (Vercel) or from localhost.

## Deploy

    npx vercel login        # once, opens a browser
    npx vercel --prod       # from this folder

## Local

    python3 -m http.server 8777    # then open http://localhost:8777

## Notes

- Nothing is stored by the page: the WiFi password goes straight to the board over USB.
- Only one program can hold the serial port, so close this tab before using `../mpr`.
- Connecting interrupts the frame's loop; reset the board to set it running again.
