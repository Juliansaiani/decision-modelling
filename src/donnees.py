"""Lecture des instances : les identifiants et les jours restent ceux du JSON."""

from pathlib import Path
import json

RACINE = Path(__file__).resolve().parents[1]

def verifier_donnees(data):
    def entier(x, minimum=0):
        return type(x) is int and x >= minimum
    def noms_uniques(elements, label):
        noms = [e["name"] for e in elements]
        if any(not isinstance(n, str) or not n for n in noms) or len(set(noms)) != len(noms):
            raise ValueError(f"Noms invalides ou répétés : {label}")
    h = data["horizon"]
    if not entier(h, 1):
        raise ValueError("Horizon entier positif attendu")
    qualifs = data["qualifications"]
    if (not qualifs or any(not isinstance(k, str) or not k for k in qualifs)
            or len(set(qualifs)) != len(qualifs)):
        raise ValueError("Qualifications invalides")
    if not data["staff"] or not data["jobs"]:
        raise ValueError("Personnel et projets non vides attendus")
    noms_uniques(data["staff"], "personnel")
    noms_uniques(data["jobs"], "projets")
    for personne in data["staff"]:
        qs, conges = personne["qualifications"], personne["vacations"]
        if not set(qs) <= set(qualifs) or len(set(qs)) != len(qs):
            raise ValueError("Qualifications du personnel invalides")
        if len(set(conges)) != len(conges) or any(not entier(t, 1) or t > h for t in conges):
            raise ValueError("Congés hors 1..h ou répétés")
    for projet in data["jobs"]:
        for champ in ("gain", "daily_penalty"):
            if not entier(projet[champ]):
                raise ValueError(f"{champ} doit être entier non négatif")
        if not entier(projet["due_date"], 1):
            raise ValueError("Échéance entière positive attendue")
        besoins = projet["working_days_per_qualification"]
        if (not besoins or not set(besoins) <= set(qualifs)
                or any(not entier(v, 1) for v in besoins.values())):
            raise ValueError("Besoins invalides")
    return data

def lire_instance(chemin):
    chemin = Path(chemin)
    texte_json = chemin.read_text(encoding="utf-8-sig")
    data = json.loads(texte_json)
    data = verifier_donnees(data)
    return data

def dimensions(data):
    h = data["horizon"]
    capacite = 0
    for personne in data["staff"]:
        jours_disponibles = h - len(personne["vacations"])
        capacite += jours_disponibles
    charge = 0
    for projet in data["jobs"]:
        jours_demandes = sum(projet["working_days_per_qualification"].values())
        charge += jours_demandes
    return {
        "jours": h, "personnes": len(data["staff"]), "projets": len(data["jobs"]),
        "competences": len(data["qualifications"]),
        "capacite": capacite,
        "charge": charge,
    }
