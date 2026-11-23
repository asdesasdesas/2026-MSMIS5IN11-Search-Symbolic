import time
from src.generator import generate_rdf_database
from src.shacl_engine import run_shacl_validation
from src.naive_engine import run_naive_validation

def main():
    
    db_path = "data/patients_db.ttl"
    shapes_path = "data/shapes.ttl"
    num_patients = 1000
    
    # 1. Génération
    errors_injected = generate_rdf_database(db_path, num_patients=num_patients, error_rate=0.05)
    
    # 2. IA Symbolique
    start_shacl = time.time()
    shacl_conforms, shacl_report = run_shacl_validation(db_path, shapes_path)
    time_shacl = time.time() - start_shacl
    print(f" Temps SHACL pour 1000 dossiers : {time_shacl:.4f} secondes")

    # 3. Comparatif
    patient_mock = {
        "resourceType": "Patient",
        "birthDate": "1990-01-01",
        "deceasedDateTime": "1985-05-15"
    }
    start_naive = time.time()
    naive_conforms, naive_report = run_naive_validation(patient_mock)
    time_naive = time.time() - start_naive
    print(f" Temps Naïf pour 1 dossier : {time_naive:.6f} secondes")
    print(f"parcourt {num_patients} dossiers et isole {errors_injected} aberrations")

if __name__ == "__main__":
    main()