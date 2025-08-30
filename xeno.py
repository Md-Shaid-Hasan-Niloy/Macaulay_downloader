import os
import requests
import time

# === CONFIG ===
BASE_DIR = "xeno_canto_downloads"
os.makedirs(BASE_DIR, exist_ok=True)

GBIF_API = "https://api.gbif.org/v1/species/search"
XC_API = "https://xeno-canto.org/api/2/recordings?query="

# === Step 1: Fetch all bird species from GBIF ===
def get_gbif_bird_species():
    params = {
        "rank": "SPECIES",
        "highertaxon_key": 212,   # Aves
        "limit": 300,             # GBIF max per page
        "offset": 0
    }

    species_list = []
    while True:
        r = requests.get(GBIF_API, params=params)
        if r.status_code != 200:
            print("❌ Error fetching from GBIF")
            break
        data = r.json()
        results = data.get("results", [])
        if not results:
            break

        for sp in results:
            if "canonicalName" in sp:
                species_list.append(sp["canonicalName"])

        params["offset"] += params["limit"]
        print(f"📥 Fetched {len(species_list)} species so far...")

        # Stop when no more
        if params["offset"] >= data.get("count", 0):
            break
        time.sleep(0.2)  # polite delay

    return species_list


# === Step 2: Download all calls for a given species ===
def download_species(species_name):
    print(f"\n=== Downloading {species_name} ===")

    # Make folder for species
    folder_name = os.path.join(BASE_DIR, species_name.replace(" ", "_"))
    os.makedirs(folder_name, exist_ok=True)

    page = 1
    while True:
        url = f"{XC_API}{species_name}&page={page}"
        r = requests.get(url)
        if r.status_code != 200:
            print(f"❌ Failed to fetch page {page} for {species_name}")
            break

        data = r.json()
        recordings = data.get("recordings", [])
        if not recordings:
            break

        for rec in recordings:
            raw_url = rec.get("file", "")
            if not raw_url:
                continue
            file_url = "https:" + raw_url if raw_url.startswith("//") else raw_url

            rec_id = rec["id"]
            filename = os.path.join(folder_name, f"{rec_id}.mp3")

            if os.path.exists(filename):
                continue  # Skip already downloaded

            print(f"⬇️ {filename}")
            try:
                audio = requests.get(file_url, timeout=30)
                if audio.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(audio.content)
                else:
                    print(f"⚠️ Failed {file_url} (status {audio.status_code})")
            except Exception as e:
                print(f"⚠️ Error downloading {file_url}: {e}")

            time.sleep(1)  # polite delay for XC

        if page >= data.get("numPages", 0):
            break
        page += 1


# === MAIN ===
if __name__ == "__main__":
    # 1. Get all bird species from GBIF
    birds = get_gbif_bird_species()
    print(f"\n✅ Total bird species fetched from GBIF: {len(birds)}")

    # 2. Download calls for each species
    for sp in birds:
        download_species(sp)

    print("\n🎉 All downloads complete.")
