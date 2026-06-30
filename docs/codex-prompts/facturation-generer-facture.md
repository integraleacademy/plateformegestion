# Prompt Codex — Correction du bouton « Générer la facture »

```text
Dans la page admin sessions > Outils > Facturation, corriger le bouton “Générer la facture”.

Actuellement, quand je clique sur “Générer la facture” depuis une ligne de la gestion des factures, il ne faut pas générer directement la facture ni rester sans réaction.

Comportement attendu :

1. Le bouton “Générer la facture” doit ouvrir exactement la même modale que celle utilisée dans admin trainee pour générer une facture.
   - Réutiliser le même composant / la même logique existante si possible.
   - Ne pas dupliquer du code inutilement.
   - La modale doit être design, claire, centrée, responsive, avec overlay propre.
   - Le bouton fermer / croix doit fonctionner parfaitement.

2. La modale doit être préremplie avec les informations de la ligne sélectionnée :
   - nom du stagiaire
   - prénom du stagiaire
   - formation
   - session / nom pédagogique
   - dates de formation
   - type de financeur : CPF, Personnel, France Travail, OPCO, entreprise, etc.
   - montant exact de la ligne
   - éventuel numéro de facture existant s’il y en a déjà un
   - statut facture
   - statut paiement

3. Workflow obligatoire :
   - Étape 1 : afficher le récapitulatif de la facture à créer.
   - Étape 2 : bouton “Créer la facture en brouillon”.
   - La facture doit d’abord être créée en BROUILLON uniquement.
   - Ne jamais créer une facture définitive directement depuis le tableau.
   - Après création du brouillon, afficher clairement :
     - numéro de facture / brouillon si disponible
     - statut “Brouillon créé”
     - lien ou bouton “Voir la facture”
     - bouton “Synchroniser paiement” si disponible
     - bouton “Finaliser / valider la facture” uniquement si cette fonctionnalité existe déjà dans admin trainee.

4. Le comportement doit être exactement le même que dans admin trainee :
   - même endpoint si possible
   - même logique Qonto
   - même gestion TVA / exonération TVA
   - même format de facture
   - même gestion des erreurs
   - même affichage des retours API
   - même mise à jour de la base de données
   - même statut visuel après création

5. Très important :
   - Pour les organismes de formation, ne pas ajouter automatiquement de TVA si le système existant admin trainee fonctionne déjà sans TVA.
   - Respecter exactement la logique existante d’exonération TVA utilisée ailleurs.
   - Ne pas modifier les montants.
   - Une ligne CPF à 1500 € doit générer un brouillon à 1500 €, pas 1500 € + TVA.
   - Une ligne “Personnel” doit générer uniquement le montant personnel.
   - Si un stagiaire a plusieurs financeurs, chaque ligne du tableau doit générer sa propre facture séparée.

6. Après création du brouillon :
   - mettre à jour la ligne dans le tableau sans recharger toute la page si possible
   - statut facture : “Brouillon créé” ou statut équivalent
   - date facture : date de création du brouillon
   - numéro de facture : afficher le numéro ou l’identifiant retourné
   - le bouton “Générer la facture” doit devenir “Voir / modifier la facture” ou “Voir le brouillon”
   - ne jamais recréer un doublon si une facture existe déjà pour cette ligne

7. Sécurité anti-doublon :
   - Avant de créer une facture, vérifier s’il existe déjà une facture liée à cette ligne de facturation.
   - Identifier une ligne de manière fiable avec un identifiant unique, par exemple :
     - trainee_id
     - session_id
     - financeur_type
     - montant
     - invoice_line_id si déjà existant
   - Si une facture existe déjà, ouvrir la modale en mode “facture existante” au lieu d’en créer une nouvelle.
   - Afficher un message clair : “Une facture existe déjà pour cette ligne.”

8. UX :
   - quand on clique sur “Générer la facture”, afficher immédiatement la modale ou un loader
   - désactiver le bouton pendant la création
   - afficher les erreurs API clairement dans la modale
   - ne jamais laisser l’utilisateur sans retour visuel
   - ajouter des notifications toast de succès / erreur

9. Corriger aussi le problème de largeur / mise en page visible sur la page Facturation :
   - le tableau doit prendre toute la largeur utile
   - éviter que les colonnes soient coupées
   - prévoir un scroll horizontal propre si nécessaire
   - les boutons doivent rester visibles
   - les statuts doivent rester lisibles
   - la colonne “Statut paiement” ne doit pas être coupée à droite

10. Vérifications techniques :
   - chercher où est définie la modale facture dans admin trainee
   - extraire la logique dans un composant réutilisable si nécessaire
   - brancher la page Facturation dessus
   - ne pas casser admin trainee
   - ne pas casser les factures déjà existantes
   - vérifier les erreurs JS console
   - vérifier que le bouton ferme bien la modale
   - vérifier que la création de brouillon fonctionne depuis admin trainee ET depuis la page Facturation

Critères de validation :
- Depuis admin trainee, la génération de facture fonctionne toujours.
- Depuis Outils > Facturation, cliquer sur “Générer la facture” ouvre la même modale.
- La modale est préremplie avec les données de la ligne.
- Le premier bouton crée uniquement une facture en brouillon.
- Aucun doublon n’est créé.
- La TVA n’est pas ajoutée par erreur.
- La ligne du tableau est mise à jour après création.
- Le bouton “Synchroniser paiement” reste disponible après création.
- Aucune erreur JS dans la console.
- La mise en page du tableau est propre et exploitable sur desktop.
```
