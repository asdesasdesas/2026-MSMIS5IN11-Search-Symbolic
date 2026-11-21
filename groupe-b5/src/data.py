"""On va charger les donénes de contact et créer un grpahe 

On commence par gérer 2 formats de fichiers : 
  1. le format brut SocioPatterns (.dat / .csv / .gz) : une ligne = "t i j" (+ "Ci Cj")
     où [t-20s, t] est l'intervalle de 20 secondes pendant lequel i et j étaient en contact ;
  2. le format Netzschleuder (.zip) : edges.csv (source, target, time) + nodes.csv.

On agrège ensuite tous les contacts en un graphe :
  - un nœud = une personne,
  - une arête = au moins `min_contacts` intervalles de 20 s passés ensemble,
  - le poids de l'arête = nombre d'intervalles de 20 s en contact.

Avec ça on perd du temps, mais on peut faire tourner les algorithmes d'optimisation.  
"""
from __future__ import annotations #permet d'utiliser des types modernes (ex: dict | None)  

#bibliothèques et dictionnaires 
import io
import json
import warnings
import zipfile
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd



# 1. Lecture des fichiers de contacts
#Lire un CSV sociopatterns 
def _read_socio_raw(path):

    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, compression="infer")
        #on ouvre le fichier avec pandas; sep=r"\s+" signifie que les colonnes sont séparées par un ou plusieurs espaces,
        # header=None il n'y a pas d'en-tête dans le fichier brut, compression="infer" permet à pandas de détecter automatiquement si le fichier est compressé
    
    except pd.errors.EmptyDataError: #on va gérer les erreurs de lecture de fichiers vides ou illisibles   
        raise ValueError(f"{path} : fichier vide") from None 
     #raise permet de lever une exeption
    except pd.errors.ParserError as err:  
        raise ValueError(f"{path} : format illisible ({err})") from None
    
    if df.shape[1] < 3: #on vérifie qu"il y a au moins 3 colonnes (temps,personne i et j)
        raise ValueError(f"{path} : il faut au moins 3 colonnes (t i j)")
    ncols = 5 if df.shape[1] >= 5 else 3 
    #et si y'en a 5, on garde les 2dernières : gi et gj
    df = df.iloc[:, :ncols].copy()
    df.columns = ["t", "i", "j", "gi", "gj"][:ncols]

    before = len(df) #on va stocker le nombre de lignes avant suppression des lignes incomplètes
    df = df.dropna(subset=["t", "i", "j"]) # on va supprimer avec dropna les lignes qui contiennent des valeurs manqauntes/nulles
    #grâce a substet qui va préciser sur quelles collojnes on vérirfie des valeurs 

    if len(df) < before: #on regarde s'il y a eu des supprésssions 
        warnings.warn(f"{path} : {before - len(df)} ligne(s) incomplète(s) ignorée(s)") #averti si ddes lignes ont bien été supprimées 
   
    try:
        df["i"] = df["i"].astype(int)
        df["j"] = df["j"].astype(int)#convertit les 2 colonnes en entiers
    except (ValueError, TypeError):#si c'est impossible, on lève l'erreur et on affiche l'erruer levée (from None)
        raise ValueError(f"{path} : les colonnes i et j doivent contenir des identifiants entiers") from None
    if df.empty:
        raise ValueError(f"{path} : aucun contact exploitable")

    groups = {} #on crée un dictionnaire vide 
    if ncols == 5:  #si le nombre de colonne = 5 alors on associe chaque personne à son groupe
        for who, grp in zip(df["i"], df["gi"]):
            groups[int(who)] = str(grp)
        for who, grp in zip(df["j"], df["gj"]):
            groups[int(who)] = str(grp)
    return df[["t", "i", "j"]], groups #retourne la dataframe avec seulement t, i, j et le dictionnaire

#lire un CSV Netzschleuder
def _read_nz_csv(raw: bytes) -> pd.DataFrame: 
    #étant donné que les CSV de Netzschleuder ont un en-tête qui commence par '# ',

    lines = raw.decode("utf-8").splitlines() #on va diviser le texte en lignes
    header = [c.strip() for c in lines[0].lstrip("#").split(",")] #on va enlever de # et le ' '
    return pd.read_csv(io.StringIO("\n".join(lines[1:])), header=None, names=header) 
#on retourne un objet de type DataFrame de pandas avec les colonnes du csv, en utilisant io.StringIO pour lire les lignes restantes du CSV après l'en-tête. 


