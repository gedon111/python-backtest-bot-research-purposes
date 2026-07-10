import os
import urllib.request
import urllib.error

SHEET_ID = "1-xY80Rdcdpx_I9k5ZTQRuOtfImnX53uo9y-eEyh5udU"
GIDS = {
    "Sheet1": "0",
    "Trade_Records": "2023134325",
    "Quality_0": "440553064",
    "Quality_1": "1230784951",
    "Quality_2": "236768565",
    "Quality_3": "1089627289",
    "Summary_Quality_Sweep": "1013647811"
}

def download_csv(name, gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    dest_path = f"scratch/{name}.csv"
    print(f"Downloading {name} (GID: {gid}) from {url}...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            with open(dest_path, "wb") as f:
                f.write(data)
        print(f"  Successfully saved to {dest_path} ({len(data)} bytes).")
        return True
    except urllib.error.URLError as e:
        print(f"  Error downloading {name}: {e}")
        return False

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    success_count = 0
    for name, gid in GIDS.items():
        if download_csv(name, gid):
            success_count += 1
    print(f"\nDownloaded {success_count}/{len(GIDS)} sheets successfully.")
