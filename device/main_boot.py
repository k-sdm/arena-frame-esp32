"""Runs on power-up. Interrupt (Ctrl-C) within a few seconds for the REPL."""
import time

print("Arena Frame starting - Ctrl-C now for the REPL")
time.sleep(4)
import frame
frame.main()
