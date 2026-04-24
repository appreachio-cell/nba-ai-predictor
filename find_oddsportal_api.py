"""
find_oddsportal_api.py — Intercepts network requests to find OddsPortal's data API.
Run: python find_oddsportal_api.py
"""
import time, json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120")

# Enable network logging
opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

try:
    print("Loading OddsPortal...")
    driver.get("https://www.oddsportal.com/basketball/usa/nba/results/")
    time.sleep(8)  # wait for AJAX

    # Grab all network requests
    logs = driver.get_log("performance")
    print(f"\nTotal network events: {len(logs)}")

    api_calls = []
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg["method"] == "Network.requestWillBeSent":
                url = msg["params"]["request"]["url"]
                if any(x in url for x in ["api", "feed", "data", "json", "ajax", "sport", "nba", "event"]):
                    api_calls.append(url)
        except:
            continue

    print(f"\nInteresting API calls ({len(api_calls)}):")
    for u in api_calls:
        print(f"  {u}")

    # Also try waiting longer and check page text
    time.sleep(5)
    body = driver.find_element(By.TAG_NAME, "body").text
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    print(f"\nPage text ({len(lines)} lines):")
    for l in lines[:60]:
        print(f"  {l}")

finally:
    driver.quit()
