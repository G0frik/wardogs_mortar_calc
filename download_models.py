import os
import sys
import urllib.request
import zipfile

MODELS = {
    "en": {
        "name": "vosk-model-small-en-us-0.15",
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "dir": "vosk-model-small-en-us-0.15"
    },
    "uk": {
        "name": "vosk-model-small-uk-v3-nano",
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-uk-v3-nano.zip",
        "dir": "vosk-model-small-uk-v3-nano"
    }
}

def reporthook(block_num, block_size, total_size):
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    percent = min(100, downloaded * 100 // total_size)
    mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    sys.stdout.write(f"\rDownloading: {percent}% [{mb:.1f}/{total_mb:.1f} MB]")
    sys.stdout.flush()

def download_and_extract(lang, target_folder="models"):
    info = MODELS.get(lang)
    if not info:
        print(f"Unknown language: {lang}")
        return False

    os.makedirs(target_folder, exist_ok=True)
    dest_dir = os.path.join(target_folder, info["dir"])
    
    if os.path.exists(dest_dir):
        print(f"[{lang.upper()}] Model already present at: {dest_dir}")
        return True

    zip_path = os.path.join(target_folder, f"{info['name']}.zip")
    print(f"\n[{lang.upper()}] Downloading {info['name']} from {info['url']}...")
    try:
        urllib.request.urlretrieve(info["url"], zip_path, reporthook=reporthook)
        print("\nExtracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
        os.remove(zip_path)
        print(f"[{lang.upper()}] Successfully installed to {dest_dir}!")
        return True
    except Exception as e:
        print(f"\nError installing model: {e}")
        if os.path.exists(zip_path):
            try: os.remove(zip_path)
            except: pass
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("all", "en"):
        download_and_extract("en")
    if target in ("all", "uk"):
        download_and_extract("uk")
