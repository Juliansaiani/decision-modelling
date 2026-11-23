"""Contrôle d'un planning sans utiliser les variables auxiliaires du solveur."""

from collections import Counter, defaultdict
from .donnees import verifier_donnees

def evaluer_planning(data, affectations, retenus):
    verifier_donnees(data)
    personnes = {p["name"]: p for p in data["staff"]}
    projets = {j["name"]: j for j in data["jobs"]}
    if len(set(retenus)) != len(retenus) or not set(retenus) <= projets.keys():
        raise ValueError("Sélection de projets invalide")
    occupation = Counter()
    couverture = Counter()
    jours = defaultdict(list)
    liens = defaultdict(set)
    for a in affectations:
        nom = a["personne"]
        job = a["projet"]
        k = a["competence"]
        t = a["jour"]
        if nom not in personnes or job not in projets:
            raise ValueError("Identifiant inconnu dans le planning")
        p, j = personnes[nom], projets[job]
        if type(t) is not int or not 1 <= t <= data["horizon"]:
            raise ValueError("Jour hors horizon")
        if t in p["vacations"]:
            raise ValueError(f"Affectation en congé : {nom}, jour {t}")
        if k not in p["qualifications"] or k not in j["working_days_per_qualification"]:
            raise ValueError("Compétence absente ou non demandée")
        if job not in retenus:
            raise ValueError("Travail sur un projet non retenu")
        occupation[nom, t] += 1
        if occupation[nom, t] > 1:
            raise ValueError(f"Double affectation : {nom}, jour {t}")
        couverture[job, k] += 1
        jours[job].append(t)
        liens[nom].add(job)
    details = []
    for nom, j in projets.items():
        choisi = nom in retenus
        for k, besoin in j["working_days_per_qualification"].items():
            if couverture[nom, k] != besoin * choisi:
                raise ValueError(f"Couverture incorrecte : {nom}, {k}")
        debut = 0
        fin = 0
        retard = 0
        if choisi:
            debut = min(jours[nom])
            fin = max(jours[nom])
            retard = max(0, fin - j["due_date"])
        details.append({
            "projet": nom, "retenu": choisi, "debut": debut, "fin": fin,
            "echeance": j["due_date"], "retard": retard,
            "duree": fin - debut + 1 if choisi else 0,
            "gain": j["gain"] if choisi else 0,
            "penalite": retard * j["daily_penalty"],
        })
    gain = sum(j["gain"] for j in details)
    penalite = sum(j["penalite"] for j in details)
    return {
        "gain": gain, "penalite": penalite, "net": gain - penalite,
        "retards": sum(j["retard"] > 0 for j in details),
        "dispersion": max((len(liens[p]) for p in personnes), default=0),
        "liens": sum(len(v) for v in liens.values()),
        "occupation": len(affectations),
        "makespan": max((j["fin"] for j in details), default=0),
        "duree_max": max((j["duree"] for j in details), default=0),
        "projets": details,
    }

CRITERES = {
    "gain_penalite": ("gain", "penalite"),
    "net_dispersion": ("net", "dispersion"),
}

def coordonnees(mesures, variante):
    benefice, cout = CRITERES[variante]
    return mesures[benefice], mesures[cout]

def non_domines(points):
    """Un point (bénéfice, coût) : le premier se maximise, le second se minimise."""
    gardes = set()
    for benefice, cout in points:
        domine = False
        for autre_benefice, autre_cout in points:
            au_moins_aussi_bon = autre_benefice >= benefice and autre_cout <= cout
            strictement_meilleur = autre_benefice > benefice or autre_cout < cout
            if au_moins_aussi_bon and strictement_meilleur:
                domine = True
                break
        if not domine:
            gardes.add((benefice, cout))
    return sorted(gardes)
