from pyshacl import validate
from rdflib import Graph

print("1. Chargement des données du patient (Format FHIR/RDF)...")
data_graph = Graph()
data_graph.parse("patient_invalide.ttl", format="turtle")

print("2. Chargement des règles cliniques (SHACL)...")
shacl_graph = Graph()
shacl_graph.parse("shapes.ttl", format="turtle")

print("3. Lancement de la validation symbolique...\n")
conforms, results_graph, results_text = validate(
    data_graph,
    shacl_graph=shacl_graph,
    data_graph_format="turtle",
    shacl_graph_format="turtle",
    inference="rdfs",
    debug=False,
    serialize_report_graph=True
)

if conforms:
    print("RÉSULTAT : Le dossier patient est cliniquement valide.")
else:
    print("RÉSULTAT : Incohérence détectée dans le dossier !")
    print("-" * 40)
    print(results_text)