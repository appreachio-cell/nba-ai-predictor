"""
debug_oddsportal.py — Dumps the page source so we can see what OddsPortal actually renders.
Run: python debug_oddsportal.py
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

try:
    driver.get("https://www.oddsportal.com/basketball/usa/nba/results/")
    time.sleep(6)

    src = driver.page_source

    # Save full source
    with open("oddsportal_debug.html", "w", encoding="utf-8") as f:
        f.write(src)
    print(f"Saved full page source → oddsportal_debug.html ({len(src)//1024}KB)")

    # Print first 3000 chars to see structure
    print("\n--- PAGE SOURCE SNIPPET ---")
    print(src[:3000])

    # Check what scripts exist
    from selenium.webdriver.common.by import By
    scripts = driver.find_elements(By.TAG_NAME, "script")
    print(f"\n--- SCRIPTS ({len(scripts)} total) ---")
    for s in scripts[:10]:
        sid = s.get_attribute("id")
        src_attr = s.get_attribute("src")
        print(f"  id={sid}  src={src_attr}")

finally:
    driver.quit()
