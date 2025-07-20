FROM selenium/standalone-chrome:4.15.0

USER root

RUN apt-get update && apt-get install -y python3 python3-pip python3-dev && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

ENV PYTHONUNBUFFERED=1
ENV RAILWAY_ENVIRONMENT=true
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV DISPLAY=:99

RUN google-chrome --version && chromedriver --version

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

RUN python3 -c "from selenium import webdriver; from selenium.webdriver.chrome.options import Options; options = Options(); options.add_argument('--headless'); options.add_argument('--no-sandbox'); driver = webdriver.Chrome(options=options); driver.get('data:text/html,<h1>Test OK</h1>'); driver.quit(); print('Selenium OK')"

COPY . .

RUN useradd -m railwayuser && chown -R railwayuser:railwayuser /app

USER railwayu