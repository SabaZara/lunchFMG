LUNCH kiosk scan tester (standalone)
====================================

Test card scans on the kiosk WITHOUT a USB card reader.

HOW TO USE
----------
1. Make sure the kiosk app is running (start.bat has been launched and the
   scan screen works at http://127.0.0.1:8000/).
2. Double-click  run-tester.bat
3. A small window opens. Type or paste a card ID, then press Enter (or click
   "Scan"). You will see:
       green  "ნებადართულია"  = allowed (meal recorded)
       red    "უარყოფილია"    = denied  (with the Georgian reason)
4. Scanning the same card again the same day shows
   "დღეს უკვე ნაჭამია" (already eaten today).

NOTES
-----
- A successful scan records a REAL meal for today, exactly like a real tap.
- If the app runs on a different port, change the PORT box (default 8000).
- Requirements: Python 3.x (the python.org install already on the kiosk).
  No project, no venv, no pip needed. tkinter (included with python.org) is used
  for the window.
- If nothing opens or you see "connection error", the kiosk app is not running:
  launch start.bat first.
