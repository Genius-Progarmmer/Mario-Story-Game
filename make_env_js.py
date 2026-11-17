"""Turns the private ".env" into "env.js", which web.html loads to know the debug password.

    python make_env_js.py

Run it again whenever you change ".env". "env.js" is in .gitignore too.
WARNING: a web page runs in the browser, so anyone who can open your page (or env.js) can read the password.
That is fine for debugging on your own computer. NEVER upload env.js to a public website.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mario_game"))
from debug_mode import read_env_file

password = read_env_file(os.path.join(HERE, ".env")).get("DEBUG_PASSWORD", "")
target = os.path.join(HERE, "env.js")
if not password or password == "change_me":
    if os.path.exists(target): os.remove(target)
    print('No real DEBUG_PASSWORD in .env: env.js was removed, so the web game has no DEBUG button.')
else:
    with open(target, "w", encoding="utf-8") as f:
        f.write("// Made by make_env_js.py from .env - private, in .gitignore, do not upload.\n")
        f.write("window.DEBUG_PASSWORD = " + json.dumps(password) + ";\n")
    print("env.js written: the DEBUG button will show in web.html.")
