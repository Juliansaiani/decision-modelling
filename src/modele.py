"""Modèle de staffing écrit directement avec gurobipy."""
import gurobipy as gp
from gurobipy import GRB
from .donnees import verifier_donnees

def construire_modele(data, variante="gain_penalite"):
    verifier_donnees(data)
    if variante not in ("gain_penalite", "net_dispersion"):
        raise ValueError("Choisir gain_penalite ou net_dispersion")
    h = data["horizon"]
    personnes = range(len(data["staff"]))
    projets = range(len(data["jobs"]))
    jours = range(1, h + 1)
    affectations = []
    for i, personne in enumerate(data["staff"]):
        for j, projet in enumerate(data["jobs"]):
            for k in projet["working_days_per_qualification"]:
                if k in personne["qualifications"]:
                    for t in jours:
                        if t not in personne["vacations"]:
                            affectations.append((i, j, k, t))

    m = gp.Model("CompuOpti")
    m.Params.OutputFlag = 0
    X = m.addVars(affectations, vtype=GRB.BINARY, name="X")
    Y = m.addVars(projets, vtype=GRB.BINARY, name="Y")
    U = m.addVars(projets, jours, vtype=GRB.BINARY, name="U")
    E = m.addVars(projets, vtype=GRB.INTEGER, ub=h, name="E")
    bornes_retard = {j: max(0, h - p["due_date"]) for j, p in enumerate(data["jobs"])}
    L = m.addVars(projets, vtype=GRB.INTEGER, ub=bornes_retard, name="L")

    for i in personnes:
        for t in jours:
            if X.select(i, "*", "*", t):
                m.addConstr(X.sum(i, "*", "*", t) <= 1, name=f"une_tache[{i},{t}]")
    for j, projet in enumerate(data["jobs"]):
        for k, besoin in projet["working_days_per_qualification"].items():
            travail = X.sum("*", j, k, "*")
            m.addConstr(travail == besoin * Y[j], name=f"couverture[{j},{k}]")
        m.addConstr(U.sum(j, "*") == Y[j], name=f"une_fin[{j}]")
        for t in jours:
            travail_jour = X.sum("*", j, "*", t)
            m.addConstr(U[j, t] <= travail_jour, name=f"fin_travaillee[{j},{t}]")
        fin = gp.quicksum(t * U[j, t] for t in jours)
        retard = gp.quicksum(max(0, t - projet["due_date"]) * U[j, t] for t in jours)
        m.addConstr(E[j] == fin, name=f"date_fin[{j}]")
        m.addConstr(L[j] == retard, name=f"jours_retard[{j}]")
    for (i, j, k, t), variable in X.items():
        derniere_journee = gp.quicksum(U[j, s] for s in range(t, h + 1))
        m.addConstr(variable <= derniere_journee, name=f"avant_fin[{i},{j},{k},{t}]")

    G = gp.quicksum(p["gain"] * Y[j] for j, p in enumerate(data["jobs"]))
    R = gp.quicksum(p["daily_penalty"] * L[j] for j, p in enumerate(data["jobs"]))
    if variante == "gain_penalite":
        benefice, cout = G, R
        borne = sum(p["daily_penalty"] * bornes_retard[j] for j, p in enumerate(data["jobs"]))
    else:
        liens = [(i, j) for i in personnes for j in projets if X.select(i, j, "*", "*")]
        B = m.addVars(liens, vtype=GRB.BINARY, name="B")
        F = m.addVar(vtype=GRB.INTEGER, ub=len(data["jobs"]), name="F")
        for i, j in liens:
            travail = X.sum(i, j, "*", "*")
            m.addConstr(travail <= h * B[i, j], name=f"travail_si_lien[{i},{j}]")
            m.addConstr(B[i, j] <= travail, name=f"lien_si_travail[{i},{j}]")
        for i in personnes:
            m.addConstr(B.sum(i, "*") <= F, name=f"dispersion[{i}]")
        benefice, cout, borne = G - R, gp.LinExpr(F), len(data["jobs"])
    m.setObjective(benefice, GRB.MAXIMIZE)
    m.update()
    return m, X, Y, E, L, benefice, cout, borne
