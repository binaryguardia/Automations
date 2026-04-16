#!/bin/bash

set -e  # stop on error

echo "🚀 Starting setup..."

# -------------------------------
# 1. Create & activate virtualenv
# -------------------------------
echo "📦 Creating virtual environment..."
python3 -m venv venv

echo "⚡ Activating virtual environment..."
source venv/bin/activate

# -------------------------------
# 2. Install requirements
# -------------------------------
echo "📚 Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# -------------------------------
# 3. Remove Chromium (if exists)
# -------------------------------
echo "🧹 Removing Chromium browser..."
sudo apt-get remove -y chromium-browser chromium || true
sudo apt-get purge -y chromium-browser chromium || true

# -------------------------------
# 4. Install Google Chrome (official)
# -------------------------------
echo "🌐 Downloading Google Chrome..."
wget -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

echo "📥 Installing Google Chrome..."
sudo dpkg -i google-chrome.deb || sudo apt-get install -f -y

# Cleanup
rm -f google-chrome.deb

# -------------------------------
# 5. Start Python server
# -------------------------------
echo "🖥️ Starting Python server..."
python server.py &

# Give server time to start
sleep 3

# -------------------------------
# 6. Open in Firefox
# -------------------------------
echo "🌍 Opening in Firefox..."
firefox http://localhost:5000 &

echo "✅ Done!"
