import random
import os

def generate_rdf_database(filepath, num_patients=1000, error_rate=0.05):
    
    # Création du dossier data
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    rdf_content = [
        "@prefix fhir: <http://hl7.org/fhir/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix ex: <http://example.com/patient/> .\n"
    ]
    
    injected_errors = 0
    
    for i in range(1, num_patients + 1):
        birth_year = random.randint(1940, 2000)
        
        # Injection d'une incohérence clinique 
        if random.random() < error_rate:
            death_year = birth_year - random.randint(1, 5)  # Erreur : décès avant naissance
            injected_errors += 1
        else:
            death_year = birth_year + random.randint(10, 40) # Valide
            
        rdf_content.append(f"ex:Patient{i} a fhir:Patient ;")
        rdf_content.append(f'    fhir:Patient.birthDate [ fhir:value "{birth_year}-01-01"^^xsd:date ] ;')
        rdf_content.append(f'    fhir:Patient.deceasedDateTime [ fhir:value "{death_year}-05-15"^^xsd:date ] .\n')
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(rdf_content))
        
    return injected_errors