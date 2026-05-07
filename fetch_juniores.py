from competition_configs import JUNIORES
from competition_sync import run_sync

OUTPUT_FILE = 'data/juniores.json'


def main():
    run_sync(JUNIORES)


if __name__ == '__main__':
    main()
