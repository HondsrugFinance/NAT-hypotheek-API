"""
NAT Calculator - Output Contract Checker
Valideert dat calculator outputs voldoen aan het contract in output_contract.json
"""

import json
import sys
import os

def load_contract():
    """Load output contract schema"""
    contract_path = os.path.join(os.path.dirname(__file__), 'output_contract.json')
    try:
        with open(contract_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: output_contract.json niet gevonden in {os.path.dirname(__file__)}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: output_contract.json is geen geldige JSON: {e}")
        sys.exit(1)


def check_numeric(value, path):
    """Check if value is numeric (int or float)"""
    if not isinstance(value, (int, float)):
        print(f"ERROR: {path} moet numeriek zijn, is {type(value).__name__}: {value}")
        return False
    return True


def check_scenario_structure(scenario_data, scenario_name):
    """
    Check scenario structure:
    - annuitair object met: max_box1, max_box3, ruimte_box1, ruimte_box3
    - niet_annuitair object met: max_box1, max_box3, ruimte_box1, ruimte_box3
    Alle waarden moeten numeriek zijn
    """
    errors = []
    
    # Check annuitair
    if 'annuitair' not in scenario_data:
        errors.append(f"{scenario_name}.annuitair ontbreekt")
    else:
        annuitair = scenario_data['annuitair']
        required_keys = ['max_box1', 'max_box3', 'ruimte_box1', 'ruimte_box3']
        
        for key in required_keys:
            if key not in annuitair:
                errors.append(f"{scenario_name}.annuitair.{key} ontbreekt")
            elif not check_numeric(annuitair[key], f"{scenario_name}.annuitair.{key}"):
                errors.append(f"{scenario_name}.annuitair.{key} is niet numeriek")
    
    # Check niet_annuitair
    if 'niet_annuitair' not in scenario_data:
        errors.append(f"{scenario_name}.niet_annuitair ontbreekt")
    else:
        niet_annuitair = scenario_data['niet_annuitair']
        required_keys = ['max_box1', 'max_box3', 'ruimte_box1', 'ruimte_box3']
        
        for key in required_keys:
            if key not in niet_annuitair:
                errors.append(f"{scenario_name}.niet_annuitair.{key} ontbreekt")
            elif not check_numeric(niet_annuitair[key], f"{scenario_name}.niet_annuitair.{key}"):
                errors.append(f"{scenario_name}.niet_annuitair.{key} is niet numeriek")
    
    return errors


def check_output(output_data):
    """
    Valideer calculator output tegen contract
    
    Returns:
        (bool, List[str]): (is_valid, errors)
    """
    errors = []
    
    # Check top-level structure
    if not isinstance(output_data, dict):
        errors.append(f"Output moet een dict zijn, is {type(output_data).__name__}")
        return False, errors
    
    # Check scenario1 (verplicht)
    if 'scenario1' not in output_data:
        errors.append("scenario1 is verplicht")
    elif output_data['scenario1'] is None:
        errors.append("scenario1 mag niet null zijn")
    else:
        scenario1_errors = check_scenario_structure(output_data['scenario1'], 'scenario1')
        errors.extend(scenario1_errors)
    
    # Check scenario2 (optioneel, null toegestaan)
    if 'scenario2' not in output_data:
        errors.append("scenario2 key ontbreekt (moet null of object zijn)")
    elif output_data['scenario2'] is not None:
        # Als scenario2 niet null is, moet het dezelfde structuur hebben
        scenario2_errors = check_scenario_structure(output_data['scenario2'], 'scenario2')
        errors.extend(scenario2_errors)
    
    return len(errors) == 0, errors


def main():
    """
    Main functie - kan aangeroepen worden met output JSON via stdin of als argument
    """
    # Check of er een filename argument is
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Bestand {filename} niet gevonden")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"ERROR: {filename} is geen geldige JSON: {e}")
            sys.exit(1)
    else:
        # Lees van stdin
        try:
            output_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"ERROR: Ongeldige JSON in stdin: {e}")
            sys.exit(1)
    
    # Load contract (voor documentatie/toekomstig gebruik)
    contract = load_contract()
    
    # Check output
    is_valid, errors = check_output(output_data)
    
    if is_valid:
        print("✓ Output voldoet aan contract")
        print(f"  - scenario1: {len(output_data['scenario1']['annuitair'])} annuitair keys, {len(output_data['scenario1']['niet_annuitair'])} niet-annuitair keys")
        if output_data.get('scenario2') is not None:
            print(f"  - scenario2: {len(output_data['scenario2']['annuitair'])} annuitair keys, {len(output_data['scenario2']['niet_annuitair'])} niet-annuitair keys")
        else:
            print("  - scenario2: null (optioneel)")
        sys.exit(0)
    else:
        print("✗ Output voldoet NIET aan contract")
        print("\nGevonden fouten:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
