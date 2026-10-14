"""Conseils de routine simples (cosmétiques, non médicaux) à partir des scores et des capteurs."""


def advice(report, sensors):
    c = report["criteres"]
    tips = []
    if c["acne"]["score"] >= 55:
        tips.append("Nettoyant doux matin et soir, éviter de toucher les boutons")
    elif c["acne"]["score"] >= 25:
        tips.append("Nettoyage doux le soir, produits non comédogènes")
    if c["rides"]["score"] >= 40:
        tips.append("Crème hydratante et protection solaire chaque matin")
    if c["taches"]["score"] >= 40:
        tips.append("Protection solaire SPF 30+ même par temps couvert")
    if c["pores"]["score"] >= 40:
        tips.append("Exfoliation douce une fois par semaine")
    hum = sensors.get("humidite")
    if hum is not None and hum < 35:
        tips.append(f"Air sec ({hum:.0f} %) : penser à bien hydrater la peau")
    t = sensors.get("t_visage")
    if t is not None and t > 36.5:
        tips.append("Peau chaude : rincer à l'eau fraîche peut apaiser les rougeurs")
    if not tips:
        tips.append("Peau en bon état : garder une routine simple (nettoyer, hydrater, protéger)")
    return tips[:3]
