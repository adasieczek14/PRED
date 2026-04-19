from bs4 import BeautifulSoup

with open("fctables_2024.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

print("Tables found:", len(soup.find_all("table")))
for i, table in enumerate(soup.find_all("table")):
    print(f"Table {i} rows:", len(table.find_all("tr")))
    if len(table.find_all("tr")) > 0:
        print("First row text:", table.find_all("tr")[0].text.strip()[:100])
        
print("Divs with class table:", len(soup.find_all("div", class_=lambda c: c and "table" in c)))
