import requests
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
}

def test_fetch():
    url = "https://pl.fctables.com/ranking-tfi/"
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response length: {len(response.text)}")
    with open("fctables_req.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    
if __name__ == "__main__":
    test_fetch()
