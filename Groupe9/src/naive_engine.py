def run_naive_validation(patient_dict):
    if "deceasedDateTime" in patient_dict and "birthDate" in patient_dict:
        if patient_dict["deceasedDateTime"] < patient_dict["birthDate"]:
            return False, "ERREUR : Date de décès antérieure à la naissance."
    return True, "Patient valide."