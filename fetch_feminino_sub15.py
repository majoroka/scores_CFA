from competition_configs import FEMININO_SUB15
from competition_sync import run_sync

OUTPUT_FILE = 'data/feminino-sub15.json'


def main():
    run_sync(FEMININO_SUB15)


if __name__ == '__main__':
    main()
