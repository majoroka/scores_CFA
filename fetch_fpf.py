from competition_configs import SENIORES
from competition_sync import run_sync

OUTPUT_FILE = 'data/seniores.json'


def main():
    run_sync(SENIORES)


if __name__ == '__main__':
    main()
