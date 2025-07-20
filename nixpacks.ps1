# nixpacks.toml - Configuration ALTERNATIVE pour Railway
[phases.setup]
# Approche mixte : nixpkgs + apt pour Chrome
nixPkgs = ["python311", "python311Packages.pip"]

# Installation Chrome via apt (plus fiable)
aptPkgs = [
    "wget",
    "gnupg", 
    "unzip",
    "curl",
    "xvfb",
    # Dépendances Chrome
    "libnss3",
    "libatk-bridge2.0-0", 
    "libdrm2",
    "libxcomposite1",
    "libxdamage1",
    "libxrandr2",
    "libgbm1",
    "libxss1",
    "libasound2"
]

[phases.build]
cmds = [
    # Installation Chrome et ChromeDriver via script
    "wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -",
    "echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' >> /etc/apt/sources.list.d/google-chrome.list",
    "apt-get update",
    "apt-get install -y google-chrome-stable",
    
    # Installation ChromeDriver
    "CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)",
    "wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip",
    "unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/",
    "chmod +x /usr/local/bin/chromedriver",
    
    # Vérification installation
    "which google-chrome-stable || echo 'Chrome installation failed'",
    "which chromedriver || echo 'ChromeDriver installation failed'", 
    "google-chrome-stable --version || echo 'Chrome not executable'",
    "chromedriver --version || echo 'ChromeDriver not executable'",
    
    # Installation Python dependencies
    "pip install -r requirements.txt"
]

[start]
cmd = "xvfb-run -a --server-args='-screen 0 1920x1080x24' uvicorn main:app --host 0.0.0.0 --port $PORT"

[variables]
CHROME_BIN = "/usr/bin/google-chrome-stable"
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
DISPLAY = ":99"
RAILWAY_ENVIRONMENT = "true"