# Prospection : sites web pour restaurants sans site

Une équipe d'agents Claude Code qui trouve les restaurants proches de chez toi sans site web,
puis prépare pour chacun un site de démonstration à montrer au patron.

## L'équipe

| Rôle | Fichier | Ce qu'il fait |
|---|---|---|
| Chef de projet | `.claude/skills/chef-de-projet/SKILL.md` | orchestre tout, vérifie, fait le bilan |
| Prospecteur | `.claude/agents/prospecteur.md` | cherche sur Google Maps les restaurants sans site |
| Analyste | `.claude/agents/analyste.md` | écrit le cahier des charges du site idéal |
| Designer A | `.claude/agents/designer-chaleureux.md` | variante chaleureuse et traditionnelle |
| Designer B | `.claude/agents/designer-moderne.md` | variante moderne et épurée |
| Designer C | `.claude/agents/designer-conversion.md` | variante pensée pour faire appeler / venir |
| Juge | `.claude/agents/juge.md` | note les 3 variantes et désigne la meilleure |

Le chef de projet est une *skill* et non un agent : dans Claude Code, un sous-agent ne peut pas
lancer d'autres sous-agents, donc c'est la session principale qui joue le chef.

## Installation

1. Installer [Claude Code](https://code.claude.com) et Python 3.
2. **Clé Google Maps** (recommandée) :
   - sur <https://console.cloud.google.com>, créer un projet et activer **Places API (New)** ;
   - créer une clé API dans « Identifiants » et la restreindre à Places API ;
   - `export GOOGLE_MAPS_API_KEY="ta-clé"`.

   Google offre un crédit mensuel ; les champs demandés (site web, avis) sont facturés au tarif
   « Enterprise », mais une recherche de 60 restaurants reste à quelques dizaines de centimes.
   Mets une alerte de budget dans la console pour être tranquille.

   Sans clé, le script passe par OpenStreetMap : gratuit, mais beaucoup de restaurants y
   manquent ou n'ont pas leur site renseigné, donc plus de faux « sans site ».

## Utilisation

Dans ce dossier, lance `claude` puis :

```
/chef-de-projet adresse "Rue de l'Exemple 1, Ma Ville", rayon 1500 m, 3 sites
```

Ou seulement la recherche :

```
python3 scripts/trouver_restaurants.py --adresse "Rue de l'Exemple 1, Ma Ville" --rayon 1500
```

## Résultats

```
prospects/
  liste.json                 tous les prospects trouvés
  bilan.md                   synthèse du chef de projet
  <restaurant>/
    fiche.json               données Google (adresse, tél., horaires, avis…)
    analyse.md               cahier des charges
    variantes/a-chaleureux/  variante A
    variantes/b-moderne/     variante B
    variantes/c-conversion/  variante C
    verdict.md               notes du juge
    site-final/index.html    le site à montrer
```

Les captures d'écran et `prospects/liste.json` (résultats bruts) ne sont pas versionnés.

## Limites à connaître

- « Pas de site sur Google » ne veut pas dire « pas de site ». Vérifie toujours avant de démarcher.
- On utilise l'API officielle et pas un scraping de Google Maps, qui est interdit par leurs conditions
  et se fait bloquer.
- Les sites de démo contiennent des contenus supposés, marqués « exemple ». Ne les mets jamais en
  ligne sans validation du patron, et n'utilise pas ses photos Google sans son accord.
