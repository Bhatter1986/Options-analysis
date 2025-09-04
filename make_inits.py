# make_inits.py
import os

paths = [
    "App/sudarshan",
    "App/sudarshan/api",
    "App/sudarshan/blades",
    "App/sudarshan/engine",
]

for path in paths:
    os.makedirs(path, exist_ok=True)
    init_file = os.path.join(path, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("# package init\n")
        print(f"Created: {init_file}")
    else:
        print(f"Already exists: {init_file}")


