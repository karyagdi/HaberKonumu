from app.db.mongo import get_news_collection
from app.services.geocoding import geocode_location, is_within_kocaeli_bounds


def has_missing_coordinates(doc):
    coordinates = doc.get("coordinates") or {}
    lat = coordinates.get("lat")
    lng = coordinates.get("lng")

    return lat in [None, "", "None"] or lng in [None, "", "None"]


def run():
    collection = get_news_collection()
    docs = collection.find({})

    checked_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    deleted_count = 0

    for doc in docs:
        checked_count += 1

        if not has_missing_coordinates(doc):
            skipped_count += 1
            continue

        location_text = (doc.get("location_text") or "").strip()
        district = (doc.get("district") or "").strip()

        lat, lng = geocode_location(location_text, district)

        # 1. API çökük veya hiçbir şey bulunamadı (Veriyi silme, atla)
        if lat is None or lng is None:
            failed_count += 1
            print(f"Koordinat bulunamadi (Atlandi): {doc.get('title', '')}")
            continue

        # 2. Koordinat bulundu ama Kocaeli dışında! (Proje dışı, SİL)
        if not is_within_kocaeli_bounds(lat, lng):
            collection.delete_one({"_id": doc["_id"]})
            deleted_count += 1
            print(f"Sinir disi, SİLİNDİ: {doc.get('title', '')} -> {lat}, {lng}")
            continue

        # 3. Her şey yolunda, Kocaeli sınırlarında (DB'yi güncelle)
        collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "coordinates.lat": lat,
                    "coordinates.lng": lng
                }
            }
        )
        updated_count += 1
        print(f"Guncellendi: {doc.get('title', '')} -> {lat}, {lng}")

    print("\n--- Islem Tamamlandi ---")
    print(f"Kontrol edilen: {checked_count}")
    print(f"Guncellenen: {updated_count}")
    print(f"Atlanan (Zaten Var): {skipped_count}")
    print(f"Silinen (Sinir Disi): {deleted_count}")
    print(f"Basarisiz (Bulunamayan): {failed_count}")


if __name__ == "__main__":
    run()