# Prototypes isolés — Studio visuels

Cet espace est une planche de validation graphique statique. Il n'est relié ni à la page d'administration, ni au backend, ni à la sauvegarde, ni à l'export du Studio.

## Consulter et régénérer

Servir ce dossier localement puis ouvrir la page de comparaison :

```bash
python -m http.server 8000 --directory docs/studio-visuels-prototypes
```

Les huit rendus sont versionnés dans `exports/` sous forme Base64 textuelle afin que la revue de code ne les refuse pas comme fichiers binaires. La page les décode automatiquement. La commande suivante matérialise aussi huit fichiers PNG 1080 × 1080 locaux, volontairement ignorés par Git :

```bash
python docs/studio-visuels-prototypes/generate.py
```

La photographie stylisée intégrée aux maquettes est un asset de prototype créé localement par le générateur. Elle devra être remplacée par une photographie validée avant toute intégration.

## Directions

1. **Immersion** — photographie plein cadre, voile sombre et titre très contrasté.
2. **Éditorial** — portrait à gauche et colonne d'information structurée à droite.
3. **Impact typographique** — aucun visuel, mots massifs et rythme d'affiche.
4. **Diagonale** — portrait découpé, diagonale verte et informations en mouvement.
5. **Cartes utiles** — fond clair, grande accroche et trois cartes immédiatement scannables.
6. **Premium nocturne** — noir bleuté, filets verts et traitement plus institutionnel.
7. **Grand chiffre** — espace blanc maîtrisé autour du point focal « 328 h ».
8. **Bandeaux** — photographie centrale encadrée par deux zones d'information franches.
