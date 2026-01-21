import os
import json
import unicodedata

CRESTS_DIR = "img/crests"
OUTPUT_FILE = "data/crests.json"

def _strip_diacritics(text: str) -> str:
    return ''.join(
        ch for ch in unicodedata.normalize('NFD', text)
        if unicodedata.category(ch) != 'Mn'
    )

def normalize_name(filename):
    """Normaliza o nome do ficheiro para coincidir com a app (lowercase, sem acentos, sem pontuação)."""
    name_part = os.path.splitext(filename)[0]
    name_part = _strip_diacritics(name_part)
    name_part = name_part.lower().replace('-', ' ').replace('_', ' ')
    name_part = ''.join(ch if (ch.isalnum() or ch == ' ') else ' ' for ch in name_part)
    name_part = ' '.join(name_part.split())
    return name_part

def main():
    """Varre a pasta de emblemas e gera um manifesto JSON."""
    if not os.path.isdir(CRESTS_DIR):
        print(f"ERRO: O diretório de emblemas '{CRESTS_DIR}' não foi encontrado.")
        return

    crest_map = {}
    for filename in os.listdir(CRESTS_DIR):
        if filename.lower().endswith('.png'):
            normalized = normalize_name(filename)
            path = f"{CRESTS_DIR}/{filename}"
            crest_map[normalized] = path

    # Aliases para variações de nomes que aparecem na FPF
    aliases = {
        'fc 11 esperancas': ['fc os 11 esperancas'],
        'casa slb albufeira': ['casa benfica albufeira'],
        'nucleo scp olhao': ['nucleo sporting cp olhao'],
        'fc ferreiras': ['fc ferreiras a', 'fc ferreiras b'],
        '4 ao cubo ado': ['4 ao cubo ad olhao'],
        'lusitano fc': ['lusitano fc vrsa'],
        'ef monte gordo': ['aef monte gordo 2019'],
        'ad tavira': ['adt ass desp tavira'],
    }
    for canon, alts in aliases.items():
        if canon in crest_map:
            for alt in alts:
                crest_map.setdefault(alt, crest_map[canon])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(crest_map, f, ensure_ascii=False, indent=4)

    print(f"Manifesto de emblemas gerado com sucesso em '{OUTPUT_FILE}' com {len(crest_map)} entradas.")

if __name__ == "__main__":
    main()
