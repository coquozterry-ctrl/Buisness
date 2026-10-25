#!/usr/bin/env python3
"""Trouve les restaurants autour d'une adresse qui n'ont pas de vrai site web.

Source principale : Google Places API (New), clé dans GOOGLE_MAPS_API_KEY.
Repli sans clé : OpenStreetMap (Overpass), gratuit mais moins complet.

Aucune dépendance externe : bibliothèque standard uniquement.

Exemples :
    python3 scripts/trouver_restaurants.py --adresse "Rue de Bourg 1, Lausanne" --rayon 1500
    python3 scripts/trouver_restaurants.py --lat 46.52 --lng 6.63 --rayon 800 --source osm
"""

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

USER_AGENT = "prospection-restaurants/1.0"
RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PROSPECTS = RACINE / "prospects"

# Un lien vers ces domaines ne compte pas comme un vrai site : c'est un prospect.
DOMAINES_SOCIAUX = (
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "linktr.ee",
    "tripadvisor.", "thefork.", "lafourchette.", "ubereats.com", "just-eat.",
    "smood.ch", "eat.ch", "deliveroo.", "wolt.com", "google.com", "business.site",
    "yelp.", "menu.ch",
)

CHAMPS_GOOGLE = ",".join(
    "places." + c
    for c in (
        "id", "displayName", "formattedAddress", "location", "websiteUri",
        "nationalPhoneNumber", "internationalPhoneNumber", "rating", "userRatingCount",
        "googleMapsUri", "types", "primaryTypeDisplayName", "priceLevel",
        "businessStatus", "regularOpeningHours", "editorialSummary", "reviews",
    )
) + ",nextPageToken"


def requete_json(url, donnees=None, entetes=None, delai=30):
    corps = None
    entetes = {"User-Agent": USER_AGENT, **(entetes or {})}
    if donnees is not None:
        if isinstance(donnees, dict):
            corps = json.dumps(donnees).encode()
            entetes.setdefault("Content-Type", "application/json")
        else:
            corps = donnees.encode()
    req = urllib.request.Request(url, data=corps, headers=entetes)
    try:
        with urllib.request.urlopen(req, timeout=delai) as rep:
            return json.load(rep)
    except urllib.error.HTTPError as e:
        message = e.read().decode(errors="replace")[:500]
        sys.exit(f"Erreur HTTP {e.code} sur {url.split('?')[0]} : {message}")


