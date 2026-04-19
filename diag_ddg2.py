"""Pełna diagnostyka DDG - pokazuje href ORAZ page_source z regexami."""
import time, sys, re, os
sys.stdout.reconfigure(encoding='utf-8')
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

for query in ["Sochaux Quevilly", "Partick Thistle Ross County"]:
    print(f"\n=== QUERY: {query} ===")
    driver.get("https://lite.duckduckgo.com/lite/")
    time.sleep(1.5)
    inp = WebDriverWait(driver, 5).until(lambda d: d.find_element(By.NAME, "q"))
    inp.clear()
    inp.send_keys(f"flashscore.pl/mecz {query}")
    inp.submit()
    time.sleep(2.5)
    
    print("--- LINKI (href) ---")
    for a in driver.find_elements(By.TAG_NAME, "a"):
        h = a.get_attribute("href") or ""
        t = a.text.strip()
        if h and "duckduckgo" not in h:
            print(f"  {h!r}  |  {t[:80]!r}")
    
    print("--- REGEX na page_source (flashscore) ---")
    src = driver.page_source
    all_fs = re.findall(r'flashscore[^\s"\'<>]{5,80}', src)
    for x in all_fs[:20]:
        print(f"  {x}")

driver.quit()
