#!/usr/bin/env bash
# install_vampire.sh — clone, patch, build Vampire, and point MATP at it.
#
# WHY THE PATCH: Vampire's current master branch has a real upstream bug on
# newer GCC (13+). Saturation/LRS.hpp uses unique_ptr<ofstream>/<ifstream>
# but only #includes <iosfwd> (forward declarations), not <fstream> (full
# definitions). Newer GCC needs the complete type at the point a unique_ptr's
# destructor is instantiated, and fails to compile without this one-line fix.
#
# EDIT THESE TWO PATHS if your setup differs:
MATP_DIR="$HOME/matp_baseline"
VAMPIRE_DIR="$HOME/vampire"

set -e  # stop on first real error, don't silently continue

echo ">>> Step 1: clone Vampire"
if [ -d "$VAMPIRE_DIR" ]; then
    echo "    $VAMPIRE_DIR already exists, skipping clone"
else
    git clone https://github.com/vprover/vampire.git "$VAMPIRE_DIR"
fi
cd "$VAMPIRE_DIR"
git submodule update --init --recursive

echo ">>> Step 2: check for a C++ compiler (needed, no sudo required if already present)"
if ! command -v gcc &> /dev/null || ! command -v g++ &> /dev/null; then
    echo "    ERROR: gcc/g++ not found. Install via your system's package manager"
    echo "    (needs sudo) or ask an admin -- this script can't install a compiler."
    exit 1
fi
echo "    Found: $(gcc --version | head -1)"

echo ">>> Step 3: check for cmake, install via pip if missing (no sudo needed)"
if ! command -v cmake &> /dev/null; then
    pip install cmake --quiet
fi
echo "    Found: $(cmake --version | head -1)"

echo ">>> Step 4: apply the LRS.hpp fstream fix (skips if already applied)"
if grep -q "#include <fstream>" Saturation/LRS.hpp; then
    echo "    Already patched, skipping"
else
    sed -i '/#include <iosfwd>/a #include <fstream>' Saturation/LRS.hpp
    echo "    Patched Saturation/LRS.hpp"
fi

echo ">>> Step 5: build (this is the slow part -- can take 10-30+ minutes)"
cmake -Bbuild -H. -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

echo ">>> Step 6: confirm the binary exists"
VAMPIRE_BIN=$(find "$VAMPIRE_DIR/build" -maxdepth 1 -name "vampire" -type f)
if [ -z "$VAMPIRE_BIN" ]; then
    echo "    ERROR: build finished but no 'vampire' binary found in $VAMPIRE_DIR/build"
    exit 1
fi
echo "    Built: $VAMPIRE_BIN"

echo ">>> Step 7: point MATP at the new binary"
CONSTANT_FILE="$MATP_DIR/ProcessAgent/constant/constant.py"
if [ ! -f "$CONSTANT_FILE" ]; then
    echo "    WARNING: $CONSTANT_FILE not found -- skipping this step."
    echo "    Manually set VAMPIRE_BIN_PATH = \"$VAMPIRE_BIN\" in MATP's constants file."
else
    sed -i "s#VAMPIRE_BIN_PATH = \".*\"#VAMPIRE_BIN_PATH = \"$VAMPIRE_BIN\"#" "$CONSTANT_FILE"
    echo "    Updated: $(grep VAMPIRE_BIN_PATH "$CONSTANT_FILE")"
fi

echo ">>> Done. Vampire is built and wired into MATP."