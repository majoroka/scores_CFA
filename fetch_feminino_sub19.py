from competition_configs import FEMININO_SUB19
from competition_sync import run_sync

OUTPUT_FILE = 'data/feminino-sub19.json'


def main():
    run_sync(FEMININO_SUB19)


if __name__ == '__main__':
    main()
