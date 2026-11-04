// Family configuration for Famille HQ: Papa/Maman/Clara/Félix, chores/routine state, holidays,
// and French reading-practice word banks. Distinct from js/data.js, which owns the calendar.
window.FAMILY = (function () {
  'use strict';

  var people = {
    papa: { id: 'papa', name: 'Papa', color: '#2D5BFF', rgb: '45 91 255', ink: '#FFFFFF' },
    maman: { id: 'maman', name: 'Maman', color: '#E4007C', rgb: '228 0 124', ink: '#FFFFFF' },
    clara: { id: 'clara', name: 'Clara', age: 6, color: '#00A36C', rgb: '0 163 108', ink: '#FFFFFF' },
    felix: { id: 'felix', name: 'Félix', age: 8, color: '#FFB000', rgb: '255 176 0', ink: '#111111' }
  };

  var bathNights = [2, 4, 0]; // Tue, Thu, Sun

  var taskMenu = [
    { id: 'recycling', title: 'Trier le recyclage', emoji: '♻️', price: 1 },
    { id: 'table', title: 'Mettre la table', emoji: '🍴', price: 1 },
    { id: 'dishwasher', title: 'Vider le lave-vaisselle', emoji: '🍽️', price: 1 },
    { id: 'plants', title: 'Arroser les plantes', emoji: '🪴', price: 1 },
    { id: 'vacuum', title: 'Passer l’aspirateur', emoji: '🧹', price: 1 },
    { id: 'garbage', title: 'Sortir les poubelles', emoji: '🗑️', price: 1 }
  ];

  var routine = {
    clara: { room: false, bath: false, earned: 0, picked: [] },
    felix: { room: false, bath: false, earned: 0, picked: [] }
  };

  var holidays = [
    { name: 'Halloween', emoji: '🎃', month: 10, day: 31 },
    { name: 'Fête de l’Action de grâce', emoji: '🦃', month: 10, day: 12 },
    { name: 'Noël', emoji: '🎄', month: 12, day: 25 },
    { name: 'Jour de l’An', emoji: '🎆', month: 1, day: 1 },
    { name: 'Saint-Valentin', emoji: '💝', month: 2, day: 14 },
    { name: 'Cabane à sucre', emoji: '🍁', month: 3, day: 15 },
    { name: 'Pâques', emoji: '🐣', month: 4, day: 5 },
    { name: 'Fête des Mères', emoji: '💐', month: 5, day: 11 },
    { name: 'Fête des Pères', emoji: '🎁', month: 6, day: 15 },
    { name: 'Fête du Canada', emoji: '🇨🇦', month: 7, day: 1 },
    { name: 'Rentrée scolaire', emoji: '🎒', month: 9, day: 2 }
  ];

  // ---------------------------------------------------------------- Félix: spelling practice
  var felixSpelling = {
    themes: [
      { theme: 'École', words: ['école', 'maître', 'maîtresse', 'camarade', 'devoir', 'leçon', 'crayon', 'cahier', 'récréation', 'classe'] },
      { theme: 'Maison et famille', words: ['maison', 'famille', 'frère', 'sœur', 'cousin', 'grand-père', 'grand-mère', 'voisin', 'chambre', 'cuisine'] },
      { theme: 'Nature et saisons', words: ['automne', 'hiver', 'printemps', 'été', 'nuage', 'orage', 'forêt', 'rivière', 'montagne', 'étoile'] },
      { theme: 'Nourriture', words: ['déjeuner', 'dîner', 'souper', 'fromage', 'légume', 'fruit', 'pomme', 'fraise', 'citrouille', 'biscuit'] },
      { theme: 'Mots courants', words: [
        'seigneur', 'messieurs', 'calme', 'voudrais', 'heureux', 'prenez', 'mariage', 'voit', 'parents', 'dedans',
        'entrer', 'lit', 'serais', 'sale', 'sûrement', 'ordre', 'souvent', 'essayé', 'peuvent', 'visage',
        'bout', 'changé', 'sérieux', 'inquiète', 'ferais', 'début', 'espèce', 'acheter', 'continue', 'sort',
        'faim', 'long', 'voyage', 'message', 'sorte', 'reçu', 'patron', 'rapport', 'apprendre', 'commencé',
        'sauver', 'seconde', 'pensez', 'allô', 'ailleurs', 'agent', 'froid', 'seras'
      ] }
    ]
  };

  // ---------------------------------------------------------------- Clara: phonics by sound
  var claraPhonics = [
    { sound: 'a', words: ['papa', 'avion', 'ami'] },
    { sound: 'i', words: ['ici', 'lit', 'tapis'] },
    { sound: 'o', words: ['moto', 'vélo', 'zéro'] },
    { sound: 'u', words: ['tutu', 'lune', 'rue'] },
    { sound: 'é', words: ['été', 'vélo', 'école'] },
    { sound: 'è', words: ['mère', 'père', 'fève'] },
    { sound: 'ou', words: ['loup', 'roue', 'bijou'] },
    { sound: 'oi', words: ['roi', 'moi', 'toit'] },
    { sound: 'eu', words: ['feu', 'jeu', 'bleu'] },
    { sound: 'on', words: ['maison', 'ballon', 'savon'] }
  ];

  // ---------------------------------------------------------------- common-word bank ("mot du jour")
  // A broad, kid-safe slice of frequent French words. Not exhaustive — grown over time as needed.
  var wordBank = [
    'de', 'la', 'le', 'et', 'les', 'des', 'un', 'une', 'être', 'avoir', 'je', 'tu', 'il', 'elle', 'nous', 'vous',
    'ils', 'elles', 'ce', 'qui', 'que', 'dans', 'pour', 'pas', 'sur', 'avec', 'mais', 'ou', 'où', 'si', 'par',
    'plus', 'dire', 'tout', 'faire', 'bien', 'aller', 'voir', 'savoir', 'pouvoir', 'falloir', 'vouloir', 'venir',
    'devoir', 'prendre', 'donner', 'trouver', 'parler', 'aimer', 'passer', 'mettre', 'demander', 'tenir',
    'sembler', 'laisser', 'rester', 'penser', 'entendre', 'regarder', 'répondre', 'rendre', 'connaître',
    'paraître', 'sentir', 'arriver', 'jour', 'temps', 'an', 'fois', 'moment', 'main', 'homme', 'femme', 'enfant',
    'monde', 'vie', 'yeux', 'tête', 'maison', 'eau', 'pays', 'ami', 'chose', 'histoire', 'nuit', 'matin',
    'soir', 'mot', 'voix', 'porte', 'ville', 'air', 'coeur', 'esprit', 'travail', 'mer', 'ciel', 'terre',
    'soleil', 'lune', 'jardin', 'arbre', 'fleur', 'oiseau', 'chien', 'chat', 'cheval', 'lapin', 'poisson',
    'papa', 'maman', 'frère', 'soeur', 'bébé', 'école', 'classe', 'livre', 'crayon', 'table', 'chaise', 'lit',
    'fenêtre', 'rouge', 'bleu', 'vert', 'jaune', 'noir', 'blanc', 'gris', 'rose', 'orange', 'violet', 'grand',
    'petit', 'beau', 'joli', 'gentil', 'content', 'heureux', 'triste', 'fâché', 'fatigué', 'malade', 'froid',
    'chaud', 'doux', 'dur', 'facile', 'difficile', 'nouveau', 'vieux', 'jeune', 'premier', 'dernier', 'seul',
    'même', 'autre', 'chaque', 'quelque', 'plusieurs', 'beaucoup', 'peu', 'trop', 'assez', 'encore', 'déjà',
    'toujours', 'jamais', 'souvent', 'parfois', 'maintenant', 'après', 'avant', 'ensuite', 'enfin', 'ici',
    'là', 'partout', 'dehors', 'dedans', 'dessus', 'dessous', 'devant', 'derrière', 'loin', 'près', 'un',
    'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'cent', 'mille', 'lundi', 'mardi',
    'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre', 'printemps', 'été', 'automne', 'hiver',
    'manger', 'boire', 'dormir', 'jouer', 'courir', 'marcher', 'sauter', 'nager', 'chanter', 'danser', 'rire',
    'pleurer', 'crier', 'chuchoter', 'écouter', 'lire', 'écrire', 'dessiner', 'peindre', 'construire', 'casser',
    'ouvrir', 'fermer', 'allumer', 'éteindre', 'monter', 'descendre', 'entrer', 'sortir', 'partir', 'revenir',
    'commencer', 'finir', 'continuer', 'arrêter', 'attendre', 'chercher', 'trouver', 'perdre', 'gagner',
    'aider', 'partager', 'choisir', 'décider', 'essayer', 'réussir', 'apprendre', 'enseigner', 'comprendre',
    'expliquer', 'raconter', 'inviter', 'visiter', 'voyager', 'rêver', 'imaginer', 'oublier', 'rappeler',
    'famille', 'cousin', 'cousine', 'oncle', 'tante', 'grand-père', 'grand-mère', 'voisin', 'copain', 'copine',
    'camarade', 'maître', 'maîtresse', 'directeur', 'docteur', 'infirmière', 'pompier', 'policier', 'facteur',
    'boulanger', 'fermier', 'pêcheur', 'cuisinier', 'musicien', 'peintre', 'écrivain', 'chanteur', 'danseur',
    'sportif', 'nageur', 'coureur', 'cuisine', 'salon', 'chambre', 'salle', 'bain', 'jardin', 'garage', 'cour',
    'toit', 'mur', 'sol', 'escalier', 'couloir', 'placard', 'tiroir', 'miroir', 'lampe', 'horloge', 'tapis',
    'rideau', 'coussin', 'couverture', 'oreiller', 'serviette', 'savon', 'brosse', 'dentifrice', 'peigne',
    'vêtement', 'chemise', 'pantalon', 'robe', 'jupe', 'chaussette', 'chaussure', 'botte', 'manteau', 'chapeau',
    'écharpe', 'gant', 'ceinture', 'pyjama', 'maillot', 'sac', 'cartable', 'trousse', 'gomme', 'règle', 'ciseau',
    'colle', 'feuille', 'page', 'image', 'photo', 'carte', 'lettre', 'journal', 'magazine', 'dictionnaire',
    'histoire', 'conte', 'poème', 'chanson', 'musique', 'instrument', 'piano', 'guitare', 'tambour', 'flûte',
    'ballon', 'jeu', 'jouet', 'poupée', 'robot', 'puzzle', 'cube', 'corde', 'vélo', 'trottinette', 'patin',
    'piscine', 'plage', 'sable', 'vague', 'bateau', 'avion', 'train', 'voiture', 'camion', 'autobus', 'route',
    'pont', 'magasin', 'marché', 'boutique', 'caisse', 'argent', 'prix', 'cadeau', 'fête', 'anniversaire',
    'gâteau', 'bougie', 'ballon', 'invité', 'musique', 'danse', 'repas', 'déjeuner', 'dîner', 'souper', 'goûter',
    'pain', 'beurre', 'confiture', 'fromage', 'lait', 'jus', 'eau', 'soupe', 'salade', 'viande', 'poisson',
    'poulet', 'oeuf', 'riz', 'pâtes', 'pomme', 'poire', 'banane', 'orange', 'fraise', 'raisin', 'cerise',
    'citron', 'carotte', 'tomate', 'pomme-de-terre', 'haricot', 'petit-pois', 'salade', 'chocolat', 'bonbon',
    'glace', 'biscuit', 'tarte', 'miel', 'sucre', 'sel', 'poivre', 'huile', 'farine', 'oeuf', 'nuage', 'pluie',
    'neige', 'vent', 'orage', 'tonnerre', 'éclair', 'arc-en-ciel', 'brouillard', 'glace', 'gel', 'chaleur',
    'tempête', 'forêt', 'montagne', 'rivière', 'lac', 'océan', 'île', 'désert', 'vallée', 'colline', 'pierre',
    'roche', 'sable', 'herbe', 'feuille', 'branche', 'racine', 'graine', 'fruit', 'légume', 'jardin', 'ferme',
    'animal', 'vache', 'cochon', 'mouton', 'chèvre', 'poule', 'coq', 'canard', 'cheval', 'âne', 'souris', 'rat',
    'écureuil', 'renard', 'loup', 'ours', 'lion', 'tigre', 'éléphant', 'girafe', 'singe', 'serpent', 'tortue',
    'grenouille', 'papillon', 'abeille', 'fourmi', 'araignée', 'mouche', 'moustique', 'coccinelle',

    // --- extended coverage: body, health, emotions, time, school, town, sport, more verbs/adj ---
    'corps', 'bras', 'jambe', 'pied', 'doigt', 'orteil', 'genou', 'coude', 'épaule', 'dos', 'ventre',
    'poitrine', 'cou', 'menton', 'joue', 'front', 'sourcil', 'cil', 'paupière', 'narine', 'lèvre',
    'langue', 'dent', 'gorge', 'cheveux', 'oreille', 'nez', 'bouche', 'oeil', 'peau', 'os', 'muscle',
    'sang', 'coeur', 'poumon', 'cerveau', 'squelette', 'santé', 'maladie', 'fièvre', 'rhume', 'toux',
    'blessure', 'bleu', 'bosse', 'pansement', 'médicament', 'piqûre', 'vaccin', 'hôpital', 'clinique',
    'ambulance', 'urgence', 'guérir', 'soigner', 'respirer', 'tousser', 'éternuer', 'vomir',
    'content', 'joyeux', 'ravi', 'excité', 'calme', 'paisible', 'inquiet', 'nerveux', 'anxieux',
    'effrayé', 'terrifié', 'surpris', 'étonné', 'choqué', 'dégoûté', 'jaloux', 'fier', 'honteux',
    'gêné', 'timide', 'courageux', 'peureux', 'curieux', 'confus', 'perplexe', 'ennuyé', 'déçu',
    'frustré', 'énervé', 'furieux', 'calme', 'détendu', 'stressé', 'épuisé', 'reposé', 'motivé',
    'découragé', 'confiant', 'inquiet', 'amoureux', 'reconnaissant', 'généreux', 'égoïste',
    'patient', 'impatient', 'poli', 'impoli', 'honnête', 'menteur', 'juste', 'injuste', 'sage',
    'minute', 'seconde', 'heure', 'journée', 'semaine', 'mois', 'année', 'siècle', 'saison',
    'aujourd’hui', 'demain', 'hier', 'bientôt', 'tard', 'tôt', 'rapide', 'lent', 'vite', 'doucement',
    'rapidement', 'lentement', 'soudain', 'brusquement', 'calendrier', 'horaire', 'rendez-vous',
    'réveil', 'minuit', 'midi', 'aube', 'crépuscule', 'lever', 'coucher', 'pendule', 'chronomètre',
    'mathématiques', 'français', 'sciences', 'histoire', 'géographie', 'musique', 'art', 'sport',
    'éducation', 'physique', 'informatique', 'anglais', 'récréation', 'devoirs', 'examen', 'test',
    'note', 'résultat', 'réussite', 'échec', 'diplôme', 'rentrée', 'vacances', 'congé', 'pupitre',
    'tableau', 'craie', 'marqueur', 'surligneur', 'agrafeuse', 'perforatrice', 'classeur', 'reliure',
    'bibliothèque', 'bibliothécaire', 'cour', 'gymnase', 'cafétéria', 'autobus', 'scolaire',
    'directrice', 'principal', 'concierge', 'secrétaire', 'infirmier', 'conseiller', 'élève',
    'étudiant', 'groupe', 'équipe', 'projet', 'présentation', 'exposé', 'recherche', 'question',
    'réponse', 'problème', 'solution', 'idée', 'exemple', 'résumé', 'conclusion', 'introduction',
    'ville', 'village', 'quartier', 'rue', 'avenue', 'boulevard', 'trottoir', 'parc', 'place',
    'fontaine', 'statue', 'monument', 'musée', 'théâtre', 'cinéma', 'restaurant', 'café', 'hôtel',
    'banque', 'poste', 'pharmacie', 'épicerie', 'boulangerie', 'boucherie', 'librairie', 'station',
    'aéroport', 'gare', 'port', 'usine', 'bureau', 'commerce', 'entreprise', 'mairie', 'église',
    'temple', 'synagogue', 'mosquée', 'cimetière', 'pont', 'tunnel', 'autoroute', 'carrefour',
    'feu', 'signal', 'panneau', 'piéton', 'trottoir', 'circulation', 'embouteillage', 'klaxon',
    'football', 'hockey', 'basketball', 'baseball', 'tennis', 'volleyball', 'golf', 'ski',
    'patinage', 'natation', 'course', 'vélo', 'gymnastique', 'karaté', 'judo', 'escrime', 'boxe',
    'aviron', 'voile', 'pêche', 'chasse', 'randonnée', 'camping', 'escalade', 'équitation',
    'entraîneur', 'arbitre', 'joueur', 'équipe', 'match', 'tournoi', 'championnat', 'médaille',
    'trophée', 'record', 'victoire', 'défaite', 'but', 'point', 'score', 'terrain', 'stade',
    'arène', 'patinoire', 'vestiaire', 'casque', 'protège-dents', 'short', 'maillot', 'crampon',
    'raquette', 'bâton', 'rondelle', 'filet', 'panier', 'arbitrage', 'mi-temps', 'prolongation',
    'avocat', 'ingénieur', 'architecte', 'scientifique', 'journaliste', 'photographe', 'acteur',
    'actrice', 'réalisateur', 'auteur', 'traducteur', 'vétérinaire', 'dentiste', 'pharmacien',
    'électricien', 'plombier', 'mécanicien', 'menuisier', 'charpentier', 'peintre', 'couturier',
    'coiffeur', 'esthéticienne', 'comptable', 'banquier', 'vendeur', 'caissier', 'serveur',
    'chef', 'pâtissier', 'agriculteur', 'bûcheron', 'mineur', 'marin', 'capitaine', 'pilote',
    'astronaute', 'soldat', 'général', 'président', 'maire', 'gouverneur', 'roi', 'reine',
    'prince', 'princesse', 'chevalier', 'magicien', 'sorcière', 'fée', 'dragon', 'géant',
    'monstre', 'fantôme', 'vampire', 'zombie', 'extraterrestre', 'robot', 'super-héros',
    'planète', 'étoile', 'galaxie', 'univers', 'fusée', 'satellite', 'comète', 'astéroïde',
    'système', 'solaire', 'télescope', 'observatoire', 'gravité', 'orbite', 'atmosphère',
    'ordinateur', 'tablette', 'téléphone', 'écran', 'clavier', 'souris', 'imprimante', 'caméra',
    'appareil', 'batterie', 'chargeur', 'câble', 'internet', 'courriel', 'message', 'application',
    'logiciel', 'jeu-vidéo', 'manette', 'casque', 'télévision', 'radio', 'haut-parleur',
    'triangle', 'carré', 'cercle', 'rectangle', 'losange', 'ovale', 'cube', 'sphère', 'cylindre',
    'pyramide', 'ligne', 'point', 'angle', 'longueur', 'largeur', 'hauteur', 'poids', 'mesure',
    'centimètre', 'mètre', 'kilomètre', 'litre', 'kilogramme', 'gramme', 'addition', 'soustraction',
    'multiplication', 'division', 'fraction', 'nombre', 'chiffre', 'calcul', 'pair', 'impair',
    'oncle', 'neveu', 'nièce', 'beau-père', 'belle-mère', 'demi-frère', 'demi-soeur', 'jumeau',
    'jumelle', 'adulte', 'personne', 'gens', 'humain', 'voisinage', 'communauté', 'société',
    'culture', 'tradition', 'coutume', 'religion', 'langue', 'pays', 'nation', 'drapeau', 'carte',
    'continent', 'frontière', 'capitale', 'province', 'région', 'climat', 'température', 'saison',
    'douche', 'baignoire', 'robinet', 'toilette', 'évier', 'four', 'cuisinière', 'réfrigérateur',
    'congélateur', 'micro-ondes', 'grille-pain', 'bouilloire', 'casserole', 'poêle', 'assiette',
    'bol', 'tasse', 'verre', 'fourchette', 'couteau', 'cuillère', 'nappe', 'serviette',
    'aspirateur', 'balai', 'vadrouille', 'seau', 'poubelle', 'recyclage', 'compost', 'lessive',
    'sèche-linge', 'fer', 'planche', 'coffre', 'étagère', 'bibliothèque', 'canapé', 'fauteuil',
    'tabouret', 'bureau', 'imprimante', 'climatiseur', 'chauffage', 'thermostat', 'interrupteur',
    'prise', 'ampoule', 'bougie', 'allumette', 'briquet', 'extincteur', 'alarme', 'détecteur',
    'courageusement', 'gentiment', 'rapidement', 'soigneusement', 'attentivement', 'calmement',
    'tranquillement', 'joyeusement', 'tristement', 'fortement', 'doucement', 'silencieusement',
    'ensemble', 'séparément', 'longtemps', 'brièvement', 'exactement', 'presque', 'environ',
    'certainement', 'peut-être', 'probablement', 'évidemment', 'finalement', 'heureusement',
    'malheureusement', 'particulièrement', 'spécialement', 'simplement', 'facilement',
    'bateau', 'canot', 'kayak', 'voilier', 'sous-marin', 'traversier', 'hélicoptère', 'fusée',
    'montgolfière', 'planeur', 'tracteur', 'excavatrice', 'grue', 'bulldozer', 'ambulance',
    'pompier', 'police', 'taxi', 'métro', 'tramway', 'funiculaire', 'télécabine', 'luge',
    'traîneau', 'skateboard', 'patinette', 'tricycle', 'poussette', 'fauteuil', 'béquille'
  ];

  function dayNumber(date) {
    var start = new Date(date.getFullYear(), 0, 0);
    return Math.floor((date - start) / 864e5);
  }

  // Simple deterministic PRNG so "today's words" are stable all day but differ by kid/date.
  function pick(seed, n, pool) {
    var s = seed >>> 0;
    function next() { s = (s * 1103515245 + 12345) & 0x7fffffff; return s; }
    var used = {}, out = [];
    while (out.length < n && out.length < pool.length) {
      var idx = next() % pool.length;
      if (used[idx]) continue;
      used[idx] = true;
      out.push(pool[idx]);
    }
    return out;
  }

  function wordOfDay(personId, count, now) {
    now = now || new Date();
    var seed = dayNumber(now) * 1000 + (personId === 'clara' ? 1 : 2);
    return pick(seed, count || 5, wordBank);
  }

  return {
    people: people,
    bathNights: bathNights,
    taskMenu: taskMenu,
    routine: routine,
    holidays: holidays,
    felixSpelling: felixSpelling,
    claraPhonics: claraPhonics,
    wordBank: wordBank,
    dayNumber: dayNumber,
    wordOfDay: wordOfDay
  };
})();
