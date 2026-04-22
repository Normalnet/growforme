import os
import re

replacements = {
    # Locations
    r'\bAmritsar\b': 'Accra',
    r'\bLudhiana\b': 'Kumasi',
    r'\bPatiala\b': 'Tamale',
    r'\bPunjab\b': 'Greater Accra',
    r'\bHaryana\b': 'Ashanti',
    r'\bUttar Pradesh\b': 'Eastern',
    r'\bRajasthan\b': 'Northern',
    r'\bMaharashtra\b': 'Central',

    # Names
    r'\bGurpreet Singh\b': 'Kwame Mensah',
    r'\bRavi Kulkarni\b': 'Ama Koomson',
    r'\bHarjeet Singh\b': 'Kofi Yeboah',
    r'\bSukhwinder Kaur\b': 'Abena Osei',
    r'\bBalwinder Gill\b': 'Yaw Asare',
    r'\bGurmail Sandhu\b': 'Kwame Appiah',
    r'\bRanjit Dhaliwal\b': 'Kojo Owusu',
    r'\bManjit Brar\b': 'Akosua Boakye',
    r'\bPreetpal Cheema\b': 'Adwoa Ofori',
    r'\bKulwant Sekhon\b': 'Kwasi Addo',

    # Suppliers
    r'\bAgriSeeds Punjab Pvt Ltd\b': 'AgriSeeds Ghana Ltd',
    r'\bIFFCO Co-op\b': 'CocoBod Inputs',
    
    # Custom Strings / Coordinates / Conversions
    r'31\.6295': '5.6037',     # Accra Base Lat
    r'74\.8696': '-0.1870',    # Accra Base Lon
    r'30\.9010': '6.6885',     # Kumasi Base Lat
    r'75\.8573': '-1.6244',    # Kumasi Base Lon
    r'31\.6350': '5.6080',     # Warehouse / DEL-002 Lat
    r'74\.8700': '-0.1820',    # Warehouse / DEL-002 Lon
    r'31\.6502': '5.6150',     # DEL-002 offset
    r'74\.8893': '-0.1700',
    r'31\.6120': '5.5900',     # DEL-003 offset
    r'74\.8540': '-0.2000',
    r'30\.9232': '6.7000',     # ORD-005
    r'75\.8712': '-1.6100',
    r'30\.8890': '6.6700',     # ORD-006
    r'75\.8400': '-1.6400',
    r'30\.3398': '9.4008',     # Tamale Lat
    r'76\.3869': '-0.8393',    # Tamale Lon
    r'30\.3600': '9.4200',
    r'76\.4100': '-0.8100',
    r'125\.8': '201.2', # Expected distance from Amritsar to Ludhiana was ~125.8. Accra to Kumasi is ~201km.
    
    r'test_known_distance_amritsar_ludhiana': 'test_known_distance_accra_kumasi',
    
    r'Village Lopoke': 'Osu',
    r'Village Fatehgarh': 'Cantonments',
    r'Village Ramdas': 'East Legon',
    
    # Currency
    r'â‚¹': 'GH₵',
    r'₹': 'GH₵',
    r'INR': 'GHS'
}

files_to_update = [
    'backend/app_simple.py',
    'docs/DEVELOPER_REFERENCE.md',
    'frontend/dashboard/analytics.html',
    'tests/test_api.py',
    'tests/test_batching.py',
    'tests/test_geofencing.py',
    'tests/conftest.py',
    'frontend/pod-interface/js/app.js'
]

for filepath in files_to_update:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for p_old, p_new in replacements.items():
            content = re.sub(p_old, p_new, content)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")
    else:
        print(f"Skipped {filepath}")

# Fix test boundary in test_geofencing.py for accra to kumasi distance
with open('tests/test_geofencing.py', 'r', encoding='utf-8') as f:
    content = f.read()
    content = content.replace('120 < dist < 140', '180 < dist < 230')
with open('tests/test_geofencing.py', 'w', encoding='utf-8') as f:
    f.write(content)
