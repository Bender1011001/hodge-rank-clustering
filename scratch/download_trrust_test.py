import urllib.request
import urllib.error

url = "https://www.grnpedia.org/trrust/data/trrust_rawdata.human.tsv"
try:
    print(f"Downloading TRRUST human dataset from: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        print("Success! First 5 lines:")
        for line in lines[:5]:
            print(f"  {line}")
except Exception as e:
    print(f"Error downloading dataset: {e}")
