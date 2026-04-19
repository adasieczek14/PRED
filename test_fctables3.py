import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import time

def main():
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
    driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    
    if os.path.exists(browser_path):
        options.binary_location = browser_path
        
    kwargs = {"options": options, "use_subprocess": True}
    if os.path.exists(driver_path):
        kwargs["driver_executable_path"] = driver_path
        if os.path.exists(browser_path):
            kwargs["browser_executable_path"] = browser_path
            
    try:
        driver = uc.Chrome(**kwargs)
    except TypeError:
        if "browser_executable_path" in kwargs:
            del kwargs["browser_executable_path"]
        driver = uc.Chrome(**kwargs)

    stealth(
        driver,
        languages=["pl-PL", "pl"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True
    )
    
    print("Navigating to URL...")
    driver.get("https://pl.fctables.com/ranking-tfi/2026-03-07/")
    time.sleep(3)
    
    # Accept cookies
    try:
        print("Waiting for cookie banner...")
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
        print("Clicked accept cookies")
        time.sleep(2)
    except Exception as e:
        print("No cookie banner found or could not click:", type(e).__name__)
        
    print("Saving screenshot before scrolling...")
    driver.save_screenshot("screenshot_before.png")
    
    # Scroll down to load lazy elements
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
    time.sleep(2)
    
    print("Saving screenshot after scrolling...")
    driver.save_screenshot("screenshot_after.png")
    
    with open("fctables_loaded.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    driver.quit()
    print("Done")

if __name__ == "__main__":
    main()
