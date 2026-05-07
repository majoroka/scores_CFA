from competition_configs import FEMININO_SUB17
from competition_sync import run_sync

OUTPUT_FILE = 'data/feminino-sub17.json'


def main():
    run_sync(FEMININO_SUB17)


if __name__ == '__main__':
    main()