def geocoder(adresse):
    """Adresse -> (lat, lng) via Nominatim (OpenStreetMap), gratuit."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": adresse, "format": "json", "limit": 1}
    )
    resultats = requete_json(url)
    if not resultats:
        sys.exit(f"Adresse introuvable : {adresse}")
    return float(resultats[0]["lat"]), float(resultats[0]["lon"])


def statut_site(url):
    """'aucun', 'reseau_social' ou 'site'."""
    if not url:
        return "aucun"
    hote = urllib.parse.urlparse(url if "://" in url else "http://" + url).netloc.lower()
    if any(d in hote for d in DOMAINES_SOCIAUX):
        return "reseau_social"
    return "site"


def chercher_google(lat, lng, rayon, cle, maximum):
    lieux, jeton = [], None
    while len(lieux) < maximum:
        corps = {
            "textQuery": "restaurant",
            "includedType": "restaurant",
            "pageSize": 20,
            "languageCode": "fr",
            "locationRestriction": {
                "rectangle": rectangle_autour(lat, lng, rayon),
            },
        }
        if jeton:
            corps["pageToken"] = jeton
        rep = requete_json(
            "https://places.googleapis.com/v1/places:searchText",
            donnees=corps,
            entetes={"X-Goog-Api-Key": cle, "X-Goog-FieldMask": CHAMPS_GOOGLE},
        )
        lieux.extend(rep.get("places", []))
        jeton = rep.get("nextPageToken")
        if not jeton:
            break
        time.sleep(2)  # le jeton de page met un instant à devenir valide
    return [normaliser_google(p) for p in lieux[:maximum]]


def rectangle_autour(lat, lng, rayon):
    # searchText n'accepte qu'un rectangle en restriction ; approximation suffisante.
    dlat = rayon / 111_320
    dlng = rayon / (111_320 * max(0.1, abs(math.cos(math.radians(lat)))))
    return {
        "low": {"latitude": lat - dlat, "longitude": lng - dlng},
        "high": {"latitude": lat + dlat, "longitude": lng + dlng},
    }


def normaliser_google(p):
    return {
        "source": "google",
        "id": p.get("id"),
        "nom": p.get("displayName", {}).get("text"),
        "adresse": p.get("formattedAddress"),
        "lat": p.get("location", {}).get("latitude"),
        "lng": p.get("location", {}).get("longitude"),
        "telephone": p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber"),
        "site": p.get("websiteUri"),
        "statut_site": statut_site(p.get("websiteUri")),
        "type": p.get("primaryTypeDisplayName", {}).get("text"),
        "categories": p.get("types", []),
        "note": p.get("rating"),
        "nb_avis": p.get("userRatingCount"),
        "prix": p.get("priceLevel"),
        "ouvert": p.get("businessStatus"),
        "horaires": p.get("regularOpeningHours", {}).get("weekdayDescriptions"),
        "resume": p.get("editorialSummary", {}).get("text"),
        "avis": [
            {
                "note": a.get("rating"),
                "texte": a.get("text", {}).get("text") or a.get("originalText", {}).get("text"),
                "quand": a.get("relativePublishTimeDescription"),
            }
            for a in p.get("reviews", [])
        ],
        "google_maps": p.get("googleMapsUri"),
    }


def chercher_osm(lat, lng, rayon, maximum):
    requete = f"""
    [out:json][timeout:60];
    nwr["amenity"~"^(restaurant|fast_food|cafe)$"](around:{rayon},{lat},{lng});
    out center tags;
    """
    rep = requete_json(
        "https://overpass-api.de/api/interpreter",
        donnees="data=" + urllib.parse.quote(requete),
        entetes={"Content-Type": "application/x-www-form-urlencoded"},
        delai=90,
    )
    lieux = []
    for el in rep.get("elements", []):
        t = el.get("tags", {})
        if not t.get("name"):
            continue
        site = t.get("website") or t.get("contact:website") or t.get("url")
        if not site and t.get("contact:facebook"):
            site = t["contact:facebook"]
        adresse = " ".join(
            filter(None, [t.get("addr:street"), t.get("addr:housenumber"), t.get("addr:postcode"), t.get("addr:city")])
        )
        lieux.append({
            "source": "osm",
            "id": f"osm-{el['type']}-{el['id']}",
            "nom": t["name"],
            "adresse": adresse or None,
            "lat": el.get("lat") or el.get("center", {}).get("lat"),
            "lng": el.get("lon") or el.get("center", {}).get("lon"),
            "telephone": t.get("phone") or t.get("contact:phone"),
            "site": site,
            "statut_site": statut_site(site),
            "type": t.get("cuisine") or t.get("amenity"),
            "categories": [t.get("amenity")],
            "horaires": t.get("opening_hours"),
            "google_maps": f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(t['name'] + ' ' + adresse)}",
            "avis": [],
        })
    return lieux[:maximum]


def slug(texte):
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")[:60]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adresse", help="adresse de départ (géocodée via OpenStreetMap)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lng", type=float)
    ap.add_argument("--rayon", type=int, default=1500, help="rayon en mètres (défaut 1500)")
    ap.add_argument("--max", type=int, default=60, help="nombre max de restaurants examinés (Google : 60 max)")
    ap.add_argument("--source", choices=["auto", "google", "osm"], default="auto")
    ap.add_argument("--exclure-reseaux", action="store_true",
                    help="ignorer ceux qui n'ont qu'une page Facebook/Instagram (gardés par défaut)")
    args = ap.parse_args()

    if args.lat is not None and args.lng is not None:
        lat, lng = args.lat, args.lng
    elif args.adresse:
        lat, lng = geocoder(args.adresse)
    else:
        ap.error("donne --adresse ou --lat et --lng")

    cle = os.environ.get("GOOGLE_MAPS_API_KEY")
    source = args.source
    if source == "auto":
        source = "google" if cle else "osm"
    if source == "google" and not cle:
        sys.exit("GOOGLE_MAPS_API_KEY manquante (voir README.md).")

    print(f"Recherche {source} autour de {lat:.5f},{lng:.5f} dans un rayon de {args.rayon} m…", file=sys.stderr)
    lieux = chercher_google(lat, lng, args.rayon, cle, args.max) if source == "google" else chercher_osm(lat, lng, args.rayon, args.max)

    gardes = [
        l for l in lieux
        if l.get("ouvert", "OPERATIONAL") == "OPERATIONAL"
        and (l["statut_site"] == "aucun" or (not args.exclure_reseaux and l["statut_site"] == "reseau_social"))
    ]
    # Les mieux notés et les plus fréquentés d'abord : ce sont les meilleurs prospects.
    gardes.sort(key=lambda l: ((l.get("nb_avis") or 0) * (l.get("note") or 3)), reverse=True)

    DOSSIER_PROSPECTS.mkdir(exist_ok=True)
    for l in gardes:
        l["slug"] = slug(l["nom"])
        dossier = DOSSIER_PROSPECTS / l["slug"]
        dossier.mkdir(exist_ok=True)
        (dossier / "fiche.json").write_text(json.dumps(l, ensure_ascii=False, indent=2))

    resume = {
        "date": date.today().isoformat(),
        "source": source,
        "centre": {"lat": lat, "lng": lng},
        "rayon_m": args.rayon,
        "examines": len(lieux),
        "sans_site": len(gardes),
        "prospects": [
            {k: l.get(k) for k in ("slug", "nom", "adresse", "telephone", "statut_site", "site", "note", "nb_avis")}
            for l in gardes
        ],
    }
    (DOSSIER_PROSPECTS / "liste.json").write_text(json.dumps(resume, ensure_ascii=False, indent=2))
    print(json.dumps(resume, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
