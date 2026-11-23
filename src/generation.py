"""Créer des instances reproductibles à partir d'un planning témoin."""

import random
from .donnees import verifier_donnees
from .verification import evaluer_planning

def generer_instance(graine, horizon=8, personnes=4, competences=3, projets=6,
                     scenario="serre", taux_conges=0.1):
    if scenario not in ("souple", "serre", "surcharge", "competence_rare"):
        raise ValueError("Scénario inconnu")
    if min(horizon, personnes, competences, projets) < 1 or not 0 <= taux_conges < 1:
        raise ValueError("Dimensions ou taux de congé invalides")
    if competences > personnes * 3:
        raise ValueError("Trop de compétences pour cette famille d'instances")
    rng = random.Random(graine)
    qs = [f"C{k+1}" for k in range(competences)]
    staff = []
    for i in range(personnes):
        detenues = {qs[i % competences]}
        nb_qualifs = min(competences, 2)
        qualifs_tirees = rng.sample(qs, nb_qualifs)
        detenues.update(qualifs_tirees)
        nb_conges = min(horizon - 1, round(taux_conges * horizon))
        jours_possibles = range(1, horizon + 1)
        conges = rng.sample(jours_possibles, nb_conges)
        conges.sort()
        staff.append({
            "name": f"Personne{i+1}", "qualifications": sorted(detenues),
            "vacations": conges,
        })
    for k, q in enumerate(qs):
        personne = staff[k % personnes]
        personne["qualifications"] = sorted(set(personne["qualifications"]) | {q})
    if scenario == "competence_rare":
        rare = qs[-1]
        staff[0]["qualifications"] = sorted(set(staff[0]["qualifications"]) | {rare})
        for personne in staff[1:]:
            personne["qualifications"] = [k for k in personne["qualifications"] if k != rare]
            if not personne["qualifications"]:
                if competences == 1:
                    raise ValueError("Le scénario rare demande au moins deux compétences")
                personne["qualifications"] = [qs[0]]
    creneaux = []
    for i, personne in enumerate(staff):
        for t in range(1, horizon + 1):
            if t not in personne["vacations"]:
                creneaux.append((i, t))
    rng.shuffle(creneaux)
    charge_cible = round(0.85 * len(creneaux))
    charge = max(projets, charge_cible)
    if projets > len(creneaux):
        raise ValueError("Pas assez de journées disponibles pour le planning témoin")
    creneaux = creneaux[:charge]
    demandes = []
    dates = []
    for j in range(projets):
        demandes.append({})
        dates.append([])
    temoin = []
    for n, (i, t) in enumerate(creneaux):
        if n < projets:
            j = n
        else:
            j = rng.randrange(projets)
        k = rng.choice(staff[i]["qualifications"])
        demandes[j][k] = demandes[j].get(k, 0) + 1
        dates[j].append(t)
        temoin.append({"personne": staff[i]["name"], "projet": f"Mission{j+1}", "competence": k, "jour": t})
    jobs = []
    for j in range(projets):
        fin = max(dates[j])
        decalage = rng.randint(0, max(1, horizon//2))
        if scenario == "souple":
            echeance = horizon
        else:
            echeance = max(1, fin - decalage)
        jobs.append({
            "name": f"Mission{j+1}", "gain": rng.randint(15, 70),
            "due_date": echeance, "daily_penalty": rng.randint(1, 8),
            "working_days_per_qualification": demandes[j],
        })
    if scenario == "surcharge":
        for j in range(max(1, projets // 2)):
            original = rng.choice(jobs[:projets])
            jobs.append({
                **original, "name": f"Option{j+1}", "gain": rng.randint(15, 70),
                "working_days_per_qualification": dict(original["working_days_per_qualification"]),
            })
    data = {"horizon": horizon, "qualifications": qs, "staff": staff, "jobs": jobs}
    verifier_donnees(data)
    selection = [j["name"] for j in jobs[:projets]]
    mesures = evaluer_planning(data, temoin, selection)
    return data, {
        "graine": graine, "scenario": scenario, "selection_realisable": selection,
        "affectations": temoin, "mesures": mesures,
        "parametres": {"horizon": horizon, "personnes": personnes, "competences": competences,
                       "projets": projets, "taux_conges": taux_conges},
    }