#lire une archive ZIP Netzschleuder
def _read_netzschleuder(path):
    try:
        with zipfile.ZipFile(path) as z: #ouvrire l'archive ZIP
            names = {Path(n).name: n for n in z.namelist()} #lister les fichuiers de l'archive ,avec namelist qui retourne une liste des noms de ficheirs
            if "edges.csv" not in names: #s'il n'ya pas edges.csv dans les noms de fichuers
                raise ValueError(f"{path} : pas de edges.csv dans l'archive ({list(names)})") #on lève l'erruer avec un message d'erruer et liste(name) affiche la liste des noms trouvés
            
            #z.read() lit le contenu du fichier et retourne des bytes et c'est avec la focntion _read_nz_csv qy'on va convertuir les bytes en DataFrame pandas 
            edges = _read_nz_csv(z.read(names["edges.csv"])) 
            nodes = _read_nz_csv(z.read(names["nodes.csv"])) if "nodes.csv" in names else None  #retourne soit un datafrmae (existe) ou None (existe pas)
    
    except zipfile.BadZipFile: #si le zip est corrompu ou invalide, on masque l'exception technique pour ne montrer que le message (from None)
        raise ValueError(f"{path} : archive zip invalide ou corrompue (téléchargement interrompu)") from None
    
    if not {"source", "target"} <= set(edges.columns):#on regarde si l'ensemble des colonnes de edges contient les colonnes source et target
        raise ValueError(f"{path} : edges.csv doit avoir les colonnes source et target ({list(edges.columns)})")
    #si il n'y est pas, on lève une erreur avec un message et la liste des collones de edge

    src, dst = edges["source"], edges["target"] #on extrait les 2 colonnes et on lew assignes a 2 variables
    groups = {} #création d'un dictionanaire vidde qui va associer chaque personne à son groupe
    if nodes is not None:
        idx_col = "index" if "index" in nodes.columns else nodes.columns[0] 
        #nodes a souvent une colonne index qui contient l'identifiant numérique, et si elle existe, on la prend sinon, on prend la première colonne.
       
        label = nodes["id"] if "id" in nodes.columns else nodes[idx_col] 
        #Si une colonne id existe, on la prend sinon, on utilise idx_col
        
        mapping = dict(zip(nodes[idx_col], label)) #zip(nodes[idx_col], label) crée des paires (index, label) qu'on transfrome en ddictionnaire avec dict()
        src, dst = src.map(mapping), dst.map(mapping) #on remplace chaque valeur de src par sa valeur correspondantde dans mapping
        
        extra = [c for c in nodes.columns if c not in (idx_col, "id")] # on va lister les colonnes qui ne sont n i idx_col ni id avec extra
        if extra:  # première colonne en plus qui est souvent le statut ou la classe
            groups = {int(a): str(g) for a, g in zip(label, nodes[extra[0]])}
            #le dictionnaire assicie chaque label à son groupe, que l'on convertie en entier (int()) et en groupe de chaine (str())

    t = edges["time"] if "time" in edges.columns else pd.Series(np.zeros(len(edges)))
    #on extrait la collonne temps si elle est présente dans les colonnes de edge
    #sinon on créer une série de 0 de la meme longueur que edge
    # il faut que la colonne existe pour que load_contacts retourne un DataFrame cohérent
    try:
        df = pd.DataFrame({"t": t, "i": src.astype(int), "j": dst.astype(int)}) #cration du dataframe avec 3 colonnes auquel on a assigné les 3 valeurs, et ou i et j sont cconverti en entier 
    except (ValueError, TypeError): #si la conversion échoue 
        raise ValueError(f"{path} : identifiants de nœuds manquants ou non entiers") from None #on lève une ValueError claire
    
    if df.empty: #vérifie que la dataframe n'est pas vide
        raise ValueError(f"{path} : aucun contact exploitable") #sinon on lève l'erreur 
    return df, groups #retourne le dataframe et le dictionnaire 


def load_contacts(path): #Renvoie (DataFrame, dict)
    path = Path(path) #transforme une chaine en objet Path
    if not path.exists():#vérifie que le fichier existe, et si non, alors :
        raise FileNotFoundError( #on lève l'exception et un message s'affiche 
            f"{path} introuvable. Télécharge le jeu de données (voir README.md, "
            "section 'Données') ou utilise --synthetic pour un test rapide."
        )
    if path.suffix == ".zip": #Si le fichier est une archive ZIP, on sait que c'est du format Netzschleuder,
        return _read_netzschleuder(path) #et on appèle la fonction correspondante
    return _read_socio_raw(path) #sinon c'est du format brut SocioPatterns et on appèle la fonction correspondante



