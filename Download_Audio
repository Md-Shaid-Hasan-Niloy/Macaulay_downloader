import os 
import requests
import pandas as pd
import time
# URL to eBird taxonomy JSON mapping
EBIRD_TAXONOMY_URL = "https://raw.githubusercontent.com/mi3nts/mDashSupport/main/resources/birdCalls/eBird_taxonomy_codes_2021E.json"

# Load taxonomy into DataFrame
def load_taxonomy():
    r = requests.get(EBIRD_TAXONOMY_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame.from_dict(data, orient='index', columns=['Species'])
    df.reset_index(inplace=True)
    df.columns = ['Code', 'Species']
    return df

# Match species name to taxonCode
def get_code_for_species(species_name, df):
    row = df[df['Species'] == species_name]
    if not row.empty:
        return row['Code'].iloc[0]
    else:
        return None

# Query Macaulay for audio recordings using taxonCode
def get_audio_for_species(code):
    url = "https://search.macaulaylibrary.org/api/v1/search"
    params = {
        "taxonCode": code,
        "mediaType": "audio",
        "sort": "rating_rank_desc",
        "pageSize": 500
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("results", {}).get("content", [])

# Download audio file
def download_audio(item, folder):
    audio_url = item.get("audioUrl") or item.get("mediaUrl")
    if not audio_url:
        return
    file_name = f"{item['assetId']}.mp3"
    file_path = os.path.join(folder, file_name)
    if os.path.exists(file_path):
        return
    r = requests.get(audio_url, stream=True, timeout=60)
    if r.status_code == 200:
        with open(file_path, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                f.write(chunk)
        print(f"✅ Downloaded: {file_name} from {audio_url}")

# --- MAIN ---species_name = "Panthera leo_Lion"   # Format: ScientificName_CommonName
save_dir = "downloads/Macaulay_final"
os.makedirs(save_dir, exist_ok=True)
df = load_taxonomy()
for idx, row in df.iterrows():
    code = row["Code"]
    species_name = row["Species"]

    if not code.islower():
        continue
    
    species_folder = os.path.join(save_dir, species_name.replace(" ", "_"))
    os.makedirs(species_folder, exist_ok=True)

    try:
        audios = get_audio_for_species(code)
        if audios:

            print(f"{len(audios)} recordings found for {species_name}")

            for audio in audios:
                download_audio(audio, species_folder) 
        else:
            print(f"No audios for {species_name}")
    
    except Exception as e:
        print(f"error for {species_name}: {e}") 
    
    time.sleep(0.1)
    

