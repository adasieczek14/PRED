import undetected_chromedriver as uc
import time

def main():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    driver = uc.Chrome(options=options)
    driver.get("https://pl.fctables.com/ranking-tfi/")
    time.sleep(5)
    
    html = driver.page_source
    with open("fctables_test.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    driver.quit()

if __name__ == "__main__":
    main()
