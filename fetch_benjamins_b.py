from competition_configs import BENJAMINS_B
from competition_sync import run_sync

OUTPUT_FILE = 'data/benjamins-b.json'


def main():
    run_sync(BENJAMINS_B)


if __name__ == '__main__':
    main()
