# ***************************************************************************
#   Animal Call Audio Downloader
#   ---------------------------------
#   Written by: Md Shaid Hasan Niloy
#   - for -
#   Mints: Multi-scale Integrated Sensing and Simulation
#   ---------------------------------
#   Date: July 16, 2025

import requests
import os
import pandas as pd
import time
import json
import re
import duckdb
from pydub import AudioSegment
import io

# Always use the real mounted D: drive inside WSL
main_audio_folder = "/mnt/d/Mints"
os.makedirs(main_audio_folder, exist_ok=True)

# API Endpoints
MACAULAY_URL = "https://search.macaulaylibrary.org/api/v1/search"
XENO_CANTO_URL = "https://xeno-canto.org/api/2/recordings"
EBIRD_TAXONOMY_URL = "https://raw.githubusercontent.com/mi3nts/mDashSupport/main/resources/birdCalls/eBird_taxonomy_codes_2021E.json"

# ------------------------------------------------------------------------------
# Load taxonomy
def load_taxonomy():
    r = requests.get(EBIRD_TAXONOMY_URL, timeout=30)
    r.raise_for_status()
    data = r.json()

    rows = []
    for code, species in data.items():
        if "_" in species:  # Only entries with "SciName_CommonName"
            sci, common = species.split("_", 1)
            rows.append({"Code": code, "Scientific name": sci, "Common name": common})

    df = pd.DataFrame(rows)
    return df

# ------------------------------------------------------------------------------
# DuckDB setup
db_path = os.path.join(main_audio_folder, "audio_metadata.db")
con = duckdb.connect(db_path)
con.execute("""
CREATE TABLE IF NOT EXISTS metadata (
    source TEXT,
    id TEXT,
    species TEXT,
    common_name TEXT,
    location TEXT,
    date TEXT,
    recordist TEXT,
    country TEXT,
    license TEXT,
    url TEXT,
    filename TEXT
)
""")

# ------------------------------------------------------------------------------
# Sanitize names for folder paths
def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', '', str(name).replace(' ', '_'))

