from competition_configs import BENJAMINS_BB
from competition_sync import run_sync

OUTPUT_FILE = 'data/benjamins-bb.json'


def main():
    run_sync(BENJAMINS_BB)


if __name__ == '__main__':
    main()
