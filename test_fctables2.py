import os
import time
import undetected_chromedriver as my_uc
from selenium_stealth import stealth

def setup_driver():
    base_dir = os.path.dirname(os.path.abspath("C:/Users/admin/Desktop/PRACA INZYNIERSKA/KOD SCRAPER/flashscore_superbet.py"))

    browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
    if not os.path.exists(browser_path):
        browser_path = os.path.join(base_dir, "chrome-win64", "chrome-win64", "chrome.exe")

    driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
    if not os.path.exists(driver_path):
        driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver-win64", "chromedriver.exe")

    opts = my_uc.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--no-first-run")

    if os.path.exists(browser_path):
        opts.binary_location = browser_path

    kwargs = {"options": opts, "use_subprocess": True}
    if os.path.exists(driver_path):
        kwargs["driver_executable_path"] = driver_path
        if os.path.exists(browser_path):
            kwargs["browser_executable_path"] = browser_path

    try:
        driver = my_uc.Chrome(**kwargs)
    except TypeError:
        if "browser_executable_path" in kwargs:
            del kwargs["browser_executable_path"]
        driver = my_uc.Chrome(**kwargs)

    stealth(
        driver,
        languages=["pl-PL", "pl"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True
    )
    
    return driver

def main():
    driver = setup_driver()
    # Test specific date URL
    driver.get("https://pl.fctables.com/ranking-tfi/2026-03-07/")
    time.sleep(5)
    
    with open("fctables_2026.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    driver.quit()

if __name__ == "__main__":
    main()
