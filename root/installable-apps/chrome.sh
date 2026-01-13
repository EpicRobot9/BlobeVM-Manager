set -e
echo "**** install chrome ****"
export DEBIAN_FRONTEND=noninteractive
apt-get update || true
apt-get install -y --no-install-recommends wget gnupg ca-certificates curl || true
# Install common runtime libraries Chrome needs so it doesn't crash on startup
apt-get install -y --no-install-recommends libnss3 lsb-release libatk1.0-0 libatk-bridge2.0-0 libxss1 libasound2 libx11-6 libx11-xcb1 libdbus-1-3 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxtst6 libc6 libcairo2 fonts-liberation || true
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/google-chrome.gpg ]]; then
	curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
fi
chmod a+r /etc/apt/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update || true
# First attempt
if ! apt-get install -y google-chrome-stable; then
	echo "Retrying chrome install after fixing dependencies..."
	apt-get -f install -y || true
	apt-get install -y google-chrome-stable || {
		echo "Chrome installation still failing; attempting final fix-broken pass" >&2
		apt --fix-broken install -y || true
		apt-get install -y google-chrome-stable
	}
fi

# Ensure chrome-sandbox is owned by root and setuid where it exists so Chrome's sandbox can work
if [ -f /opt/google/chrome/chrome-sandbox ]; then
	chown root:root /opt/google/chrome/chrome-sandbox || true
	chmod 4755 /opt/google/chrome/chrome-sandbox || true
fi

echo "Chrome install done."
