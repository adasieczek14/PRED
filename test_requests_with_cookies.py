import undetected_chromedriver as uc
from selenium_stealth import stealth
import requests
import time
import os

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
    driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--headless=new")
    
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
    
    print("Navigating to initial URL via Selenium...")
    driver.get("https://pl.fctables.com/ranking-tfi/")
    time.sleep(5)
    
    # Get cookies and user agent
    selenium_cookies = driver.get_cookies()
    user_agent = driver.execute_script("return navigator.userAgent;")
    
    driver.quit()
    
    print("Using requests session...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.5",
        "Referer": "https://pl.fctables.com/"
    })
    
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
        
    print("Fetching another date via requests...")
    resp = session.get("https://pl.fctables.com/ranking-tfi/2026-03-06/")
    print("Status code:", resp.status_code)
    
    if resp.status_code == 200:
        if "table-responsive" in resp.text or "stage-table" in resp.text:
            print("SUCCESS! Data found in response.")
        else:
            print("Response 200, but table not found (might be Cloudflare challenge).")
            with open("fctables_requests_failed.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
    else:
        print("Failed with status code:", resp.status_code)

if __name__ == "__main__":
    main()
