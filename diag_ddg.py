"""Diagnostyczny skrypt: pobiera i wypisuje wszystkie href z DDG dla jednego meczu."""
import time, sys
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
opts = uc.ChromeOptions()
if os.path.exists(browser_path):
    opts.binary_location = browser_path
kwargs = {"options": opts, "use_subprocess": True}
if os.path.exists(driver_path):
    kwargs["driver_executable_path"] = driver_path

driver = uc.Chrome(**kwargs)
driver.get("https://lite.duckduckgo.com/lite/")
time.sleep(2)
search_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "q")))
search_input.clear()
search_input.send_keys("site:flashscore.pl Sochaux Quevilly")
search_input.submit()
time.sleep(2)

print("=== WSZYSTKIE LINKI NA STRONIE DDG ===")
links = driver.find_elements(By.TAG_NAME, "a")
for l in links:
    href = l.get_attribute("href") or ""
    text = l.text.strip()
    if href and "duckduckgo" not in href:
        print(f"  href={href!r}  text={text!r}")

print("=== ZRODLO STRONY (pierwsze 3000 znakow) ===")
print(driver.page_source[:3000])
driver.quit()