# 2. Construction du graphe statique
def build_graph(contacts: pd.DataFrame, groups: dict | None = None, min_contacts: int = 1) -> nx.Graph:
    #création de la focntion avec ses paramètres et on retourne un graphe en sortie
    #dict | None  signifique que c'est sot un l'un soit l'autre

    groups = groups or {} # si groups est None, on le remplace par un dictionnaire vide
    pairs = Counter( #retourne un dictionnaire ou chaque élément est associé à son nombre d'application 
    #grâce à Counter qui compte les occurences d'éléments dans un itérable
        (min(a, b), max(a, b)) for a, b in zip(contacts["i"], contacts["j"]) if a != b
        #contact[] sont les colonnes pandas des id, i des 1eres personnes, j des 2emes 
        #zip crée des paires (i, j) pour chaque ligne du Dataframe 
        #on va dond itèrer sur chauque paire (a et b), et ignorer les paires ou a == et 
        #et où une paire identique (min() , max()) soit représentés de la même manière
    )

    G = nx.Graph() #création d'en graphe vide non orienté (arrête (A,B) identique à (B,A))
   
    people = set(contacts["i"]) | set(contacts["j"]) | set(groups)
    # set(contacts["i"]) : l'ensemble des IDs des 1ere personnes
    # set(contacts["j"]) : l'ensemble des IDs des 2nd personnes
    # set(groups) : l'ensemble des clés du dictionnaire groups (les personnes qui ont un groupe défini)
    # | : union d'ensembles, on combine les trois

    G.add_nodes_from(sorted(int(p) for p in people)) #on va ensuite ajouter tous les noeuds à la fois 
    #sorted permet d'éviter l'aléatoire, et on convertit chaque ID en entier 
    
    for (a, b), w in pairs.items(): #on va itérer sur les les (a,b) et w du counter avec pair.item
        if w >= min_contacts: #on ne garde que les arrêtes avec un poid suppérieur au min_contact
            G.add_edge(int(a), int(b), weight=int(w)) #on ajoute des arr^te entre les a et b et un poids leur est associé
    for v in G.nodes:
        G.nodes[v]["group"] = groups.get(v, "?") #  on ajoute l'attribut group à chaque nœud. Si la personne n'est pas dans groups, met "?"
    return G #retourne le graphe


def load_graph(path, min_contacts: int = 1) -> nx.Graph:
    contacts, groups = load_contacts(path)
    return build_graph(contacts, groups, min_contacts)



# 3. Graphe synthétique (seulement pour les tests et le développement)
def synthetic_graph(n_groups=4, group_size=20, p_in=0.35, p_out=0.01, seed=0) -> nx.Graph:
    #p_in = Probabilité de contact dans la même communauté
    #p_out = Probabilité de contact entre communautés

    sizes = [group_size] * n_groups #liste des tailles de chaque communauté
    probs = [[p_in if a == b else p_out for b in range(n_groups)] for a in range(n_groups)]
  #on créé la matrice de probailité entre les groupes pour chaque pair de group (a,b)

    sbm = nx.stochastic_block_model(sizes, probs, seed=seed)
    #nx.stochastic_block_model est un générateur de graphe aléatoire de NetworkX
    #avec les noeuds répartits en bloc de tailles "sizes" et associé une probabilité "probs"
    rng = np.random.default_rng(seed) #on gérère un nombre aléatoire
    G = nx.Graph() #création du graphe vide 
    G.add_nodes_from(sbm.nodes) #on ajoute les noeuds de sbm 
    
    for u, v in sbm.edges: #pour chaque arr^te du graphe SBM, on ajoute la même arrête au graphe G
        G.add_edge(u, v, weight=int(rng.integers(1, 15))) #et on lui ajoute un poids aléatoire pour simuler la durée des contacts 
    for v in G.nodes: #pour chaque neouds,
        G.nodes[v]["group"] = f"G{sbm.nodes[v]['block']}" #on lui attribut un attribut "group" dont la valeur est selon block SBM
    return G #retourne le graphe 



# 4. Sauvegarde / lecture du graphe en JSON (lu aussi par le vérificateur)
def save_graph_json(G: nx.Graph, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True) #crée le dossier parent s'il n'existe pas et ne relève pas d'erreur si le dossier existe deja 
    data = {
        "nodes": sorted(int(v) for v in G.nodes), #liste itéré, convertie en int et triée des ID de noeuds
        "edges": [[int(u), int(v), int(d.get("weight", 1))] for u, v, d in G.edges(data=True)],
        #on itère sur les arêtes en incluant les attributs : chaque élément est un tuple (u, v, attrs), en mettant comme poids 1 par defaut
        "groups": {str(v): G.nodes[v].get("group", "?") for v in G.nodes},
        #dictionnaire qui associe chaque noeuds à son groupe, convertie le noeuds en chaine et on récupère les le groupe, avec  " ?" par défaut si absent
    }
    path.write_text(json.dumps(data), encoding="utf-8") #convertit le dictationnaire data en chaine JSON, ensuite écrit dans le fichier en utilisant l'encodage UTF-8


def load_graph_json(path) -> nx.Graph: #on charge le graphe depuis JSON
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    #on lit le contenu du fichier en chaine et parse la chaine JSON en dict Python
    G = nx.Graph()
    G.add_nodes_from(data["nodes"]) #ajoute les boeuds 
    for u, v, w in data["edges"]: #pour chaque triplet, 
        G.add_edge(u, v, weight=w) #on leur ajoute l'arrête avec le poids 
    for v, g in data.get("groups", {}).items(): #récupération du dictionnaire avec {} par défaut         
        G.nodes[int(v)]["group"] = g #ajoute l'attribut "group" au noeud
    return G
