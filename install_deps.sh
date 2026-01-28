#!/bin/bash
#
# install_deps.sh - Install dependencies for thermo-cli
# For Raspberry Pi OS (Debian-based systems)
#

set -e

echo ""

# Check if running on Raspberry Pi or Debian-based system
if [ ! -f /etc/debian_version ]; then
    echo "Warning: This script is designed for Debian-based systems (Raspberry Pi OS)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update package list
echo "[1/4] Updating package list..."
sudo apt update

# Install libyaml development library
echo ""
echo "[2/4] Installing libyaml-dev..."
sudo apt install -y libyaml-dev

# Check for daqhats library
echo ""
echo "[3/4] Checking for daqhats library..."
if ldconfig -p | grep -q libdaqhats; then
    echo "✓ libdaqhats is already installed"
else
    echo "⚠ libdaqhats not found!"
    echo ""
    echo "The MCC DAQ HAT library is required but not installed."
    echo "Installing from: https://github.com/mccdaq/daqhats"
    echo ""
    
    # Clone daqhats if not exists
    if [ ! -d "daqhats" ]; then
        echo "Cloning daqhats repository..."
        git clone https://github.com/mccdaq/daqhats.git
    else
        echo "Using existing daqhats directory"
    fi
    
    # Install daqhats
    echo "Installing daqhats library (this may take a few minutes)..."
    cd daqhats
    sudo ./install.sh
    cd ..
    
    echo "✓ libdaqhats installed successfully"
fi

# cJSON is vendored, no need to install
echo ""
echo "✓ cJSON is vendored (no installation needed)"

# Install Python dependencies
echo ""
echo "[4/4] Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    # Check if virtual environment exists
    if [ -d "$HOME/tt_env" ]; then
        echo "Activating Python virtual environment at ~/tt_env..."
        source "$HOME/tt_env/bin/activate"
        
        echo "Installing Python packages from requirements.txt..."
        pip install -r requirements.txt
        
        echo "✓ Python dependencies installed successfully"
    else
        echo "⚠ Virtual environment not found at ~/tt_env"
        echo "Creating virtual environment..."
        python3 -m venv "$HOME/tt_env"
        
        echo "Activating virtual environment..."
        source "$HOME/tt_env/bin/activate"
        
        echo "Installing Python packages from requirements.txt..."
        pip install -r requirements.txt
        
        echo "✓ Virtual environment created and dependencies installed"
    fi
else
    echo "⚠ requirements.txt not found, skipping Python dependencies"
fi

echo ""
echo "You can now build thermo-cli:"
echo "  make"
echo ""
echo "To install system-wide:"
echo "  sudo make install"
echo ""
echo "For Python scripts (monitor.py), activate the virtual environment:"
echo "  source ~/tt_env/bin/activate"
echo ""