# ------------------------------------------------------------------------------
# Taxonomy fetch from GBIF
def get_taxonomy_from_gbif(scientific_name):
    try:
        response = requests.get(
            f"https://api.gbif.org/v1/species/match?name={scientific_name}",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return {
            'class': data.get('class', 'Unknown'),
            'order': data.get('order', 'Unknown'),
            'family': data.get('family', 'Unknown'),
        }
    except Exception as e:
        print(f"❌ Taxonomy fetch failed for {scientific_name}: {e}")
        return {'class': 'Unknown', 'order': 'Unknown', 'family': 'Unknown'}

# ------------------------------------------------------------------------------
# Save metadata to DuckDB
def store_metadata(meta):
    con.execute("""
        INSERT INTO metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meta.get('source'),
        meta.get('id'),
        meta.get('species'),
        meta.get('common_name'),
        meta.get('location'),
        meta.get('date'),
        meta.get('recordist'),
        meta.get('country'),
        meta.get('license'),
        meta.get('url'),
        meta.get('filename')
    ))

# ------------------------------------------------------------------------------
# Download audio + json metadata and convert to WAV
def download_audio(species_folder, filename, url, metadata):
    try:
        filepath = os.path.join(species_folder, filename)
        jsonpath = filepath.rsplit(".", 1)[0] + ".json"
        if os.path.exists(filepath):
            print(f"↪️ Already exists: {filename}")
            return True

        response = requests.get(url, timeout=20)
        response.raise_for_status()

        # Convert to WAV format
        audio_data = io.BytesIO(response.content)
        
        if url.endswith('.mp3'):
            # Convert MP3 to WAV
            audio = AudioSegment.from_mp3(audio_data)
            audio.export(filepath, format="wav")
        else:
            # For other formats, try to read and convert to WAV
            try:
                audio = AudioSegment.from_file(audio_data)
                audio.export(filepath, format="wav")
            except:
                # If conversion fails, save as is but with .wav extension
                with open(filepath, 'wb') as f:
                    f.write(response.content)
        
        # Save metadata
        with open(jsonpath, 'w') as f:
            json.dump(metadata, f, indent=2)

        store_metadata(metadata)
        print(f"✓ Saved: {filename}")
        return True
    except Exception as e:
        print(f"❌ Download failed for {filename}: {e}")
        return False

# ------------------------------------------------------------------------------
# Macaulay fetch
def fetch_macaulay(scientific_name, code, species_folder):
    print(f"🔎 Searching Macaulay: {scientific_name}")
    params = {
        "taxonCode": code,
        "mediaType": "audio",
        "sort": "rating_rank_desc",
        "pageSize": 500
    }
    url = MACAULAY_URL

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        json_data = response.json()
        results = json_data.get('results', {}).get('content', [])

        print(f"  → Found {len(results)} recordings on Macaulay")

        for item in results:
            audio_url = item.get("audioUrl") or item.get("mediaUrl")
            asset_id = item.get("assetId")
            if not asset_id or not audio_url:
                continue

            filename = f"{sanitize(scientific_name)}_ML_{asset_id}.wav"  # Changed to WAV
            metadata = {
                "source": "Macaulay Library",
                "id": str(asset_id),
                "species": item.get("scientificName"),
                "common_name": item.get("commonName"),
                "location": item.get("location"),
                "date": item.get("date"),
                "recordist": item.get("recordist"),
                "country": item.get("country"),
                "license": item.get("license"),
                "url": f"https://macaulaylibrary.org/asset/{asset_id}",
                "filename": filename
            }
            download_audio(species_folder, filename, audio_url, metadata)

    except Exception as e:
        print(f"❌ Macaulay error for {scientific_name}: {e}")

# ------------------------------------------------------------------------------
# Xeno-Canto fetch
def fetch_xeno_canto(common_name, scientific_name, species_folder):
    print(f"🔎 Searching Xeno-Canto: {scientific_name}")
    try:
        params = {'query': scientific_name}
        response = requests.get(XENO_CANTO_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        recordings = data.get('recordings', [])
        print(f"  → Found {len(recordings)} recordings on Xeno-Canto")

        for item in recordings:
            file_url = item.get('file')
            if not file_url:
                continue
            if file_url.startswith("//"):
                file_url = "https:" + file_url

            filename = f"{sanitize(common_name)}_XC_{item['id']}.wav"  # Changed to WAV
            metadata = {
                "source": "Xeno-Canto",
                "id": str(item['id']),
                "species": item.get('sp'),
                "common_name": common_name,
                "location": item.get('loc'),
                "date": item.get('date'),
                "recordist": item.get('rec'),
                "country": item.get('cnt'),
                "license": item.get('lic'),
                "url": f"https://xeno-canto.org/{item['id']}",
                "filename": filename
            }
            download_audio(species_folder, filename, file_url, metadata)

    except Exception as e:
        print(f"❌ Xeno-Canto error for {scientific_name}: {e}")

# ------------------------------------------------------------------------------
# MAIN
def main():
    print("=====================================")
    print("  Macaulay + Xeno-Canto Downloader")
    print("  Taxonomic Folder Hierarchy: Class > Order > Family > Species")
    print("  Downloading files in WAV format")
    print("=====================================\n")

    df_species = load_taxonomy()
    for _, row in df_species.iterrows():
        common_name = row['Common name']
        scientific_name = row['Scientific name']
        code = row['Code']

        taxonomy = get_taxonomy_from_gbif(scientific_name)
        cls = sanitize(taxonomy['class'])
        order = sanitize(taxonomy['order'])
        family = sanitize(taxonomy['family'])
        species_folder = os.path.join(main_audio_folder, cls, order, family, sanitize(scientific_name))
        os.makedirs(species_folder, exist_ok=True)

        # Download from Macaulay
        fetch_macaulay(scientific_name, code, species_folder)

        # Download from Xeno-Canto
        fetch_xeno_canto(common_name, scientific_name, species_folder)

    print("\n✅ Download complete. Metadata saved to DuckDB.")

# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
