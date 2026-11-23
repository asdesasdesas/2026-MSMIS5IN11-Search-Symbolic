from pyshacl import validate
from rdflib import Graph

def run_shacl_validation(data_path, shapes_path):
    data_graph = Graph().parse(data_path, format="turtle")
    shacl_graph = Graph().parse(shapes_path, format="turtle")
    
    conforms, _, results_text = validate(
        data_graph,
        shacl_graph=shacl_graph,
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        inference="rdfs",
        debug=False
    )
    return conforms, results_text