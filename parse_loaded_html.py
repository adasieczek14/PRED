from bs4 import BeautifulSoup
import json

def parse_html():
    with open("fctables_loaded.html", "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        
    print("Looking for tables...")
    # Typically fctables uses divs for rows,e.g., div.table, or table tags
    # Let's just find the first team name we see in the screenshot: "San Giovanni"
    
    elem = soup.find(text=lambda t: t and "San Giovanni" in t)
    if elem:
        print("Found 'San Giovanni', tracing up to row...")
        row = elem.find_parent("tr")
        if not row:
            row = elem.find_parent("div", class_=lambda c: c and "row" in c)
            if not row:
                row = elem.find_parent(["div", "li"]) # generic fallback
        
        print("Row HTML tag:", row.name if row else "None")
        if row:
            print("Row classes:", row.get("class"))
            
            # Let's print all text in this row
            cells = []
            if row.name == 'tr':
                for td in row.find_all(['td', 'th']):
                    cells.append(td.get_text(strip=True))
            else:
                for child in row.find_all(recursive=False):
                    cells.append(child.get_text(strip=True))
            
            print("Row data:", cells)
            
            # Find the parent table
            table = row.find_parent("table")
            if table:
                print("Parent table found. Classes:", table.get("class"))
                # let's get headers
                headers = []
                for th in table.find_all('th'):
                    headers.append(th.get_text(strip=True))
                print("Table headers:", headers)
            else:
                print("No parent table found.")
    else:
        print("Could not find 'San Giovanni'")

if __name__ == "__main__":
    parse_html()
