import os
import requests
import time
from pathlib import Path

# --- CONFIG ---
BASE_DIR = Path("AnimalCalls")  # Root directory for saving
DELAY = 2  # seconds between downloads to be nice to server

# --- FUNCTIONS ---
def get_gbif_species(limit=100000):
    """Fetch species list from GBIF backbone."""
    url = "https://api.gbif.org/v1/species/search"
    params = {"rank": "species", "limit": limit}
    species_list = []
    offset = 0

    while True:
        params["offset"] = offset
        r = requests.get(url, params=params)
        data = r.json()
        results = data.get("results", [])
        if not results:
            break

        for sp in results:
            if all(k in sp for k in ["kingdom", "phylum", "order", "family", "genus", "species"]):
                species_list.append(sp)

        offset += limit
        if offset >= data["count"]:
            break

    return species_list


def get_xc_recordings(scientific_name, page=1):
    """Fetch recordings from Xeno-Canto by scientific name."""
    url = f"https://www.xeno-canto.org/api/2/recordings"
    params = {"query": f"cnt:{scientific_name}", "page": page}
    r = requests.get(url, params=params)
    return r.json()


def download_recording(url, filepath):
    """Download MP3 recording if not exists."""
    if filepath.exists():
        return
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"Saved {filepath}")
    except Exception as e:
        print(f"Failed {url}: {e}")


def build_path(base, sp):
    """Build folder path from taxonomy."""
    return (
        base
        / sp["kingdom"]
        / sp["order"]
        / sp["family"]
        / sp["genus"]
        / sp["species"]
    )


# --- MAIN ---
if __name__ == "__main__":
    print("Fetching species list from GBIF...")
    species_list = get_gbif_species(limit=300)  # smaller batch for testing
    print(f"Total species fetched: {len(species_list)}")

    for sp in species_list:
        sci_name = sp["scientificName"]
        save_path = build_path(BASE_DIR, sp)
        save_path.mkdir(parents=True, exist_ok=True)

        print(f"Searching recordings for {sci_name}...")
        page = 1
        while True:
            data = get_xc_recordings(sci_name, page=page)
            if "recordings" not in data or not data["recordings"]:
                break

            for rec in data["recordings"]:
                file_url = f"https:{rec['file']}"
                file_name = f"{rec['id']}.mp3"
                filepath = save_path / file_name
                download_recording(file_url, filepath)
                time.sleep(DELAY)

            if page >= int(data["numPages"]):
                break
            page += 1
