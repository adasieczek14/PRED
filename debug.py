import time
import undetected_chromedriver as uc

driver = uc.Chrome()
driver.get("https://www.flashscore.pl/")
time.sleep(5)
matches = driver.find_elements("css selector", "div.event__match")
print("FOUND:", len(matches))
if matches:
    print("HTML:", matches[0].get_attribute("outerHTML"))
driver.quit()
