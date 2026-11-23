"""Une méthode epsilon-contrainte, avec Gurobi uniquement."""
from datetime import datetime, timezone
from time import perf_counter
import gurobipy as gp
from gurobipy import GRB
from .modele import construire_modele
from .verification import coordonnees, evaluer_planning, non_domines

def extraire_solution(data, X, Y, E, L, variante):
    retenus = [data["jobs"][j]["name"] for j in Y if Y[j].X > .5]
    affectations = []
    for (i, j, k, t), variable in X.items():
        if variable.X > .5:
            affectations.append({"personne": data["staff"][i]["name"],
                                 "projet": data["jobs"][j]["name"], "competence": k, "jour": t})
    affectations.sort(key=lambda a: (a["personne"], a["jour"]))
    mesures = evaluer_planning(data, affectations, retenus)
    for j, detail in enumerate(mesures["projets"]):
        if abs(E[j].X - detail["fin"]) > 1e-5 or abs(L[j].X - detail["retard"]) > 1e-5:
            raise ValueError("Dates du modèle différentes du planning")
    benefice, cout = coordonnees(mesures, variante)
    return {"benefice": benefice, "cout": cout, "retenus": retenus,
            "affectations": affectations, "mesures": mesures, "valide": True}

def calculer_front(data, variante="gain_penalite", limite=30, budget=120):
    if limite <= 0 or budget <= 0:
        raise ValueError("Les budgets doivent être positifs")
    debut = perf_counter()
    resultat = {"variante": variante, "moteur": "gurobi", "methode": "epsilon_contrainte",
                "date_utc": datetime.now(timezone.utc).isoformat(),
                "version_gurobi": list(gp.gurobi.version()),
                "parametres": {"limite": limite, "budget": budget},
                "complet": False, "points": [], "candidats_non_certifies": [], "resolutions": []}

    bruts = []
    m = None
    try:
        m, X, Y, E, L, benefice, cout, borne = construire_modele(data, variante)
        resultat.update(variables=m.NumVars, contraintes=m.NumConstrs, variables_X=len(X))
        m.Params.MIPGap = 0
        m.Params.MIPGapAbs = 0
        m.Params.Threads = 4
        m.Params.Seed = 18

        plafond = m.addConstr(cout <= borne, name="plafond_cout")
        epsilon = borne
        while True:
            restant = budget - (perf_counter() - debut)
            if restant <= 0:
                resultat["arret"] = "Budget total atteint"
                break
            plafond.RHS = epsilon
            m.Params.TimeLimit = min(limite, restant)
            m.optimize()
            etape = {"epsilon": epsilon, "statut": m.Status, "secondes": m.Runtime}
            if m.SolCount:
                etape.update(objectif=m.ObjVal, borne=m.ObjBound, gap=m.MIPGap)
                point = extraire_solution(data, X, Y, E, L, variante)
                bruts.append(point)
            resultat["resolutions"].append(etape)
            if m.Status == GRB.INFEASIBLE:
                resultat.update(complet=True, arret="Infaisabilité prouvée")
                break
            if m.Status != GRB.OPTIMAL:
                resultat["arret"] = f"Résolution interrompue, statut Gurobi {m.Status}"
                break
            if point["cout"] == 0:
                resultat.update(complet=True, arret="Coût minimal nul atteint")
                break
            epsilon = point["cout"] - 1
    except gp.GurobiError as erreur:
        resultat.update(arret="Erreur Gurobi", erreur=str(erreur), erreur_code=erreur.errno)
    finally:
        if m is not None:
            m.dispose()

    coord_gardees = non_domines([(p["benefice"], p["cout"]) for p in bruts])
    points = []
    deja_vus = set()
    for point in bruts:
        coord = (point["benefice"], point["cout"])
        if coord in coord_gardees and coord not in deja_vus:
            points.append(point)
            deja_vus.add(coord)
    if resultat["complet"]:
        resultat["points"] = points
    else:
        resultat["candidats_non_certifies"] = points
    resultat.update(secondes=perf_counter() - debut, solutions_brutes=len(bruts),
                    points_retires=len(bruts) - len(points))
    return resultat
