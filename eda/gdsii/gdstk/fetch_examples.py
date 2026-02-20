import requests
from bs4 import BeautifulSoup
import os
import zipfile
import io

URL = "https://www.yzuda.org/download/_GDSII_examples.html"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def download_examples():
    print(f"Fetching {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Create examples directory if it doesn't exist
    os.makedirs('examples', exist_ok=True)
    
    # Find all download links (matching .zip or .gds)
    links = [a['href'] for a in soup.find_all('a', href=True) if 'download' in a['href'] and (a['href'].endswith('.zip') or a['href'].endswith('.gds'))]
    
    for link in links:
        if link.startswith('.'):
            # Resolve relative links
            full_url = "https://www.yzuda.org" + link[1:]
        elif link.startswith('/'):
            full_url = "https://www.yzuda.org" + link
        else:
            full_url = link
            
        print(f"Downloading {full_url}")
        
        file_resp = requests.get(full_url, headers=HEADERS)
        
        filename = full_url.split('/')[-1]
        
        if filename.endswith('.zip'):
             print(f"Extracting {filename}")
             with zipfile.ZipFile(io.BytesIO(file_resp.content)) as z:
                 z.extractall('examples')
        else:
             print(f"Saving {filename}")
             with open(os.path.join('examples', filename), 'wb') as f:
                 f.write(file_resp.content)
                 

if __name__ == "__main__":
    download_examples()
    print("Done!")
